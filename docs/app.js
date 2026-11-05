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

  let stats, records, A;
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

    const cov = A.coverage;
    make("coverage", {
      type: "bar",
      data: { labels: cov.map(r => r.year + (r.partial ? "*" : "")), datasets: [
        { label: "Official cases (all types)", data: cov.map(r => r.official_all), backgroundColor: css("--c6") },
        { label: "Raw postings (FIR + press)", data: cov.map(r => r.raw_postings), backgroundColor: css("--c2") },
        { label: "Unique cases (estimate)", data: cov.map(r => r.unique_cases), backgroundColor: css("--c1") },
      ] },
      options: baseOpts({ scales: { x: { grid: { display: false } }, y: { grid: { color: css("--grid") }, beginAtZero: true } },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } },
          tooltip: { callbacks: { afterBody: it => { const r = cov[it[0].dataIndex]; return `Unique / official: ${r.coverage_pct}%`; } } } } }),
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


  // ---------- advanced analytics ----------
  const chip = (box, label, value) => $(box).append(el("span", { className: "chip" }, label + " ", el("b", { textContent: value })));
  const heat = (host, rowLabels, colLabels, matrix, fmt, color) => {
    const flat = matrix.flat(), max = Math.max(...flat, 1);
    const t = el("table", { className: "heat" });
    t.append(el("thead", {}, el("tr", {}, el("th"), ...colLabels.map(c => el("th", { textContent: c })))));
    const tb = el("tbody");
    matrix.forEach((row, i) => tb.append(el("tr", {}, el("th", { className: "rl", textContent: rowLabels[i] }),
      ...row.map(v => { const td = el("td", { textContent: v ? fmt(v) : "–" });
        td.style.background = `color-mix(in srgb, ${color} ${Math.round(8 + 80 * v / max)}%, transparent)`; return td; }))));
    t.append(tb); $(host).replaceChildren(t);
  };
  const fillTable = (id, rows) => {
    const tb = document.querySelector(`#${id} tbody`); tb.replaceChildren();
    rows.forEach(r => tb.append(el("tr", {}, ...r.map((v, i) => el("td", { className: i ? "num" : "", textContent: v })))));
  };

  let advDone = false;
  function chartsAdv() { if (!A) return; if (!advDone) { document.querySelectorAll("#insightList,#trendChips,#concChips").forEach(n => n.replaceChildren()); } advanced(); advDone = true; }
  function advanced() {
    $("insightList").replaceChildren(); $("trendChips").replaceChildren(); $("concChips").replaceChildren();
    A.insights.forEach(t => $("insightList").append(el("li", { textContent: t })));
    const T = A.trend, P = A.projection, y = stats.yearly, labels = y.map(r => r.year + (r.partial ? "*" : ""));

    chip("trendChips", "Trend:", `${T.slope_per_year > 0 ? "+" : "−"}${Math.abs(T.slope_per_year)} cases/yr (R² ${T.r2})`);
    chip("trendChips", `CAGR ${T.from_year}–${T.to_year}:`, `${T.cagr_pct}%/yr`);
    chip("trendChips", `vs ${T.peak_year} peak:`, `${T.change_vs_peak_pct}%`);
    if (P.seasonal) chip("trendChips", "2026 projection:", `${IN.format(P.seasonal_low)}–${IN.format(P.seasonal_high)}`);
    make("trend", {
      data: { labels, datasets: [
        { type: "bar", label: "Trap cases", data: y.map(r => r.trap), backgroundColor: css("--c1"), order: 2 },
        { type: "bar", label: "2026 projected range", grouped: false, order: 3,
          data: y.map((r, i) => r.partial && P.seasonal ? [P.seasonal_low, P.seasonal_high] : null),
          backgroundColor: css("--c2") + "99", borderColor: css("--c2"), borderWidth: 1 },
        { type: "line", label: "Linear trend", data: T.fit.map(f => f.trap), borderColor: css("--c5"), borderDash: [6, 4],
          pointRadius: 0, order: 1 },
      ] },
      options: baseOpts({ scales: { x: { grid: { display: false } }, y: { grid: { color: css("--grid") }, beginAtZero: true } } }),
    });
    make("yoy", {
      type: "bar",
      data: { labels: T.yoy.map(r => r.year), datasets: [{ label: "% change", data: T.yoy.map(r => r.pct),
        backgroundColor: T.yoy.map(r => r.pct >= 0 ? css("--c5") : css("--c3")) }] },
      options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => c.parsed.y + "%" } } },
        scales: { x: { grid: { display: false } }, y: { grid: { color: css("--grid") }, ticks: { callback: v => v + "%" } } } }),
    });

    const C = A.concentration;
    chip("concChips", "Top 3 depts:", C.top3_pct + "% of cases");
    chip("concChips", "Depts for 80%:", `${C.n_for_80pct} of ${C.n_depts}`);
    chip("concChips", "HHI:", IN.format(C.hhi));
    chip("concChips", "Avg bribe:", rupees(C.avg_bribe_overall));
    make("pareto", {
      data: { labels: C.pareto.map(p => p.dept), datasets: [
        { type: "bar", label: "Cases", data: C.pareto.map(p => p.cases), backgroundColor: css("--c1"), yAxisID: "y" },
        { type: "line", label: "Cumulative %", data: C.pareto.map(p => p.cum_pct), borderColor: css("--c2"), backgroundColor: css("--c2"),
          pointRadius: 2, yAxisID: "y2" },
      ] },
      options: baseOpts({ scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 70, minRotation: 50, autoSkip: false, font: { size: 10 } } },
        y: { grid: { color: css("--grid") }, beginAtZero: true, title: { display: true, text: "Cases" } },
        y2: { position: "right", min: 0, max: 100, grid: { display: false }, ticks: { callback: v => v + "%" } } } }),
    });
    const big = C.depts.filter(d => d.cases >= 5);
    const bubbleLabels = { id: "bubbleLabels", afterDatasetsDraw(chart) {
      const { ctx } = chart; ctx.save(); ctx.fillStyle = css("--ink"); ctx.font = "11px sans-serif"; ctx.textBaseline = "middle";
      chart.getDatasetMeta(0).data.forEach((pt, i) => { const d = big[i]; if (d.cases < 12) return;
        ctx.fillText(d.dept.split(/[ /(]/)[0], pt.x + pt.options.radius + 4, pt.y); });
      ctx.restore(); } };
    make("bubble", {
      type: "bubble", plugins: [bubbleLabels],
      data: { datasets: [{ label: "Departments", data: big.map(d => ({ x: d.accused_per_case, y: d.avg_bribe, r: 4 + Math.sqrt(d.cases) * 1.6, d })),
        backgroundColor: css("--c1") + "aa", borderColor: css("--c1") }] },
      options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: {
        title: c => c[0].raw.d.dept,
        label: c => { const d = c.raw.d; return [`${d.cases} cases, ${d.accused} accused`, `Avg bribe ${rupees(d.avg_bribe)}`,
          `Senior ${d.senior_pct}% · private ${d.private_pct}%`]; } } } },
        scales: { x: { title: { display: true, text: "Accused per case" }, grid: { color: css("--grid") } },
          y: { title: { display: true, text: "Average bribe per case" }, grid: { color: css("--grid") }, beginAtZero: true,
            ticks: { callback: v => rupees(v) } } } }),
    });
    fillTable("deptTable", C.depts.map(d => [d.dept, d.cases, d.accused_per_case, rupees(d.avg_bribe), d.senior_pct + "%", d.private_pct + "%"]));
    fillTable("regionTable", A.regions.map(r => [r.region, r.trap_cases, r.share_pct + "%", r.accused_per_trap, r.non_trap_pct + "%"]));

    const RY = A.region_year;
    heat("regionHeat", RY.regions, RY.years, RY.share_pct, v => v.toFixed(0) + "%", css("--c1"));

    const CAL = A.calendar;
    heat("calHeat", CAL.years, CAL.months, CAL.matrix, v => v, css("--c3"));
    make("monthAvg", {
      type: "bar", data: { labels: CAL.months, datasets: [{ label: "Avg cases", data: CAL.avg_by_month, backgroundColor: css("--c3") }] },
      options: baseOpts({ plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: css("--grid") }, beginAtZero: true } } }),
    });
    const W = A.weekdays;
    make("weekday", {
      type: "bar", data: { labels: W.labels, datasets: [{ label: "% of postings", data: W.pct, backgroundColor: css("--c4") }] },
      options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => c.parsed.y + "%" } } },
        scales: { x: { grid: { display: false } }, y: { grid: { color: css("--grid") }, beginAtZero: true, ticks: { callback: v => v + "%" } } } }),
    });
    const M = A.monthly, idx = new Map(M.months.map((m, i) => [m, i]));
    make("anom", {
      data: { labels: M.months, datasets: [
        { type: "bar", label: "Cases", data: M.values, backgroundColor: css("--c1") + "66", order: 3 },
        { type: "line", label: "3-month average", data: M.ma3, borderColor: css("--c1"), pointRadius: 0, tension: .25, order: 2 },
        { type: "line", label: "Unusual month", showLine: false, order: 1, pointRadius: 6, borderColor: css("--c5"), backgroundColor: css("--c5"),
          data: M.months.map(m => { const a = M.anomalies.find(x => x.month === m); return a ? a.count : null; }) },
      ] },
      options: baseOpts({ scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } }, y: { grid: { color: css("--grid") }, beginAtZero: true } },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } }, tooltip: { callbacks: { afterLabel: c => {
          const a = M.anomalies.find(x => x.month === M.months[c.dataIndex]);
          return a ? `Unusual: ${a.direction} vs 12-mo baseline ${a.baseline}` : ""; } } } } }),
    });
  }

  function notes() {
    Object.values(A.method_notes).forEach(n => $("notesList").append(el("li", { textContent: "Method: " + n })));
    stats.notes.forEach(n => $("notesList").append(el("li", { textContent: "Source inconsistency: " + n })));
    $("foot").textContent = `Index data fetched ${window.__generated || ""}. Stats as of ${stats.as_of}.`;
  }

  function drawCharts() { charts.splice(0).forEach(c => c.destroy()); yearly(); regions(); depts(); postings(); chartsAdv(); }

  async function main() {
    try {
      const [s, r, an] = await Promise.all([
        fetch("data/stats.json").then(x => x.json()), fetch("data/records.json").then(x => x.json()),
        fetch("data/analytics.json").then(x => x.json())]);
      stats = s; A = an; records = r.records; window.__generated = r.generated_at.slice(0, 10);
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
