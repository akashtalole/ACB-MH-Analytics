(() => {
  "use strict";
  const IN = new Intl.NumberFormat("en-IN");
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const $ = id => document.getElementById(id);

  function rupees(n) {
    if (n >= 1e7) return "₹" + (n / 1e7).toFixed(2) + " cr";
    if (n >= 1e5) return "₹" + (n / 1e5).toFixed(1) + " lakh";
    return "₹" + IN.format(Math.round(n));
  }
  const el = (tag, props = {}, ...kids) => {
    const e = Object.assign(document.createElement(tag), props);
    kids.forEach(k => e.append(k));
    return e;
  };

  let stats, records;
  const charts = [];

  function baseOpts(extra = {}) {
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.color = css("--muted");
    return Object.assign({
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
      scales: {
        x: { grid: { color: css("--grid") }, ticks: { color: css("--muted") } },
        y: { grid: { color: css("--grid") }, ticks: { color: css("--muted") }, beginAtZero: true },
      },
    }, extra);
  }
  function make(id, cfg) {
    const old = Chart.getChart(id); if (old) old.destroy();
    const c = new Chart($(id), cfg); charts.push(c); return c;
  }

  // ---------- KPIs ----------
  function kpis() {
    const t = stats.trap_totals, y = stats.yearly, cur = y[y.length - 1], prev = y[y.length - 2];
    const top = [...stats.trap_by_dept].sort((a, b) => b.cases - a.cases)[0];
    const latest = records.map(r => r.date).filter(Boolean).sort().pop();
    const items = [
      [IN.format(t.cases), "Trap cases, 2026 to " + stats.as_of, `${IN.format(prev.trap)} in all of ${prev.year}`],
      [IN.format(t.accused), "Accused in trap cases", ""],
      [rupees(t.amount), "Bribe amount in trap cases", "avg " + rupees(t.amount / t.cases) + " per case"],
      [IN.format(cur.total), "All ACB cases, 2026 YTD", `trap ${IN.format(cur.trap)} · assets ${cur.da} · other ${cur.other}`],
      [top.dept.split(" / ")[0], "Most trap cases: department", `${top.cases} cases (${Math.round(100 * top.cases / t.cases)}%)`],
      [latest ? new Date(latest + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "–", "Latest item on ACB site", "FIR / press release"],
    ];
    const box = $("kpis");
    items.forEach(([v, l, d]) => box.append(el("div", { className: "kpi" },
      el("div", { className: "v", textContent: v }),
      el("div", { className: "l", textContent: l }),
      el("div", { className: "d muted", textContent: d }))));
  }

  // ---------- yearly ----------
  function yearly() {
    const y = stats.yearly;
    make("yearly", {
      type: "bar",
      data: {
        labels: y.map(r => r.year + (r.partial ? "*" : "")),
        datasets: [
          { label: "Trap (सापळा)", data: y.map(r => r.trap), backgroundColor: css("--c1") },
          { label: "Disproportionate assets (अपसंपदा)", data: y.map(r => r.da), backgroundColor: css("--c2") },
          { label: "Other corruption (अन्य)", data: y.map(r => r.other), backgroundColor: css("--c3") },
        ],
      },
      options: baseOpts({
        scales: {
          x: { stacked: true, grid: { display: false }, title: { display: true, text: "* 2026 = 1 Jan to " + stats.as_of } },
          y: { stacked: true, grid: { color: css("--grid") }, beginAtZero: true },
        },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12 } },
          tooltip: { callbacks: { footer: items => "Total: " + IN.format(items.reduce((s, i) => s + i.parsed.y, 0)) } },
        },
      }),
    });
  }

  // ---------- regions ----------
  function regions() {
    const r = [...stats.regions].sort((a, b) => b.trap_cases - a.trap_cases);
    make("regions", {
      type: "bar",
      data: {
        labels: r.map(x => x.region),
        datasets: [
          { label: "Trap cases", data: r.map(x => x.trap_cases), backgroundColor: css("--c1") },
          { label: "Accused in traps", data: r.map(x => x.trap_accused), backgroundColor: css("--c2") },
          { label: "All other cases (assets + other)", data: r.map(x => x.da_cases + x.other_cases), backgroundColor: css("--c3") },
        ],
      },
      options: baseOpts({ indexAxis: "y", scales: {
        x: { grid: { color: css("--grid") }, beginAtZero: true }, y: { grid: { display: false } } } }),
    });
  }

  // ---------- departments ----------
  function depts() {
    const metric = $("deptMetric").value, n = +$("deptN").value;
    const val = d => metric === "avg" ? (d.cases ? d.amount / d.cases : 0) : d[metric];
    const rows = stats.trap_by_dept.filter(d => d.cases > 0).sort((a, b) => val(b) - val(a)).slice(0, n);
    const money = metric === "amount" || metric === "avg";
    make("depts", {
      type: "bar",
      data: { labels: rows.map(d => d.dept), datasets: [{
        label: $("deptMetric").selectedOptions[0].text, data: rows.map(val), backgroundColor: css("--c1") }] },
      options: baseOpts({
        indexAxis: "y",
        plugins: { legend: { display: false }, tooltip: { callbacks: {
          label: c => money ? rupees(c.parsed.x) : IN.format(c.parsed.x),
          afterLabel: c => { const d = rows[c.dataIndex]; return `${d.cases} cases · ${d.accused} accused · ${rupees(d.amount)}`; },
        } } },
        scales: { x: { grid: { color: css("--grid") }, beginAtZero: true,
          ticks: { callback: v => money ? rupees(v) : IN.format(v) } }, y: { grid: { display: false } } },
      }),
    });
    const cls = [["c1", "Class 1", "--c1"], ["c2", "Class 2", "--c2"], ["c3", "Class 3", "--c3"],
      ["c4", "Class 4", "--c4"], ["other", "Other public servants", "--c5"], ["private", "Private persons", "--c6"]];
    const byCases = stats.trap_by_dept.filter(d => d.cases > 0).sort((a, b) => b.cases - a.cases).slice(0, n);
    make("classes", {
      type: "bar",
      data: { labels: byCases.map(d => d.dept), datasets: cls.map(([k, l, c]) => ({
        label: l, data: byCases.map(d => d[k]), backgroundColor: css(c) })) },
      options: baseOpts({ indexAxis: "y", scales: {
        x: { stacked: true, grid: { color: css("--grid") }, beginAtZero: true },
        y: { stacked: true, grid: { display: false } } } }),
    });
  }

  // ---------- website postings ----------
  function monthKey(d) { return d.slice(0, 7); }
  function postings() {
    const dated = records.filter(r => r.date);
    // the site launched in May 2018; the handful of earlier dates are legacy/typo entries
    const months = {};
    dated.filter(r => r.date >= "2018-01-01").forEach(r => { const m = monthKey(r.date); (months[m] ||= { fir: 0, press_release: 0 })[r.kind]++; });
    const keys = Object.keys(months).sort(), all = [];
    let [y, m] = keys[0].split("-").map(Number); const [ey, em] = keys[keys.length - 1].split("-").map(Number);
    while (y < ey || (y === ey && m <= em)) { all.push(`${y}-${String(m).padStart(2, "0")}`); if (++m > 12) { m = 1; y++; } }
    make("monthly", {
      type: "line",
      data: { labels: all, datasets: [
        { label: "FIRs", data: all.map(k => months[k]?.fir || 0), borderColor: css("--c1"), backgroundColor: css("--c1"), pointRadius: 0, tension: .25 },
        { label: "Press releases", data: all.map(k => months[k]?.press_release || 0), borderColor: css("--c2"), backgroundColor: css("--c2"), pointRadius: 0, tension: .25 },
      ] },
      options: baseOpts({ scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } },
        y: { grid: { color: css("--grid") }, beginAtZero: true } },
        interaction: { mode: "index", intersect: false } }),
    });

    const years = stats.yearly.filter(r => r.year >= 2019);
    const by = (kind, yr) => dated.filter(r => r.kind === kind && r.date.startsWith(String(yr))).length;
    make("coverage", {
      type: "bar",
      data: { labels: years.map(r => r.year + (r.partial ? "*" : "")), datasets: [
        { label: "Official trap cases", data: years.map(r => r.trap), backgroundColor: css("--c6") },
        { label: "FIRs on website", data: years.map(r => by("fir", r.year)), backgroundColor: css("--c1") },
        { label: "Press releases on website", data: years.map(r => by("press_release", r.year)), backgroundColor: css("--c2") },
      ] },
      options: baseOpts({ scales: { x: { grid: { display: false } }, y: { grid: { color: css("--grid") }, beginAtZero: true } } }),
    });
  }

  // ---------- explorer ----------
  const PAGE = 25;
  let filtered = [], page = 0;
  function applyFilters() {
    const q = $("q").value.trim().toLowerCase(), k = $("fKind").value, yr = $("fYear").value, rg = $("fRegion").value;
    filtered = records.filter(r =>
      (!k || r.kind === k) && (!yr || (r.date || "").startsWith(yr)) && (!rg || r.region === rg) &&
      (!q || r.title.toLowerCase().includes(q)));
    page = 0; render();
  }
  function render() {
    const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
    page = Math.min(page, pages - 1);
    $("count").textContent = `${IN.format(filtered.length)} of ${IN.format(records.length)} items`;
    const body = $("rows"); body.replaceChildren();
    filtered.slice(page * PAGE, page * PAGE + PAGE).forEach(r => {
      const a = el("a", { href: r.pdf, target: "_blank", rel: "noopener", textContent: "Open" });
      body.append(el("tr", {},
        el("td", { className: "nw", textContent: r.date || "—" }),
        el("td", {}, el("span", { className: "tag", textContent: r.kind === "fir" ? "FIR" : "Press" })),
        el("td", { textContent: r.title }),
        el("td", { className: "nw", textContent: r.cr_no ? `${r.cr_no}/${r.cr_year}` : "" }),
        el("td", { textContent: r.region || "" }),
        el("td", {}, a)));
    });
    $("page").textContent = `Page ${page + 1} of ${pages}`;
    $("prev").disabled = page === 0; $("next").disabled = page >= pages - 1;
  }
  function explorer() {
    const yrs = [...new Set(records.map(r => (r.date || "").slice(0, 4)).filter(Boolean))].sort().reverse();
    yrs.forEach(y => $("fYear").append(el("option", { value: y, textContent: y })));
    [...new Set(records.map(r => r.region).filter(Boolean))].sort()
      .forEach(g => $("fRegion").append(el("option", { value: g, textContent: g })));
    let t; $("q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(applyFilters, 150); });
    ["fKind", "fYear", "fRegion"].forEach(i => $(i).addEventListener("change", applyFilters));
    $("prev").onclick = () => { page--; render(); };
    $("next").onclick = () => { page++; render(); };
    applyFilters();
  }

  function notes() {
    stats.notes.forEach(n => $("notesList").append(el("li", { textContent: "Source inconsistency: " + n })));
    $("foot").textContent = `Index data fetched ${window.__generated || ""}. Stats as of ${stats.as_of}.`;
  }

  function drawCharts() { charts.splice(0).forEach(c => c.destroy()); yearly(); regions(); depts(); postings(); }

  async function main() {
    try {
      const [s, r] = await Promise.all([
        fetch("data/stats.json").then(x => x.json()), fetch("data/records.json").then(x => x.json())]);
      stats = s; records = r.records; window.__generated = r.generated_at.slice(0, 10);
    } catch (e) {
      document.querySelector("main").prepend(el("p", { textContent: "Could not load data: " + e.message }));
      return;
    }
    kpis(); drawCharts(); explorer(); notes();
    $("deptMetric").addEventListener("change", depts);
    $("deptN").addEventListener("change", depts);
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", drawCharts);
  }
  main();
})();
