(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const CUR = window.CURRENCY || "";
  const els = { start: $("start"), end: $("end"), region: $("region"), category: $("category") };
  let maxDate = null, minDate = null, timer = null, requestId = 0;

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (v) => CUR + Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
  const num = (v) => Number(v).toLocaleString("en-IN");
  const fmtDate = (iso) => new Date(iso + "T00:00:00Z").toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });

  function addDays(iso, n) {
    const d = new Date(iso + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }

  function query() {
    const p = new URLSearchParams();
    for (const [k, el] of Object.entries(els)) if (el.value) p.set(k, el.value);
    return p.toString();
  }

  async function getJSON(url) {
    const r = await fetch(url);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || `Request failed (${r.status})`);
    return body;
  }

  function badge(pct) {
    if (pct === null || pct === undefined) return '<span class="badge na">n/a</span>';
    const cls = pct >= 0 ? "up" : "down";
    return `<span class="badge ${cls}">${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct).toFixed(1)}%</span>`;
  }
  const growthCell = (pct) => pct === null || pct === undefined ? '<td class="num">n/a</td>'
    : `<td class="num ${pct >= 0 ? "pos" : "neg"}">${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%</td>`;

  function renderKpis(d) {
    const c = d.current, g = d.growth_pct;
    const cards = [
      { label: "Net sales", value: money(c.net_sales), growth: g.net_sales, primary: true, sub: "after discounts & returns" },
      { label: "Gross sales", value: money(c.gross_sales), growth: g.gross_sales, primary: true, sub: "before discounts & returns" },
      { label: "Orders", value: num(c.orders), growth: g.orders, primary: true, sub: `${num(c.units_sold)} units sold` },
      { label: "Avg order value", value: money(c.aov), growth: g.aov, primary: true, sub: "net sales ÷ orders" },
      { label: "Discounts", value: money(c.discounts), sub: `${c.discount_rate.toFixed(1)}% of gross sales` },
      { label: "Returns", value: money(c.returns), sub: `${c.return_rate.toFixed(1)}% of gross sales` },
      { label: "Cancellation rate", value: c.cancellation_rate.toFixed(1) + "%", sub: `${num(c.cancelled_orders)} cancelled orders (excluded)` },
      { label: "Previous period net", value: money(d.previous.net_sales), sub: `${fmtDate(d.previous_period.start)} – ${fmtDate(d.previous_period.end)}` },
    ];
    $("kpis").innerHTML = cards.map((k) => `
      <div class="kpi ${k.primary ? "primary" : ""}">
        <div class="label">${esc(k.label)}</div>
        <div class="value">${esc(k.value)}</div>
        <div class="sub">${"growth" in k ? badge(k.growth) + " vs previous period<br>" : ""}${esc(k.sub)}</div>
      </div>`).join("");
    $("periodInfo").textContent = `Showing ${fmtDate(d.period.start)} – ${fmtDate(d.period.end)} · compared with ${fmtDate(d.previous_period.start)} – ${fmtDate(d.previous_period.end)}`;
  }

  function table(id, head, rows) {
    const t = $(id);
    if (!rows.length) { t.innerHTML = '<tr><td class="muted">No data for the selected filters</td></tr>'; return; }
    t.innerHTML = "<thead><tr>" + head.map(([h, n]) => `<th class="${n ? "num" : ""}">${h}</th>`).join("") + "</tr></thead><tbody>" + rows.join("") + "</tbody>";
  }

  function renderTables(cat, reg, prod) {
    table("t-category", [["Category"], ["Net", 1], ["Share", 1], ["Growth", 1]],
      cat.map((r) => `<tr><td>${esc(r.category)}</td><td class="num">${money(r.net_sales)}</td><td class="num">${r.share_pct.toFixed(1)}%</td>${growthCell(r.growth_pct)}</tr>`));
    table("t-region", [["Region"], ["Net", 1], ["Share", 1], ["Growth", 1]],
      reg.map((r) => `<tr><td>${esc(r.region)}</td><td class="num">${money(r.net_sales)}</td><td class="num">${r.share_pct.toFixed(1)}%</td>${growthCell(r.growth_pct)}</tr>`));
    table("t-products", [["Product"], ["Net", 1], ["Units", 1]],
      prod.map((r) => `<tr><td>${esc(r.product_name)}<div class="muted" style="font-size:12px">${esc(r.category)}</div></td><td class="num">${money(r.net_sales)}</td><td class="num">${num(r.units_sold)}</td></tr>`));
  }

  function showError(msg) { const a = $("alert"); a.textContent = msg; a.hidden = !msg; }

  async function refresh() {
    const id = ++requestId, qs = query();
    showError("");
    $("download").href = "/api/report.csv?" + qs;
    window.CHARTS.forEach((name) => {
      const img = $("c-" + name);
      img.classList.add("loading");
      img.onload = img.onerror = () => img.classList.remove("loading");
      img.src = `/charts/${name}.png?${qs}`;
    });
    try {
      const [k, cat, reg, prod] = await Promise.all([
        getJSON("/api/kpis?" + qs), getJSON("/api/revenue/category?" + qs),
        getJSON("/api/revenue/region?" + qs), getJSON("/api/products/top?" + qs),
      ]);
      if (id !== requestId) return;   // a newer request superseded this one
      renderKpis(k); renderTables(cat, reg, prod);
    } catch (e) { if (id === requestId) showError(e.message); }
  }

  const debounced = () => { clearTimeout(timer); timer = setTimeout(refresh, 250); };

  function setPreset(days) {
    document.querySelectorAll(".presets button").forEach((b) => b.classList.toggle("on", Number(b.dataset.days) === days));
    els.end.value = maxDate;
    els.start.value = days === 0 ? minDate : addDays(maxDate, -(days - 1));
    if (els.start.value < minDate) els.start.value = minDate;
  }

  async function init() {
    try {
      const f = await getJSON("/api/filters");
      minDate = f.min_date; maxDate = f.max_date;
      if (!minDate) { showError("No data yet. Run: python manage.py seed"); return; }
      f.regions.forEach((r) => els.region.add(new Option(r, r)));
      f.categories.forEach((c) => els.category.add(new Option(c, c)));
      els.start.min = els.end.min = minDate; els.start.max = els.end.max = maxDate;
      setPreset(365);
      document.querySelectorAll(".presets button").forEach((b) => b.addEventListener("click", () => { setPreset(Number(b.dataset.days)); refresh(); }));
      Object.values(els).forEach((el) => el.addEventListener("change", () => {
        if (el === els.start || el === els.end) document.querySelectorAll(".presets button").forEach((b) => b.classList.remove("on"));
        if (els.start.value && els.end.value && els.start.value > els.end.value) { showError("'From' date must not be after 'To' date."); return; }
        debounced();
      }));
      refresh();
    } catch (e) { showError(e.message); }
  }
  init();
})();
