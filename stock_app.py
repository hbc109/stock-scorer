#!/usr/bin/env python3
"""Stock Scorer Web UI — Flask app wrapping stock_scorer.py"""

import threading
import webbrowser
from flask import Flask, request, jsonify
from stock_scorer import assess_stock_data

app = Flask(__name__)

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Scorer</title>
<style>
  :root {
    --bg: #0f1117;
    --card: #1a1d2e;
    --border: #2a2d3e;
    --text: #e1e4ed;
    --muted: #8b8fa3;
    --accent: #6c63ff;
    --green: #22c55e;
    --yellow: #eab308;
    --orange: #f97316;
    --red: #ef4444;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg); color: var(--text);
    min-height: 100vh;
  }
  .container { max-width: 1200px; margin: 0 auto; padding: 20px; }

  /* Header */
  header { text-align: center; padding: 40px 0 30px; }
  header h1 { font-size: 2.2rem; font-weight: 700; letter-spacing: -0.5px; }
  header h1 span { color: var(--accent); }
  header p { color: var(--muted); margin-top: 8px; font-size: 0.95rem; }

  /* Search */
  .search-box {
    display: flex; gap: 12px; max-width: 600px; margin: 0 auto 40px;
  }
  .search-box input {
    flex: 1; padding: 14px 18px; border-radius: 12px;
    border: 1px solid var(--border); background: var(--card);
    color: var(--text); font-size: 1rem; outline: none;
    transition: border-color 0.2s;
  }
  .search-box input:focus { border-color: var(--accent); }
  .search-box input::placeholder { color: var(--muted); }
  .search-box button {
    padding: 14px 28px; border-radius: 12px; border: none;
    background: var(--accent); color: #fff; font-size: 1rem;
    font-weight: 600; cursor: pointer; transition: opacity 0.2s;
    white-space: nowrap;
  }
  .search-box button:hover { opacity: 0.85; }
  .search-box button:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Loading */
  .loader { text-align: center; padding: 60px 0; display: none; }
  .loader.active { display: block; }
  .spinner {
    width: 48px; height: 48px; border: 4px solid var(--border);
    border-top-color: var(--accent); border-radius: 50%;
    animation: spin 0.8s linear infinite; margin: 0 auto 16px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loader p { color: var(--muted); }

  /* Error */
  .error { text-align: center; color: var(--red); padding: 20px; display: none; }

  /* Cards grid */
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 24px; }

  /* Stock card */
  .stock-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 16px; padding: 28px; transition: transform 0.15s;
  }
  .stock-card:hover { transform: translateY(-2px); }
  .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
  .card-header .info h2 { font-size: 1.3rem; font-weight: 700; }
  .card-header .info .ticker { color: var(--accent); font-weight: 600; }
  .card-header .info .meta { color: var(--muted); font-size: 0.82rem; margin-top: 4px; }
  .card-header .price-block { text-align: right; }
  .card-header .price { font-size: 1.5rem; font-weight: 700; }
  .card-header .mcap { color: var(--muted); font-size: 0.82rem; }

  /* Gauge */
  .gauge-row { display: flex; align-items: center; gap: 24px; margin-bottom: 24px; }
  .gauge {
    position: relative; width: 100px; height: 100px; flex-shrink: 0;
  }
  .gauge svg { width: 100px; height: 100px; transform: rotate(-90deg); }
  .gauge circle {
    fill: none; stroke-width: 8; stroke-linecap: round;
  }
  .gauge .bg { stroke: var(--border); }
  .gauge .fg { transition: stroke-dashoffset 0.8s ease; }
  .gauge .score-text {
    position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
    font-size: 1.5rem; font-weight: 800;
  }
  .rating-badge {
    display: inline-block; padding: 6px 16px; border-radius: 8px;
    font-weight: 700; font-size: 0.95rem; letter-spacing: 0.5px;
  }

  /* Category bars */
  .category-bars { margin-bottom: 16px; }
  .cat-bar { margin-bottom: 12px; }
  .cat-bar .cat-label {
    display: flex; justify-content: space-between; font-size: 0.85rem;
    margin-bottom: 4px;
  }
  .cat-bar .cat-label span:first-child { font-weight: 600; }
  .cat-bar .cat-label span:last-child { color: var(--muted); }
  .bar-track {
    height: 8px; background: var(--border); border-radius: 4px; overflow: hidden;
  }
  .bar-fill {
    height: 100%; border-radius: 4px; transition: width 0.6s ease;
  }

  /* Details accordion */
  .details-section { border-top: 1px solid var(--border); padding-top: 12px; }
  .details-toggle {
    background: none; border: none; color: var(--accent); cursor: pointer;
    font-size: 0.85rem; padding: 4px 0; font-weight: 600;
  }
  .details-content { display: none; margin-top: 8px; }
  .details-content.open { display: block; }
  .detail-cat { margin-bottom: 12px; }
  .detail-cat h4 { font-size: 0.82rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
  .detail-row {
    display: flex; justify-content: space-between; font-size: 0.82rem;
    padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .detail-row .pts { color: var(--accent); font-weight: 600; min-width: 50px; text-align: right; }

  /* Narrative badge */
  .narrative-badge {
    display: inline-block; padding: 4px 12px; border-radius: 6px;
    font-size: 0.8rem; font-weight: 700; margin-top: 8px;
  }

  /* Comparison table */
  .comparison { margin-top: 40px; display: none; }
  .comparison.active { display: block; }
  .comparison h2 { font-size: 1.3rem; margin-bottom: 16px; font-weight: 700; }
  .comp-table {
    width: 100%; border-collapse: collapse; background: var(--card);
    border-radius: 12px; overflow: hidden; border: 1px solid var(--border);
  }
  .comp-table th, .comp-table td { padding: 14px 16px; text-align: left; }
  .comp-table th {
    background: rgba(108,99,255,0.1); font-size: 0.82rem;
    text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted);
    cursor: pointer; user-select: none;
  }
  .comp-table th:hover { color: var(--text); }
  .comp-table th .sort-arrow { margin-left: 4px; font-size: 0.7rem; }
  .comp-table td { border-top: 1px solid var(--border); font-size: 0.9rem; }
  .comp-table tr:hover td { background: rgba(255,255,255,0.02); }

  /* Warning card */
  .warning-card {
    background: var(--card); border: 1px solid #f9731644;
    border-radius: 16px; padding: 28px;
  }
  .warning-card .card-header { margin-bottom: 16px; }
  .warning-banner {
    background: #f9731615; border: 1px solid #f9731633; border-radius: 10px;
    padding: 16px 20px; display: flex; align-items: center; gap: 12px;
  }
  .warning-banner .warn-icon { font-size: 1.5rem; flex-shrink: 0; }
  .warning-banner .warn-text { color: #f97316; font-weight: 500; font-size: 0.95rem; }
  .warning-banner .warn-type {
    display: inline-block; background: #f9731622; color: #f97316;
    padding: 2px 10px; border-radius: 5px; font-weight: 700; font-size: 0.82rem;
  }

  /* Responsive */
  @media (max-width: 640px) {
    .cards { grid-template-columns: 1fr; }
    .search-box { flex-direction: column; }
    .search-box button { width: 100%; }
    .gauge-row { flex-direction: column; text-align: center; }
    .comp-table { font-size: 0.8rem; }
    .comp-table th, .comp-table td { padding: 10px 8px; }
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Stock <span>Scorer</span></h1>
    <p>Fundamental analysis with growth, relative strength, market popularity &amp; narrative scoring</p>
  </header>

  <div class="search-box">
    <input type="text" id="tickers" placeholder="Enter tickers (e.g. AAPL NVDA MSFT)" autofocus>
    <button id="analyzeBtn" onclick="analyze()">Analyze</button>
  </div>

  <div class="loader" id="loader">
    <div class="spinner"></div>
    <p>Fetching data from Yahoo Finance...</p>
  </div>

  <div class="error" id="error"></div>

  <div class="cards" id="cards"></div>

  <div class="comparison" id="comparison">
    <h2>Comparison</h2>
    <table class="comp-table" id="compTable">
      <thead><tr>
        <th data-key="symbol">Ticker <span class="sort-arrow"></span></th>
        <th data-key="overall">Overall <span class="sort-arrow"></span></th>
        <th data-key="growth">Growth <span class="sort-arrow"></span></th>
        <th data-key="relative">Relative <span class="sort-arrow"></span></th>
        <th data-key="market">Market <span class="sort-arrow"></span></th>
        <th data-key="narrative">Narrative <span class="sort-arrow"></span></th>
        <th data-key="rating">Rating <span class="sort-arrow"></span></th>
      </tr></thead>
      <tbody id="compBody"></tbody>
    </table>
  </div>
</div>

<script>
function scoreColor(score) {
  if (score >= 75) return '#22c55e';
  if (score >= 60) return '#6c63ff';
  if (score >= 40) return '#eab308';
  if (score >= 25) return '#f97316';
  return '#ef4444';
}

function ratingColor(rating) {
  const m = {'STRONG BUY':'#22c55e','BUY':'#6c63ff','HOLD':'#eab308','UNDERPERFORM':'#f97316','SELL':'#ef4444'};
  return m[rating] || '#8b8fa3';
}

function narrativeColor(stage) {
  const m = {'Early':'#22c55e','Momentum':'#6c63ff','Peak Hype':'#f97316','Declining':'#ef4444','Under the Radar':'#8b8fa3','Neutral':'#eab308'};
  return m[stage] || '#8b8fa3';
}

function formatMcap(n) {
  if (!n) return 'N/A';
  if (n >= 1e12) return '$' + (n/1e12).toFixed(1) + 'T';
  if (n >= 1e9) return '$' + (n/1e9).toFixed(1) + 'B';
  if (n >= 1e6) return '$' + (n/1e6).toFixed(0) + 'M';
  return '$' + n.toLocaleString();
}

function gaugeHTML(score) {
  const r = 42, circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = scoreColor(score);
  return `<div class="gauge">
    <svg viewBox="0 0 100 100">
      <circle class="bg" cx="50" cy="50" r="${r}"/>
      <circle class="fg" cx="50" cy="50" r="${r}"
        stroke="${color}" stroke-dasharray="${circ}" stroke-dashoffset="${offset}"/>
    </svg>
    <div class="score-text" style="color:${color}">${score}</div>
  </div>`;
}

function barHTML(label, score) {
  const color = scoreColor(score);
  return `<div class="cat-bar">
    <div class="cat-label"><span>${label}</span><span>${score}/100</span></div>
    <div class="bar-track"><div class="bar-fill" style="width:${score}%;background:${color}"></div></div>
  </div>`;
}

function detailsHTML(details) {
  const cats = [
    ['Growth Potential', 'growth'],
    ['Relative Strength', 'relative'],
    ['Market Strength', 'market'],
    ['Narrative & Sentiment', 'narrative']
  ];
  let html = '';
  for (const [title, key] of cats) {
    const items = details[key] || [];
    html += `<div class="detail-cat"><h4>${title}</h4>`;
    for (const d of items) {
      const pts = typeof d.points === 'number' ? d.points + 'pts' : d.points;
      html += `<div class="detail-row"><span>${d.metric}: ${d.value}</span><span class="pts">${pts}</span></div>`;
    }
    html += '</div>';
  }
  return html;
}

function getNarrativeStage(details) {
  const items = details.narrative || [];
  const stage = items.find(d => d.metric === 'Narrative Stage');
  return stage ? stage.value : 'N/A';
}

function warningCardHTML(stock) {
  return `<div class="warning-card">
    <div class="card-header">
      <div class="info">
        <h2>${stock.name}</h2>
        <div class="ticker">${stock.symbol}</div>
      </div>
      <div class="price-block">
        <div class="price">$${stock.price.toFixed(2)}</div>
      </div>
    </div>
    <div class="warning-banner">
      <div class="warn-icon">&#9888;</div>
      <div>
        <span class="warn-type">${stock.quoteType || 'ETF'}</span>
        <div class="warn-text">${stock.warning}</div>
      </div>
    </div>
  </div>`;
}

function cardHTML(stock) {
  if (stock.warning) return warningCardHTML(stock);
  const s = stock.scores;
  const rc = ratingColor(stock.rating);
  const stage = getNarrativeStage(stock.details);
  const nc = narrativeColor(stage);
  const id = 'det-' + stock.symbol;
  return `<div class="stock-card">
    <div class="card-header">
      <div class="info">
        <h2>${stock.name}</h2>
        <div class="ticker">${stock.symbol}</div>
        <div class="meta">${stock.sector} &bull; ${stock.industry}</div>
      </div>
      <div class="price-block">
        <div class="price">$${stock.price.toFixed(2)}</div>
        <div class="mcap">${formatMcap(stock.marketCap)}</div>
      </div>
    </div>
    <div class="gauge-row">
      ${gaugeHTML(s.overall)}
      <div>
        <div class="rating-badge" style="background:${rc}22;color:${rc};border:1px solid ${rc}44">${stock.rating}</div>
        <div class="narrative-badge" style="background:${nc}22;color:${nc};border:1px solid ${nc}44">${stage}</div>
      </div>
    </div>
    <div class="category-bars">
      ${barHTML('Growth', s.growth)}
      ${barHTML('Relative Strength', s.relative)}
      ${barHTML('Market Strength', s.market)}
      ${barHTML('Narrative', s.narrative)}
    </div>
    <div class="details-section">
      <button class="details-toggle" onclick="toggleDetails('${id}')">Show details</button>
      <div class="details-content" id="${id}">${detailsHTML(stock.details)}</div>
    </div>
  </div>`;
}

function toggleDetails(id) {
  const el = document.getElementById(id);
  const btn = el.previousElementSibling;
  el.classList.toggle('open');
  btn.textContent = el.classList.contains('open') ? 'Hide details' : 'Show details';
}

let allResults = [];

function renderComparison(results) {
  const comp = document.getElementById('comparison');
  const body = document.getElementById('compBody');
  if (results.length < 2) { comp.classList.remove('active'); return; }
  comp.classList.add('active');
  fillCompTable(results);
}

function fillCompTable(results) {
  const body = document.getElementById('compBody');
  body.innerHTML = results.map(r => {
    const rc = ratingColor(r.rating);
    return `<tr>
      <td><strong>${r.symbol}</strong></td>
      <td style="color:${scoreColor(r.scores.overall)};font-weight:700">${r.scores.overall}</td>
      <td>${r.scores.growth}</td>
      <td>${r.scores.relative}</td>
      <td>${r.scores.market}</td>
      <td>${r.scores.narrative}</td>
      <td><span style="color:${rc};font-weight:600">${r.rating}</span></td>
    </tr>`;
  }).join('');
}

// Sortable table
let sortKey = 'overall', sortAsc = false;
document.querySelectorAll('.comp-table th').forEach(th => {
  th.addEventListener('click', () => {
    const key = th.dataset.key;
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = false; }
    const sorted = [...allResults].sort((a, b) => {
      let va = key === 'symbol' ? a.symbol : key === 'rating' ? a.rating : a.scores[key];
      let vb = key === 'symbol' ? b.symbol : key === 'rating' ? b.rating : b.scores[key];
      if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortAsc ? va - vb : vb - va;
    });
    fillCompTable(sorted);
  });
});

async function analyze() {
  const input = document.getElementById('tickers').value.trim();
  if (!input) return;
  const symbols = input.toUpperCase().split(/[\s,]+/).filter(Boolean);

  const btn = document.getElementById('analyzeBtn');
  const loader = document.getElementById('loader');
  const error = document.getElementById('error');
  const cards = document.getElementById('cards');

  btn.disabled = true;
  loader.classList.add('active');
  error.style.display = 'none';
  cards.innerHTML = '';
  document.getElementById('comparison').classList.remove('active');

  try {
    const resp = await fetch('/api/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({symbols})
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    allResults = data.results.filter(r => !r.warning);
    const allCards = data.results;
    cards.innerHTML = allCards.map(cardHTML).join('');
    renderComparison(allResults);
  } catch (e) {
    error.textContent = 'Error: ' + e.message;
    error.style.display = 'block';
  } finally {
    loader.classList.remove('active');
    btn.disabled = false;
  }
}

// Enter key to submit
document.getElementById('tickers').addEventListener('keydown', e => {
  if (e.key === 'Enter') analyze();
});
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML_PAGE


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json()
    symbols = data.get("symbols", [])
    if not symbols:
        return jsonify({"error": "No symbols provided"}), 400

    results = []
    errors = []
    for sym in symbols[:10]:  # limit to 10 tickers
        try:
            result = assess_stock_data(sym)
            results.append(result)
        except Exception as e:
            errors.append(f"{sym}: {str(e)}")

    return jsonify({"results": results, "errors": errors})


if __name__ == "__main__":
    print("Starting Stock Scorer Web UI at http://localhost:5000")
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(debug=False, host="0.0.0.0", port=5000)
