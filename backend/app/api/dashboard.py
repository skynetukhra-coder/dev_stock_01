"""Interactive Prophecy Trading Engine Web Dashboard."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Dashboard"])

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Prophecy Trading Platform — Strategy & Live Operator Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090d16;
      --card-bg: rgba(18, 24, 38, 0.85);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.25);
      --green: #10b981;
      --green-glow: rgba(16, 185, 129, 0.25);
      --red: #ef4444;
      --red-glow: rgba(239, 68, 68, 0.25);
      --purple: #a855f7;
      --yellow: #f59e0b;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      background-image: radial-gradient(circle at 10% 20%, rgba(56, 189, 248, 0.04) 0%, transparent 40%),
                        radial-gradient(circle at 90% 80%, rgba(168, 85, 247, 0.04) 0%, transparent 40%);
      color: var(--text);
      font-family: 'Outfit', sans-serif;
      min-height: 100vh;
      padding: 24px;
    }

    .container { max-width: 1400px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }

    /* Header */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 24px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      backdrop-filter: blur(12px);
    }
    .logo-group { display: flex; align-items: center; gap: 14px; }
    .logo-badge {
      background: linear-gradient(135deg, #0284c7, #9333ea);
      color: #fff;
      font-weight: 800;
      font-size: 1.1rem;
      padding: 8px 14px;
      border-radius: 10px;
      box-shadow: 0 0 20px rgba(56, 189, 248, 0.3);
    }
    .logo-text h1 { font-size: 1.3rem; font-weight: 700; }
    .logo-text p { font-size: 0.8rem; color: var(--text-muted); }
    .status-group { display: flex; align-items: center; gap: 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
    .live-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 10px var(--green);
      animation: pulse 1.8s infinite;
    }
    @keyframes pulse { 0% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(1.2); } 100% { opacity: 1; transform: scale(1); } }

    /* Top Stats Grid */
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 16px;
      backdrop-filter: blur(10px);
    }
    .stat-label { font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; letter-spacing: 0.5px; }
    .stat-val { font-size: 1.4rem; font-weight: 700; margin-top: 6px; font-family: 'JetBrains Mono', monospace; }

    /* Control Bar for Strategy Cases */
    .case-trigger-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .case-buttons-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
    .btn {
      padding: 12px 16px;
      border: none;
      border-radius: 10px;
      font-weight: 600;
      font-size: 0.85rem;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    .btn-case { background: rgba(56, 189, 248, 0.1); color: var(--accent); border: 1px solid rgba(56, 189, 248, 0.3); }
    .btn-case:hover { background: var(--accent); color: #000; box-shadow: 0 0 15px var(--accent-glow); transform: translateY(-1px); }
    .btn-all { background: linear-gradient(135deg, #0284c7, #9333ea); color: #fff; border: 1px solid rgba(255, 255, 255, 0.2); }
    .btn-all:hover { box-shadow: 0 0 20px rgba(147, 51, 234, 0.4); transform: translateY(-1px); }
    .btn-confirm { background: var(--green); color: #000; font-weight: 700; }
    .btn-confirm:hover { box-shadow: 0 0 15px var(--green-glow); }
    .btn-ignore { background: rgba(239, 68, 68, 0.15); color: var(--red); border: 1px solid var(--red); }
    .btn-ignore:hover { background: var(--red); color: #fff; }
    .btn-kill { background: rgba(239, 68, 68, 0.2); color: var(--red); border: 1px solid var(--red); }
    .btn-kill.active { background: var(--red); color: #fff; box-shadow: 0 0 20px var(--red); }

    /* Main Grid */
    .main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    @media (max-width: 960px) { .main-grid { grid-template-columns: 1fr; } }

    .panel {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .panel-title { font-size: 1.05rem; font-weight: 700; display: flex; align-items: center; justify-content: space-between; }

    /* Signal Card */
    .signal-card {
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      font-family: 'JetBrains Mono', monospace;
    }
    .badge-call { background: rgba(16, 185, 129, 0.2); color: var(--green); border: 1px solid var(--green); }
    .badge-put { background: rgba(239, 68, 68, 0.2); color: var(--red); border: 1px solid var(--red); }
    .badge-straddle { background: rgba(168, 85, 247, 0.2); color: var(--purple); border: 1px solid var(--purple); }
    .badge-pending { background: rgba(245, 158, 11, 0.2); color: var(--yellow); border: 1px solid var(--yellow); }
    .badge-routed { background: rgba(56, 189, 248, 0.2); color: var(--accent); border: 1px solid var(--accent); }

    /* Multi-Timeframe Matrix Table */
    table { width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }
    th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
    th { color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 0.7rem; }

    /* Log Feed */
    .log-feed {
      max-height: 240px;
      overflow-y: auto;
      background: rgba(0, 0, 0, 0.4);
      padding: 12px;
      border-radius: 10px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .log-entry { display: flex; gap: 8px; color: var(--text-muted); }
    .log-time { color: var(--accent); }
    .log-msg { color: #e2e8f0; }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header>
      <div class="logo-group">
        <div class="logo-badge">⚡ PROPHECY</div>
        <div class="logo-text">
          <h1>Strategy Cases & Contract Selector Matrix</h1>
          <p>Indian Derivatives Options Engine (5-Timeframe Pure Evaluator)</p>
        </div>
      </div>
      <div class="status-group">
        <span class="live-dot" id="sse-dot"></span>
        <span id="sse-status">STREAM CONNECTED</span>
        <span style="color: var(--accent);">NIFTY 50: ₹24,000.00</span>
      </div>
    </header>

    <!-- Top Account Stats -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Paper Cash Balance</div>
        <div class="stat-val" id="stat-cash" style="color: var(--accent);">₹500,000.00</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Portfolio Equity</div>
        <div class="stat-val" id="stat-equity">₹500,000.00</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Realized P&L</div>
        <div class="stat-val" id="stat-realized" style="color: var(--green);">+₹0.00</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Kill Switch Safety</div>
        <div class="stat-val" id="stat-kill" style="color: var(--green);">DISARMED (SAFE)</div>
      </div>
    </div>

    <!-- Strategy Simulation Trigger Control Bar -->
    <div class="case-trigger-card">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h2 style="font-size: 1.05rem; font-weight: 700;">Simulate & Validate Strategy Cases (1 to 6)</h2>
          <p style="font-size: 0.8rem; color: var(--text-muted);">Click any case to generate valid multi-timeframe candles, evaluate strategy conditions, select contracts, and dispatch signals.</p>
        </div>
        <button class="btn btn-kill" id="btn-toggle-kill" onclick="toggleKillSwitch()">🛑 EMERGENCY KILL SWITCH</button>
      </div>
      <div class="case-buttons-grid">
        <button class="btn btn-case" onclick="triggerCase(1)">📊 Case 1: Straddle</button>
        <button class="btn btn-case" onclick="triggerCase(2)">⚡ Case 2: Straddle Special</button>
        <button class="btn btn-case" onclick="triggerCase(3)">🚀 Case 3: Directional Call</button>
        <button class="btn btn-case" onclick="triggerCase(4)">🔻 Case 4: Directional Put</button>
        <button class="btn btn-case" onclick="triggerCase(5)">💎 Case 5: Call Special</button>
        <button class="btn btn-case" onclick="triggerCase(6)">🎯 Case 6: Put Special</button>
        <button class="btn btn-all" onclick="triggerAllCases()">✨ Run All 6 Cases</button>
      </div>
    </div>

    <!-- Main Grid -->
    <div class="main-grid">
      <!-- Left: Active Signal & Contract Selector -->
      <div class="panel">
        <div class="panel-title">
          <span>Active Strategy Signal & Contract Selector</span>
          <span class="badge badge-pending" id="signal-badge">WAITING TRIGGER</span>
        </div>

        <div class="signal-card" id="signal-details">
          <div style="font-size: 0.85rem; color: var(--text-muted);">Click a Strategy Case button above to evaluate conditions and select contracts.</div>
        </div>

        <!-- Selected Contract Details -->
        <div class="panel-title" style="margin-top: 8px;">Resolved Option Contracts</div>
        <div id="contract-details" style="display: flex; flex-direction: column; gap: 10px;">
          <div style="font-size: 0.85rem; color: var(--text-muted);">No contracts resolved yet.</div>
        </div>

        <!-- Operator Action Buttons -->
        <div style="display: flex; gap: 12px; margin-top: auto;" id="action-buttons">
          <!-- Populated dynamically -->
        </div>
      </div>

      <!-- Right: 5-Timeframe Indicator Matrix & Realtime Event Log -->
      <div class="panel">
        <div class="panel-title">
          <span>5-Timeframe Indicator Matrix</span>
          <span style="font-size: 0.75rem; color: var(--accent); font-family: 'JetBrains Mono';">1m • 3m • 5m • 15m • 30m</span>
        </div>

        <table>
          <thead>
            <tr>
              <th>Timeframe</th>
              <th>RSI (14)</th>
              <th>ADX (14)</th>
              <th>+DI / -DI</th>
              <th>BB %B</th>
              <th>RVOL</th>
            </tr>
          </thead>
          <tbody id="matrix-body">
            <tr><td>1m</td><td>--</td><td>--</td><td>--</td><td>--</td><td>--</td></tr>
            <tr><td>3m</td><td>--</td><td>--</td><td>--</td><td>--</td><td>--</td></tr>
            <tr><td>5m</td><td>--</td><td>--</td><td>--</td><td>--</td><td>--</td></tr>
            <tr><td>15m</td><td>--</td><td>--</td><td>--</td><td>--</td><td>--</td></tr>
            <tr><td>30m</td><td>--</td><td>--</td><td>--</td><td>--</td><td>--</td></tr>
          </tbody>
        </table>

        <div class="panel-title" style="margin-top: 10px;">
          <span>Live Event Audit Stream (SSE)</span>
          <button onclick="clearLogs()" style="background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.75rem;">Clear</button>
        </div>
        <div class="log-feed" id="log-feed">
          <div class="log-entry"><span class="log-time">[00:00:00]</span><span class="log-msg">SSE stream initialized. Waiting for events...</span></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let activeSignalId = null;
    let isKillSwitchActive = false;

    function addLog(msg) {
      const feed = document.getElementById('log-feed');
      const time = new Date().toTimeString().split(' ')[0];
      const entry = document.createElement('div');
      entry.className = 'log-entry';
      entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-msg">${msg}</span>`;
      feed.appendChild(entry);
      feed.scrollTop = feed.scrollHeight;
    }

    function clearLogs() {
      document.getElementById('log-feed').innerHTML = '';
    }

    // Connect to Server-Sent Events (SSE)
    const evtSource = new EventSource('/stream/events');
    evtSource.addEventListener('connection', (e) => {
      addLog('🟢 Connected to Prophecy SSE Stream.');
    });
    evtSource.addEventListener('signal', (e) => {
      const data = JSON.parse(e.data);
      addLog(`⚡ New Signal: Case ${data.case_number} (${data.type}) for ${data.symbol} [Status: ${data.status}]`);
    });
    evtSource.addEventListener('signal_confirmed', (e) => {
      const data = JSON.parse(e.data);
      addLog(`✅ Signal ${data.signal_id} CONFIRMED! Orders routed: ${data.orders_count}`);
      updateAccountStats();
    });
    evtSource.addEventListener('signal_ignored', (e) => {
      const data = JSON.parse(e.data);
      addLog(`❌ Signal ${data.signal_id} IGNORED: ${data.reason}`);
    });
    evtSource.addEventListener('kill_switch', (e) => {
      const data = JSON.parse(e.data);
      addLog(`🛑 Kill Switch toggled: ${data.active ? 'ACTIVATED' : 'DEACTIVATED'}`);
      updateKillSwitchState(data.active);
    });

    async function triggerCase(caseNum) {
      addLog(`🚀 Triggering evaluation for Case ${caseNum}...`);
      try {
        const res = await fetch(`/simulate/${caseNum}`, { method: 'POST' });
        const data = await res.json();
        renderSimulationResult(data);
      } catch (err) {
        addLog(`❌ Error triggering Case ${caseNum}: ${err.message}`);
      }
    }

    async function triggerAllCases() {
      addLog('✨ Triggering evaluation across ALL 6 Strategy Cases...');
      try {
        const res = await fetch('/simulate/run/all', { method: 'POST' });
        const data = await res.json();
        addLog(`✅ Successfully evaluated all ${data.total} cases! Displaying latest Case 6.`);
        if (data.cases.length > 0) {
          renderSimulationResult(data.cases[data.cases.length - 1]);
        }
      } catch (err) {
        addLog(`❌ Error running all cases: ${err.message}`);
      }
    }

    function renderSimulationResult(data) {
      const sig = data.signal;
      activeSignalId = sig.id;

      // Update Signal Badge & Card
      const badge = document.getElementById('signal-badge');
      badge.innerText = `CASE ${sig.case_number} • ${sig.signal_type}`;
      badge.className = 'badge ' + (sig.signal_type.includes('CALL') ? 'badge-call' : sig.signal_type.includes('PUT') ? 'badge-put' : 'badge-straddle');

      document.getElementById('signal-details').innerHTML = `
        <div style="display: flex; justify-content: space-between;">
          <span style="font-weight: 700; font-size: 1.1rem; color: var(--accent);">ID: ${sig.id}</span>
          <span style="font-family: 'JetBrains Mono'; font-weight: 600;">PCR: ${sig.pcr.toFixed(2)}</span>
        </div>
        <div style="font-size: 0.85rem; color: #cbd5e1;">${sig.reason}</div>
        <div style="font-family: 'JetBrains Mono'; font-size: 0.8rem; color: var(--text-muted);">
          Underlying: <strong>₹${sig.underlying_price.toFixed(2)}</strong> | Status: <span style="color: var(--yellow);">${sig.status}</span>
        </div>
      `;

      // Render Selected Option Contracts
      const cContainer = document.getElementById('contract-details');
      cContainer.innerHTML = data.selected_contracts.map(c => `
        <div style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 10px; border: 1px solid var(--card-border); font-family: 'JetBrains Mono';">
          <div style="display: flex; justify-content: space-between; font-weight: 700; font-size: 0.95rem; color: ${c.option_type === 'CE' ? 'var(--green)' : 'var(--red)'};">
            <span>${c.trading_symbol}</span>
            <span>LTP: ₹${c.ltp.toFixed(2)}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">
            <span>Strike: ₹${c.strike} (${c.option_type})</span>
            <span>Qty: ${c.quantity} (${c.lot_size} lot) • Value: ₹${c.order_value}</span>
          </div>
          <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 4px;">OI: ${c.open_interest.toLocaleString()} • ${c.selection_reason}</div>
        </div>
      `).join('');

      // Render Action Buttons
      document.getElementById('action-buttons').innerHTML = `
        <button class="btn btn-confirm" style="flex: 2;" onclick="confirmActiveSignal()">⚡ CONFIRM ORDER (${data.selected_contracts.length} leg)</button>
        <button class="btn btn-ignore" style="flex: 1;" onclick="ignoreActiveSignal()">IGNORE</button>
      `;

      // Update 5-Timeframe Table
      const summary = data.indicators_summary;
      const tbody = document.getElementById('matrix-body');
      tbody.innerHTML = ['1m', '3m', '5m', '15m', '30m'].map(tf => {
        const item = summary[tf];
        if (!item) return '';
        return `
          <tr>
            <td style="font-weight: 700; color: var(--accent);">${tf}</td>
            <td style="color: ${item.rsi <= 30 ? 'var(--green)' : item.rsi >= 70 ? 'var(--red)' : '#fff'};">${item.rsi}</td>
            <td style="font-weight: 600;">${item.adx}</td>
            <td>+${item.plus_di} / -${item.minus_di}</td>
            <td>${item.bb_percent_b}</td>
            <td style="color: ${item.rvol >= 2.0 ? 'var(--yellow)' : '#fff'};">${item.rvol}x</td>
          </tr>
        `;
      }).join('');
    }

    async function confirmActiveSignal() {
      if (!activeSignalId) return;
      try {
        const res = await fetch(`/signals/${activeSignalId}/confirm`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operator_id: 'dashboard-operator' })
        });
        const data = await res.json();
        addLog(`✅ Confirmation sent for ${activeSignalId}: ${data.status}`);
        document.getElementById('action-buttons').innerHTML = `<div style="color: var(--green); font-weight: 700; padding: 8px;">Order Routed to Paper Broker!</div>`;
        updateAccountStats();
      } catch (err) {
        addLog(`❌ Confirmation failed: ${err.message}`);
      }
    }

    async function ignoreActiveSignal() {
      if (!activeSignalId) return;
      try {
        await fetch(`/signals/${activeSignalId}/ignore`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operator_id: 'dashboard-operator', reason: 'Operator rejected' })
        });
        addLog(`❌ Signal ${activeSignalId} ignored.`);
        document.getElementById('action-buttons').innerHTML = `<div style="color: var(--red); font-weight: 700; padding: 8px;">Signal Ignored.</div>`;
      } catch (err) {
        addLog(`❌ Ignore failed: ${err.message}`);
      }
    }

    async function toggleKillSwitch() {
      const newState = !isKillSwitchActive;
      try {
        const res = await fetch('/kill-switch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ active: newState, operator_id: 'dashboard-operator' })
        });
        const data = await res.json();
        updateKillSwitchState(data.active);
      } catch (err) {
        addLog(`❌ Failed to toggle kill switch: ${err.message}`);
      }
    }

    function updateKillSwitchState(active) {
      isKillSwitchActive = active;
      const btn = document.getElementById('btn-toggle-kill');
      const stat = document.getElementById('stat-kill');
      if (active) {
        btn.className = 'btn btn-kill active';
        btn.innerText = '⚠️ HALT ACTIVE (CLICK TO DISARM)';
        stat.innerText = 'ACTIVE (HALT)';
        stat.style.color = 'var(--red)';
      } else {
        btn.className = 'btn btn-kill';
        btn.innerText = '🛑 EMERGENCY KILL SWITCH';
        stat.innerText = 'DISARMED (SAFE)';
        stat.style.color = 'var(--green)';
      }
    }

    async function updateAccountStats() {
      try {
        const res = await fetch('/account/summary');
        const data = await res.json();
        document.getElementById('stat-cash').innerText = '₹' + data.cash_balance.toLocaleString('en-IN', { minimumFractionDigits: 2 });
        document.getElementById('stat-equity').innerText = '₹' + data.total_equity.toLocaleString('en-IN', { minimumFractionDigits: 2 });
        const pnl = data.realized_pnl;
        const pnlEl = document.getElementById('stat-realized');
        pnlEl.innerText = (pnl >= 0 ? '+₹' : '-₹') + Math.abs(pnl).toLocaleString('en-IN', { minimumFractionDigits: 2 });
        pnlEl.style.color = pnl >= 0 ? 'var(--green)' : 'var(--red)';
      } catch (err) {}
    }

    // Initial load
    updateAccountStats();
  </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard() -> HTMLResponse:
    """Serve the interactive Prophecy strategy cases and contract selector dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML)
