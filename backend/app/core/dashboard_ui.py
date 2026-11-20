"""Interactive Web Control Center for the Super App Modular Monolith (GET /dashboard)."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Control Center UI"])

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Super App Ecosystem — Control Center</title>
  <style>
    :root {
      --bg-base: #090d16;
      --bg-surface: #111827;
      --bg-surface-elevated: #162032;
      --bg-input: #1e293b;
      --border-subtle: #1e293b;
      --border-focus: #334155;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --emerald: #10b981;
      --emerald-light: #34d399;
      --purple: #a855f7;
      --purple-light: #c084fc;
      --amber: #f59e0b;
      --amber-light: #fbbf24;
      --cyan: #06b6d4;
      --cyan-light: #22d3ee;
      --rose: #f43f5e;
      --blue: #3b82f6;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-base);
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Helvetica Neue", sans-serif;
      line-height: 1.5;
      padding: 1.5rem;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }

    .container {
      max-width: 1380px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }

    /* Cards & Containers */
    .card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 1rem;
      padding: 1.25rem;
      box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.4);
    }
    .card-elevated {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: 0.75rem;
      padding: 1rem;
    }

    /* Header */
    .top-header {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      background: linear-gradient(135deg, #111827 0%, #0f172a 100%);
      border: 1px solid var(--border-subtle);
      border-radius: 1rem;
      padding: 1.25rem 1.5rem;
    }
    .header-tag {
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--emerald);
    }
    .header-title {
      font-size: 1.5rem;
      font-weight: 800;
      color: #ffffff;
      margin-top: 0.15rem;
    }
    .header-sub {
      font-size: 0.825rem;
      color: var(--text-muted);
    }
    .header-actions {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.75rem;
    }

    /* KPI Summary Grid */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1rem;
    }
    .kpi-card {
      padding: 1rem 1.25rem;
      border-radius: 1rem;
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.2s, border-color 0.2s;
    }
    .kpi-card:hover {
      transform: translateY(-2px);
    }
    .kpi-emerald { border-color: rgba(16, 185, 129, 0.35); }
    .kpi-purple { border-color: rgba(168, 85, 247, 0.35); }
    .kpi-amber { border-color: rgba(245, 158, 11, 0.35); }
    .kpi-cyan { border-color: rgba(6, 182, 212, 0.35); }
    .kpi-title {
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }
    .kpi-value {
      font-size: 1.45rem;
      font-weight: 800;
      margin: 0.25rem 0;
    }
    .kpi-footer {
      font-size: 0.75rem;
      color: var(--text-dim);
    }

    /* Navigation Tabs */
    .tabs-bar {
      display: flex;
      gap: 0.5rem;
      background: #0d131f;
      padding: 0.375rem;
      border-radius: 0.875rem;
      border: 1px solid var(--border-subtle);
      overflow-x: auto;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 0.85rem;
      font-weight: 600;
      padding: 0.6rem 1.15rem;
      border-radius: 0.65rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      white-space: nowrap;
      transition: all 0.2s ease;
    }
    .tab-btn:hover {
      color: #ffffff;
      background: rgba(255, 255, 255, 0.05);
    }
    .tab-btn.active {
      color: #ffffff;
      background: #1e293b;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
      border: 1px solid #334155;
    }

    /* Status Banner */
    #statusBanner {
      padding: 0.85rem 1.25rem;
      border-radius: 0.75rem;
      font-size: 0.875rem;
      font-weight: 500;
    }
    .banner-success {
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #a7f3d0;
    }
    .banner-error {
      background: rgba(244, 63, 94, 0.15);
      border: 1px solid rgba(244, 63, 94, 0.4);
      color: #fecdd3;
    }

    /* Tab Content Panes */
    .tab-pane {
      display: none;
    }
    .tab-pane.active-pane {
      display: block;
    }

    /* Multi-Column Layouts */
    .grid-overview {
      display: grid;
      grid-template-columns: 1fr;
      gap: 1.25rem;
    }
    .grid-two-col {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.25rem;
    }
    .grid-studio {
      display: grid;
      grid-template-columns: minmax(380px, 1.15fr) minmax(460px, 1.85fr);
      gap: 1.25rem;
      align-items: start;
    }
    .grid-all-view {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1.25rem;
    }
    @media (max-width: 980px) {
      .grid-two-col { grid-template-columns: 1fr; }
      .grid-studio { grid-template-columns: 1fr; }
    }

    .btn-sm {
      padding: 0.38rem 0.7rem !important;
      font-size: 0.725rem !important;
      border-radius: 0.5rem !important;
    }

    .job-card {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: 0.85rem;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      transition: border-color 0.15s;
    }
    .job-card:hover {
      border-color: #334155;
    }

    .job-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.75rem;
      flex-wrap: wrap;
    }

    .script-box {
      background: #090d16;
      border: 1px solid var(--border-subtle);
      border-radius: 0.65rem;
      padding: 0.75rem;
      display: flex;
      flex-direction: column;
      gap: 0.45rem;
      font-size: 0.75rem;
    }
    .script-row {
      display: flex;
      gap: 0.5rem;
      align-items: baseline;
      flex-wrap: wrap;
    }
    .tag-badge {
      font-size: 0.65rem;
      font-weight: 700;
      padding: 0.15rem 0.45rem;
      border-radius: 0.35rem;
      white-space: nowrap;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .tag-hook {
      background: rgba(245, 158, 11, 0.18);
      color: var(--amber-light);
      border: 1px solid rgba(245, 158, 11, 0.35);
    }
    .tag-cta {
      background: rgba(6, 182, 212, 0.18);
      color: var(--cyan-light);
      border: 1px solid rgba(6, 182, 212, 0.35);
    }
    .tag-combo {
      background: rgba(168, 85, 247, 0.18);
      color: var(--purple-light);
      border: 1px solid rgba(168, 85, 247, 0.35);
    }
    .tag-audio {
      background: rgba(16, 185, 129, 0.18);
      color: var(--emerald-light);
      border: 1px solid rgba(16, 185, 129, 0.35);
    }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 0.8rem;
      padding: 0.55rem 0.95rem;
      border-radius: 0.65rem;
      border: 1px solid transparent;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
      gap: 0.4rem;
    }
    .btn-emerald {
      background: var(--emerald);
      color: #022c22;
    }
    .btn-emerald:hover { background: var(--emerald-light); }
    .btn-emerald-outline {
      background: rgba(16, 185, 129, 0.12);
      border-color: rgba(16, 185, 129, 0.35);
      color: var(--emerald-light);
    }
    .btn-emerald-outline:hover { background: rgba(16, 185, 129, 0.22); }

    .btn-purple {
      background: var(--purple);
      color: #ffffff;
    }
    .btn-purple:hover { background: var(--purple-light); }
    .btn-purple-outline {
      background: rgba(168, 85, 247, 0.12);
      border-color: rgba(168, 85, 247, 0.35);
      color: var(--purple-light);
    }
    .btn-purple-outline:hover { background: rgba(168, 85, 247, 0.22); }

    .btn-cyan {
      background: var(--cyan);
      color: #083344;
    }
    .btn-cyan:hover { background: var(--cyan-light); }
    .btn-cyan-outline {
      background: rgba(6, 182, 212, 0.12);
      border-color: rgba(6, 182, 212, 0.35);
      color: var(--cyan-light);
    }
    .btn-cyan-outline:hover { background: rgba(6, 182, 212, 0.22); }

    .btn-amber-outline {
      background: rgba(245, 158, 11, 0.12);
      border-color: rgba(245, 158, 11, 0.35);
      color: var(--amber-light);
    }
    .btn-amber-outline:hover { background: rgba(245, 158, 11, 0.22); }

    .btn-secondary {
      background: #1e293b;
      color: var(--text-main);
      border-color: #334155;
    }
    .btn-secondary:hover { background: #334155; }

    /* Forms & Inputs */
    input[type="text"], input[type="number"], select {
      width: 100%;
      background: var(--bg-input);
      border: 1px solid var(--border-subtle);
      border-radius: 0.55rem;
      padding: 0.5rem 0.75rem;
      font-size: 0.8rem;
      color: #ffffff;
      outline: none;
      transition: border-color 0.15s;
    }
    input:focus, select:focus {
      border-color: var(--border-focus);
    }
    label {
      display: block;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 0.25rem;
    }

    /* Utility & Helper Classes for JS templates */
    .hidden { display: none !important; }
    .flex { display: flex; }
    .flex-col { flex-direction: column; }
    .flex-wrap { flex-wrap: wrap; }
    .items-center { align-items: center; }
    .items-start { align-items: flex-start; }
    .justify-between { justify-content: space-between; }
    .justify-center { justify-content: center; }
    .grid { display: grid; }
    .grid-cols-1 { grid-template-columns: repeat(1, minmax(0, 1fr)); }
    .grid-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .grid-cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .gap-1 { gap: 0.25rem; }
    .gap-1\.5 { gap: 0.375rem; }
    .gap-2 { gap: 0.5rem; }
    .gap-3 { gap: 0.75rem; }
    .gap-4 { gap: 1rem; }
    .gap-6 { gap: 1.5rem; }
    .space-y-1 > * + * { margin-top: 0.25rem; }
    .space-y-2 > * + * { margin-top: 0.5rem; }
    .space-y-3 > * + * { margin-top: 0.75rem; }
    .space-y-4 > * + * { margin-top: 1rem; }
    .p-1 { padding: 0.25rem; }
    .p-1\.5 { padding: 0.375rem; }
    .p-2 { padding: 0.5rem; }
    .p-2\.5 { padding: 0.625rem; }
    .p-3 { padding: 0.75rem; }
    .p-3\.5 { padding: 0.875rem; }
    .p-4 { padding: 1rem; }
    .pt-1 { padding-top: 0.25rem; }
    .pt-2 { padding-top: 0.5rem; }
    .px-1\.5 { padding-left: 0.375rem; padding-right: 0.375rem; }
    .px-2 { padding-left: 0.5rem; padding-right: 0.5rem; }
    .px-2\.5 { padding-left: 0.625rem; padding-right: 0.625rem; }
    .px-3 { padding-left: 0.75rem; padding-right: 0.75rem; }
    .py-0\.5 { padding-top: 0.125rem; padding-bottom: 0.125rem; }
    .py-1 { padding-top: 0.25rem; padding-bottom: 0.25rem; }
    .py-1\.5 { padding-top: 0.375rem; padding-bottom: 0.375rem; }
    .py-2 { padding-top: 0.5rem; padding-bottom: 0.5rem; }
    .py-2\.5 { padding-top: 0.625rem; padding-bottom: 0.625rem; }
    .rounded { border-radius: 0.25rem; }
    .rounded-lg { border-radius: 0.5rem; }
    .rounded-xl { border-radius: 0.75rem; }
    .rounded-full { border-radius: 9999px; }
    .border { border-width: 1px; border-style: solid; border-color: var(--border-subtle); }
    .border-t { border-top-width: 1px; border-top-style: solid; border-color: var(--border-subtle); }
    .border-slate-800 { border-color: #1e293b; }
    .border-slate-700 { border-color: #334155; }
    .border-emerald-500\/30 { border-color: rgba(16, 185, 129, 0.3); }
    .border-emerald-500\/40 { border-color: rgba(16, 185, 129, 0.4); }
    .border-emerald-500\/50 { border-color: rgba(16, 185, 129, 0.5); }
    .border-purple-500\/30 { border-color: rgba(168, 85, 247, 0.3); }
    .border-purple-500\/40 { border-color: rgba(168, 85, 247, 0.4); }
    .border-purple-500\/60 { border-color: rgba(168, 85, 247, 0.6); }
    .border-cyan-500\/30 { border-color: rgba(6, 182, 212, 0.3); }
    .border-cyan-500\/40 { border-color: rgba(6, 182, 212, 0.4); }
    .border-amber-500\/40 { border-color: rgba(245, 158, 11, 0.4); }
    .border-blue-500\/30 { border-color: rgba(59, 130, 246, 0.3); }
    .bg-slate-800 { background-color: #1e293b; }
    .bg-slate-900 { background-color: #0f172a; }
    .bg-slate-900\/70 { background-color: rgba(15, 23, 42, 0.7); }
    .bg-slate-900\/90 { background-color: rgba(15, 23, 42, 0.9); }
    .bg-slate-950 { background-color: #020617; }
    .bg-emerald-500\/20 { background-color: rgba(16, 185, 129, 0.2); }
    .bg-purple-500\/20 { background-color: rgba(168, 85, 247, 0.2); }
    .bg-amber-500\/20 { background-color: rgba(245, 158, 11, 0.2); }
    .bg-cyan-500\/20 { background-color: rgba(6, 182, 212, 0.2); }
    .bg-blue-500\/20 { background-color: rgba(59, 130, 246, 0.2); }
    .bg-cyan-400 { background-color: #22d3ee; }
    .text-white { color: #ffffff; }
    .text-slate-300 { color: #cbd5e1; }
    .text-slate-400 { color: #94a3b8; }
    .text-slate-500 { color: #64748b; }
    .text-emerald-300 { color: #6ee7b7; }
    .text-emerald-400 { color: #34d399; }
    .text-purple-200 { color: #e9d5ff; }
    .text-purple-300 { color: #d8b4fe; }
    .text-amber-300 { color: #fcd34d; }
    .text-amber-400 { color: #fbbf24; }
    .text-cyan-300 { color: #67e8f9; }
    .text-cyan-400 { color: #22d3ee; }
    .text-blue-300 { color: #93c5fd; }
    .text-\[10px\] { font-size: 0.625rem; line-height: 0.875rem; }
    .text-\[11px\] { font-size: 0.6875rem; line-height: 0.95rem; }
    .text-xs { font-size: 0.75rem; line-height: 1rem; }
    .text-sm { font-size: 0.875rem; line-height: 1.25rem; }
    .font-medium { font-weight: 500; }
    .font-semibold { font-weight: 600; }
    .font-bold { font-weight: 700; }
    .font-extrabold { font-weight: 800; }
    .font-black { font-weight: 900; }
    .uppercase { text-transform: uppercase; }
    .tracking-wider { letter-spacing: 0.05em; }
    .tracking-widest { letter-spacing: 0.1em; }
    .line-through { text-decoration: line-through; }
    .whitespace-pre-wrap { white-space: pre-wrap; }
    .overflow-y-auto { overflow-y: auto; }
    .overflow-x-auto { overflow-x: auto; }
    .overflow-hidden { overflow: hidden; }
    .max-h-64 { max-height: 16rem; }
    .max-h-80 { max-height: 20rem; }
    .w-full { width: 100%; }
    .h-full { height: 100%; }
    .h-1\.5 { height: 0.375rem; }
    .block { display: block; }
    .text-center { text-align: center; }
    .cursor-pointer { cursor: pointer; }

    /* Custom Scrollbars */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-base); }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #475569; }
  </style>
</head>
<body>
  <div class="container">
    <!-- Top Header & 1-Click Auto-Login -->
    <header class="top-header">
      <div>
        <span class="header-tag">Modular Monolith • 4 Bounded Contexts</span>
        <h1 class="header-title">Super App Ecosystem — Live Control Center</h1>
        <p class="header-sub">Conectado en vivo a <code style="color: var(--emerald-light);">/api/v1/{identity,wallet,commerce,media-ai}</code></p>
      </div>
      <div class="header-actions">
        <div id="authBadge" class="btn btn-secondary" style="cursor: default; font-size: 0.75rem;">
          Sin sesión activa
        </div>
        <button onclick="downloadWeeklyReport()" class="btn btn-purple-outline">
          📊 Descargar Reporte Semanal (.MD)
        </button>
        <button onclick="loginDemoUser()" class="btn btn-emerald">
          ⚡ Auto-Login Demo (demo@superapp.co)
        </button>
      </div>
    </header>

    <!-- Unit Economics & Daily Streak Banner (4 Cards Always Visible) -->
    <section class="kpi-grid">
      <div class="kpi-card kpi-emerald">
        <div class="kpi-title">Unidad Económica • Stock en Casa (COGS)</div>
        <div id="invCostVal" class="kpi-value" style="color: #ffffff;">$0 COP</div>
        <div id="invRetailVal" class="kpi-footer" style="color: var(--emerald-light);">Valor Venta Potencial: $0 COP</div>
      </div>
      <div class="kpi-card kpi-purple">
        <div class="kpi-title">Utilidad Neta Real (Post COGS + Envío)</div>
        <div id="netProfitVal" class="kpi-value" style="color: var(--emerald-light);">$0 COP</div>
        <div id="grossRevVal" class="kpi-footer">Ingresos Brutos: $0 COP</div>
      </div>
      <div class="kpi-card kpi-amber">
        <div class="kpi-title">🔥 Meta Diaria: 2 Videos/Día</div>
        <div id="streakBadge" class="kpi-value" style="color: var(--amber-light);">0/2</div>
        <div class="kpi-footer">Franja 1 (12:30) + Franja 2 (19:30)</div>
      </div>
      <div class="kpi-card kpi-cyan">
        <div class="kpi-title">Atribución de Ventas por Video</div>
        <div id="totalRevenueBadge" class="kpi-value" style="color: var(--cyan-light);">$0 COP</div>
        <div class="kpi-footer">Conversiones: <span id="totalConversionsBadge" style="font-weight: 700; color: #ffffff;">0</span></div>
      </div>
    </section>

    <!-- Tab Navigation Bar -->
    <nav class="tabs-bar">
      <button id="tabBtn-overview" class="tab-btn active" onclick="switchTab('overview')">
        📊 Resumen y Nichos
      </button>
      <button id="tabBtn-commerce" class="tab-btn" onclick="switchTab('commerce')">
        🛍️ Tienda y Pedidos
      </button>
      <button id="tabBtn-studio" class="tab-btn" onclick="switchTab('studio')">
        🎬 Studio IA y Agenda
      </button>
      <button id="tabBtn-wallet" class="tab-btn" onclick="switchTab('wallet')">
        💳 Billetera y Ledger
      </button>
      <button id="tabBtn-all" class="tab-btn" onclick="switchTab('all')">
        👁️ Ver Todo
      </button>
    </nav>

    <!-- Global Notification Banner -->
    <div id="statusBanner" class="hidden"></div>

    <!-- TAB 1: Overview & Niche Analytics -->
    <div id="tabPane-overview" class="tab-pane active-pane">
      <section class="card space-y-4" style="border-color: rgba(6, 182, 212, 0.3);">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-2">
          <div>
            <h2 class="text-sm font-bold text-cyan-300" style="font-size: 1rem;">📈 Rendimiento por Nicho (ROI de Contenido)</h2>
            <p class="text-xs text-slate-400">Comparativa en vivo de videos creados, agendados, conversiones y ventas reales en COP por vertical</p>
          </div>
          <div id="topNicheBadge" class="px-3 py-1 rounded-lg bg-cyan-500/20 border border-cyan-500/30 text-xs text-cyan-300 font-semibold">
            Vertical Líder: Evaluando...
          </div>
        </div>
        <div id="nicheAnalyticsGrid" class="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div class="p-4 rounded-xl bg-slate-900 border border-slate-800 text-slate-500">Inicia sesión con Auto-Login Demo para cargar métricas por nicho.</div>
        </div>
      </section>
    </div>

    <!-- TAB 2: Commerce & Orders -->
    <div id="tabPane-commerce" class="tab-pane">
      <div class="grid-two-col">
        <!-- Products & Creation -->
        <section class="card space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-bold text-purple-300" style="font-size: 1.1rem;">Catálogo & Precios Dinámicos</h2>
            <button onclick="loadCatalogAndOrders()" class="text-xs text-slate-400 hover:text-white" style="cursor: pointer;">Actualizar ↻</button>
          </div>

          <!-- Attribution & Coupon Selector -->
          <div class="card-elevated space-y-2">
            <label class="block text-xs font-semibold text-amber-300">Atribuir Compra al Video (source_job_id)</label>
            <select id="orderSourceJobSelect">
              <option value="">-- Compra directa (sin atribución de video) --</option>
            </select>
            <label class="block text-xs font-semibold text-emerald-300 pt-1">🎟️ Cupón Promocional (ej. SUPER10)</label>
            <input id="orderCouponCodeInput" type="text" placeholder="SUPER10 (10% OFF con piso COGS 1.15x)" style="text-transform: uppercase;" />
          </div>

          <!-- Create Product Form -->
          <div class="card-elevated space-y-2">
            <div class="text-xs font-semibold text-purple-300">Crear Producto / Reabastecer Stock</div>
            <div class="grid grid-cols-3 gap-2">
              <input id="newProdSku" type="text" placeholder="SKU" />
              <input id="newProdPrice" type="number" placeholder="Precio COP" />
              <input id="newProdCost" type="number" placeholder="Costo COGS" />
            </div>
            <input id="newProdTitle" type="text" placeholder="Título del Producto" />
            <button onclick="createProductFromDashboard()" class="w-full btn btn-purple" style="font-size: 0.75rem;">
              + Crear Producto en Catálogo
            </button>
          </div>

          <!-- Cross-Sell Bundle Recommendation -->
          <div id="crossSellBundleCard" class="hidden"></div>

          <!-- Product Catalog List -->
          <div id="catalogList" class="space-y-3"></div>
        </section>

        <!-- Orders & Fulfillment -->
        <section class="card space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-bold text-purple-300" style="font-size: 1.1rem;">Órdenes, Entrega COD & WhatsApp</h2>
            <span class="text-xs text-slate-500">Actualización en vivo</span>
          </div>
          <div id="ordersList" class="space-y-2 overflow-y-auto" style="max-height: 48rem;"></div>
        </section>
      </div>
    </div>

    <!-- TAB 3: Media AI Studio & Schedule -->
    <div id="tabPane-studio" class="tab-pane">
      <div class="grid-studio">
        <!-- Enqueue Job Form (Columna Izquierda con mayor amplitud para selects) -->
        <section class="card space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-bold text-cyan-300" style="font-size: 1.15rem;">Studio IA Multinicho</h2>
            <button onclick="loadMediaJobs()" class="text-xs text-slate-400 hover:text-white" style="cursor: pointer;">Actualizar ↻</button>
          </div>
          <div class="space-y-3 card-elevated">
            <div>
              <label>Nicho de Contenido (Plantilla de Retención)</label>
              <select id="contentNicheSelect">
                <option value="DESK_SETUP_UGC">DESK_SETUP_UGC (Setup Productividad & Gadgets)</option>
                <option value="RAP_CULTURE_VIRAL">RAP_CULTURE_VIRAL (Cultura Rap, Barras & Streetwear)</option>
                <option value="YOUTUBE_HIGHLIGHT_CLIP">YOUTUBE_HIGHLIGHT_CLIP (Highlights & Clips Virales 9:16)</option>
                <option value="MENSWEAR_LOOKBOOK">MENSWEAR_LOOKBOOK (Moda Masculina & Outfits)</option>
              </select>
            </div>
            <div>
              <label>Tipo de Trabajo Asíncrono</label>
              <select id="jobTypeSelect">
                <option value="PRODUCT_SHOWCASE_VIDEO">PRODUCT_SHOWCASE_VIDEO (Guion UGC + Vídeo)</option>
                <option value="VIRAL_SHORT_CLIP">VIRAL_SHORT_CLIP (Clip 9:16 + Hook 3s)</option>
                <option value="AI_OUTFIT_RECOMMENDATION">AI_OUTFIT_RECOMMENDATION (Calendario Lunes-Domingo)</option>
                <option value="AUTO_CAPTIONS_WHISPER">AUTO_CAPTIONS_WHISPER (Subtítulos .SRT)</option>
              </select>
            </div>
            <div>
              <label>Prompt o URL de Video Origen</label>
              <input id="jobSourceInput" type="text" value="https://storage.superapp.io/demo/setup_ergo_raw.mp4" />
            </div>
            <div>
              <label>Vincular Producto del Catálogo (Opcional)</label>
              <select id="jobProductSelect">
                <option value="">-- Sin producto vinculado --</option>
              </select>
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.45rem; padding-top: 0.35rem;">
              <label class="flex items-center gap-2 text-xs text-amber-300 font-semibold cursor-pointer">
                <input id="useRealPipelineCheck" type="checkbox" style="width: auto;" />
                🎬 Activar Pipeline Real (yt-dlp 720p + Whisper + FFmpeg 9:16)
              </label>
              <label class="flex items-center gap-2 text-xs text-emerald-300 font-semibold cursor-pointer">
                <input id="burnSubtitlesCheck" type="checkbox" checked style="width: auto;" />
                🔥 Quemar Subtítulos Estilo TikTok en el MP4
              </label>
            </div>
            <button onclick="enqueueStudioJob()" class="w-full btn btn-cyan" style="font-size: 0.85rem; padding: 0.8rem; margin-top: 0.25rem;">
              🚀 Encolar Trabajo Asíncrono (HTTP 202)
            </button>
          </div>
        </section>

        <!-- Scheduled & Processing Queue -->
        <section class="card space-y-4">
          <div>
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Videos Agendados & Atribución</h3>
              <span class="text-[11px] text-amber-300 font-semibold">Meta: 2/día</span>
            </div>
            <div id="scheduleList" class="space-y-2 mb-4 text-xs"></div>
          </div>
          <div class="pt-3 border-t border-slate-800">
            <div class="flex items-center justify-between gap-2 mb-2 flex-wrap">
              <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Cola de Procesamiento & Descarga .SRT / .MD / .ICS</h3>
              <div class="flex items-center gap-2">
                <button onclick="purgeExpiredMediaArtifacts(30)" class="btn btn-amber-outline btn-sm" style="font-size: 0.7rem;">
                  🧹 Purgar Artefactos Antiguos (>30d)
                </button>
                <span class="text-[11px] text-cyan-300">Asíncrono</span>
              </div>
            </div>
            <div id="jobsList" class="space-y-3 overflow-y-auto text-xs" style="max-height: 40rem;"></div>
          </div>
        </section>
      </div>
    </div>

    <!-- TAB 4: Wallet & Ledger -->
    <div id="tabPane-wallet" class="tab-pane">
      <div class="grid-two-col">
        <section class="card space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-bold text-emerald-400" style="font-size: 1.1rem;">Billetera (Wallet COP)</h2>
            <button onclick="loadWallet()" class="text-xs text-slate-400 hover:text-white" style="cursor: pointer;">Actualizar ↻</button>
          </div>
          <div class="card-elevated" style="border-color: rgba(16, 185, 129, 0.3);">
            <div class="flex justify-between items-start">
              <div>
                <div class="text-xs text-slate-400">Saldo Disponible</div>
                <div id="walletBalance" class="text-3xl font-extrabold text-white mt-1" style="font-size: 2rem;">$0 COP</div>
              </div>
              <div id="loyaltyTierBadge" class="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-700/20 text-amber-400 border border-amber-700/40">
                🥉 BRONZE
              </div>
            </div>
            <div id="walletIdText" class="text-[11px] text-slate-500 mt-1">Inicia sesión para consultar tu billetera</div>
          </div>

          <!-- Cashback & Loyalty Points Box -->
          <div class="card-elevated space-y-2" style="border-color: rgba(168, 85, 247, 0.35);">
            <div class="flex justify-between items-center">
              <span class="text-xs font-bold text-purple-300">🎁 Programa Cashback & Fidelización (3%)</span>
              <span class="text-[11px] text-slate-400">Nivel VIP: <strong id="loyaltyTierLevel" class="text-white">BRONZE</strong></span>
            </div>
            <div class="flex justify-between items-baseline">
              <div class="text-xs text-slate-400">Puntos Disponibles:</div>
              <div id="loyaltyPointsVal" class="text-base font-extrabold text-emerald-400">0 pts ($0 COP)</div>
            </div>
            <div class="text-[11px] text-slate-500">
              Volumen acumulado: <span id="lifetimeVolumeVal" class="text-slate-300 font-medium">$0 COP</span> (SILVER a $300k • GOLD a $1M COP)
            </div>
            <button id="redeemPointsBtn" onclick="redeemCashbackPoints()" class="w-full btn btn-purple-outline" style="font-size: 0.775rem;">
              🎁 Canjear Puntos a Saldo COP
            </button>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <button onclick="walletTransaction('deposit', 5000000)" class="btn btn-emerald-outline">
              + Recargar $50,000 COP
            </button>
            <button onclick="walletTransaction('withdraw', 2000000)" class="btn btn-amber-outline">
              - Retirar $20,000 COP
            </button>
          </div>
        </section>

        <section class="card space-y-4">
          <h2 class="text-sm font-bold text-emerald-400" style="font-size: 1.1rem;">Libro Mayor Inmutable (Ledger)</h2>
          <div id="ledgerList" class="space-y-2 overflow-y-auto text-xs" style="max-height: 24rem;"></div>
        </section>
      </div>
    </div>
  </div>

  <script>
    const TOKEN_STORAGE_KEY = "superapp_dashboard_tokens";
    const DEMO_CREDENTIALS = {
      email: "demo@superapp.co",
      password: "SuperApp2026!",
      full_name: "Demo Founder Super App",
      roles: ["USER", "MERCHANT", "CREATOR"]
    };
    let accessToken = null;
    let refreshToken = null;
    let refreshInFlight = null;
    let currentTab = "overview";
    const copFormat = (cents) => "$" + Math.round((cents || 0) / 100).toLocaleString("es-CO") + " COP";

    function loadStoredTokens() {
      try {
        const raw = localStorage.getItem(TOKEN_STORAGE_KEY);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        accessToken = parsed.access_token || null;
        refreshToken = parsed.refresh_token || null;
      } catch (_) {
        accessToken = null;
        refreshToken = null;
      }
    }

    function setSessionTokens(nextAccess, nextRefresh) {
      accessToken = nextAccess || null;
      refreshToken = nextRefresh || null;
      try {
        if (accessToken || refreshToken) {
          localStorage.setItem(
            TOKEN_STORAGE_KEY,
            JSON.stringify({ access_token: accessToken, refresh_token: refreshToken })
          );
        } else {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
        }
      } catch (_) {}
    }

    function clearSessionTokens(notifyUser = false) {
      setSessionTokens(null, null);
      const badge = document.getElementById("authBadge");
      if (badge) badge.textContent = "Sin sesión activa";
      if (notifyUser) {
        showBanner("Tu sesión no es válida o expiró. Haz clic en '⚡ Auto-Login Demo (demo@superapp.co)' para continuar.", true);
      }
    }

    async function rotateAccessToken() {
      if (!refreshToken) return false;
      if (refreshInFlight) return refreshInFlight;
      refreshInFlight = (async () => {
        try {
          const res = await fetch("/api/v1/identity/auth/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken })
          });
          if (!res.ok) {
            clearSessionTokens(false);
            return false;
          }
          const tokens = await res.json();
          setSessionTokens(tokens.access_token, tokens.refresh_token);
          return Boolean(accessToken);
        } catch (_) {
          return false;
        } finally {
          refreshInFlight = null;
        }
      })();
      return refreshInFlight;
    }

    function switchTab(tabId) {
      currentTab = tabId;
      const tabBtns = document.querySelectorAll(".tab-btn");
      tabBtns.forEach(btn => btn.classList.remove("active"));
      const activeBtn = document.getElementById(`tabBtn-${tabId}`);
      if (activeBtn) activeBtn.classList.add("active");

      const panes = {
        overview: document.getElementById("tabPane-overview"),
        commerce: document.getElementById("tabPane-commerce"),
        studio: document.getElementById("tabPane-studio"),
        wallet: document.getElementById("tabPane-wallet")
      };

      if (tabId === "all") {
        Object.values(panes).forEach(pane => {
          if (pane) {
            pane.style.display = "block";
            pane.classList.add("active-pane");
          }
        });
      } else {
        Object.entries(panes).forEach(([key, pane]) => {
          if (pane) {
            if (key === tabId) {
              pane.style.display = "block";
              pane.classList.add("active-pane");
            } else {
              pane.style.display = "none";
              pane.classList.remove("active-pane");
            }
          }
        });
      }
    }

    function showBanner(msg, isError = false) {
      const el = document.getElementById("statusBanner");
      el.textContent = msg;
      el.className = isError ? "banner-error" : "banner-success";
      el.classList.remove("hidden");
    }

    async function apiFetchRaw(path, options = {}) {
      const { skipAuth = false, _retried = false, headers: customHeaders = {}, ...fetchOptions } = options;
      const headers = { ...customHeaders };
      if (!skipAuth && accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
      }
      const res = await fetch(path, { ...fetchOptions, headers });
      if (res.status === 401 && !skipAuth && !_retried) {
        const refreshed = await rotateAccessToken();
        if (refreshed) {
          return apiFetchRaw(path, { ...options, _retried: true });
        }
        clearSessionTokens(true);
      }
      return res;
    }

    async function apiFetch(path, options = {}) {
      const mergedHeaders = { "Content-Type": "application/json", ...(options.headers || {}) };
      const res = await apiFetchRaw(path, { ...options, headers: mergedHeaders });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      return data;
    }

    async function syncAuthenticatedDashboard(me, silent = false) {
      document.getElementById("authBadge").innerHTML =
        `<span style="color: var(--emerald); font-weight: 700;">● ${me.full_name}</span> <span style="color: var(--text-dim); margin-left: 0.25rem;">[${me.roles.join(", ")}]</span>`;
      if (!silent) {
        showBanner(`Sesión iniciada como ${me.email}. Datos sincronizados en tiempo real.`);
      }
      await Promise.all([loadWallet(), loadCatalogAndOrders(), loadMediaJobs()]);
    }

    async function loginDemoUser() {
      try {
        let loginRes = await fetch("/api/v1/identity/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: DEMO_CREDENTIALS.email,
            password: DEMO_CREDENTIALS.password
          })
        });

        // If demo user does not exist yet in a fresh local DB, auto-register and retry login
        if (loginRes.status === 401) {
          const regRes = await fetch("/api/v1/identity/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(DEMO_CREDENTIALS)
          });
          if (regRes.ok || regRes.status === 409) {
            loginRes = await fetch("/api/v1/identity/login", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                email: DEMO_CREDENTIALS.email,
                password: DEMO_CREDENTIALS.password
              })
            });
          }
        }

        const tokens = await loginRes.json().catch(() => ({}));
        if (!loginRes.ok) {
          throw new Error(tokens.detail || `HTTP ${loginRes.status}`);
        }
        setSessionTokens(tokens.access_token, tokens.refresh_token);
        const me = await apiFetch("/api/v1/identity/me");
        await syncAuthenticatedDashboard(me, false);
      } catch (err) {
        showBanner("Error en Auto-Login: " + err.message, true);
      }
    }

    async function loadWallet() {
      if (!accessToken) return;
      const data = await apiFetch("/api/v1/wallet/me");
      document.getElementById("walletBalance").textContent = copFormat(data.wallet.balance_cents);
      document.getElementById("walletIdText").textContent = `Wallet ID: ${data.wallet.id} • Moneda: ${data.wallet.currency}`;

      const tier = data.wallet.loyalty_tier || "BRONZE";
      const points = data.wallet.loyalty_points || 0;
      const volume = data.wallet.lifetime_volume_cents || 0;

      const tierBadgeEl = document.getElementById("loyaltyTierBadge");
      const tierLevelEl = document.getElementById("loyaltyTierLevel");
      if (tierBadgeEl) {
        if (tier === "GOLD") {
          tierBadgeEl.innerHTML = "🥇 GOLD VIP (Envío Gratis)";
          tierBadgeEl.className = "px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-500/25 text-amber-300 border border-amber-500/50";
        } else if (tier === "SILVER") {
          tierBadgeEl.innerHTML = "🥈 SILVER VIP (Envío Gratis)";
          tierBadgeEl.className = "px-2.5 py-1 rounded-lg text-xs font-bold bg-slate-300/20 text-slate-200 border border-slate-300/40";
        } else {
          tierBadgeEl.innerHTML = "🥉 BRONZE";
          tierBadgeEl.className = "px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-700/20 text-amber-400 border border-amber-700/40";
        }
      }
      if (tierLevelEl) tierLevelEl.textContent = tier;
      const ptsValEl = document.getElementById("loyaltyPointsVal");
      if (ptsValEl) ptsValEl.textContent = `${points.toLocaleString("es-CO")} pts (${copFormat(points)})`;
      const volEl = document.getElementById("lifetimeVolumeVal");
      if (volEl) volEl.textContent = copFormat(volume);

      const list = document.getElementById("ledgerList");
      list.innerHTML = data.recent_entries.map(e => `
        <div class="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex justify-between items-center">
          <div>
            <div class="font-semibold text-white">${e.reference}</div>
            <div class="text-[10px] text-slate-500">Key: ${e.idempotency_key}</div>
          </div>
          <span class="${e.transaction_type === 'CREDIT' ? 'text-emerald-400' : 'text-amber-400'} font-bold">
            ${e.transaction_type === 'CREDIT' ? '+' : '-'}${copFormat(e.amount_cents)}
          </span>
        </div>
      `).join("") || '<div class="text-slate-500">Sin movimientos aún</div>';
    }

    async function redeemCashbackPoints() {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const res = await apiFetch("/api/v1/wallet/me/redeem-points", {
          method: "POST"
        });
        await loadWallet();
        showBanner(`🎉 ¡Puntos canjeados con éxito! Se acreditaron ${copFormat(res.entry.amount_cents)} a tu saldo de billetera COP.`);
      } catch (err) {
        showBanner("Error al canjear puntos: " + err.message, true);
      }
    }

    async function walletTransaction(action, amountCents) {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const key = `${action}-${Date.now()}`;
        await apiFetch(`/api/v1/wallet/me/${action}`, {
          method: "POST",
          body: JSON.stringify({
            amount_cents: amountCents,
            reference: action === "deposit" ? "Recarga Instantánea Dashboard" : "Retiro Dashboard",
            idempotency_key: key
          })
        });
        await loadWallet();
        showBanner(`Transacción (${action.toUpperCase()}) procesada con idempotency_key=${key}`);
      } catch (err) {
        showBanner(err.message, true);
      }
    }

    async function createProductFromDashboard() {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const sku = document.getElementById("newProdSku").value || `SKU-${Date.now()}`;
        const title = document.getElementById("newProdTitle").value || "Nuevo Producto Super App";
        const priceCop = parseInt(document.getElementById("newProdPrice").value || "95000", 10);
        const costCop = parseInt(document.getElementById("newProdCost").value || "42000", 10);
        await apiFetch("/api/v1/commerce/products", {
          method: "POST",
          body: JSON.stringify({
            sku: sku,
            title: title,
            description: "Creado desde el Centro de Control Web",
            price_cents: priceCop * 100,
            unit_cost_cents: costCop * 100,
            stock_quantity: 10
          })
        });
        await loadCatalogAndOrders();
        showBanner(`Producto '${title}' creado con COGS $${costCop.toLocaleString("es-CO")} COP.`);
      } catch (err) {
        showBanner("Error creando producto: " + err.message, true);
      }
    }

    async function restockProduct(productId, units = 5) {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const updated = await apiFetch(`/api/v1/commerce/products/${productId}/stock`, {
          method: "PATCH",
          body: JSON.stringify({ quantity_to_add: units })
        });
        await loadCatalogAndOrders();
        showBanner(`Inventario actualizado para ${updated.sku}: nuevo stock = ${updated.stock_quantity} unidades.`);
      } catch (err) {
        showBanner("Error al reabastecer stock: " + err.message, true);
      }
    }

    async function triggerDynamicPrice(productId) {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const conversions = parseInt(document.getElementById("totalConversionsBadge").textContent || "0", 10);
        const res = await apiFetch(`/api/v1/commerce/products/${productId}/dynamic-price`, {
          method: "POST",
          body: JSON.stringify({ demand_conversions: conversions })
        });
        await loadCatalogAndOrders();
        showBanner(`⚡ Precio Dinámico (${res.pricing_strategy}): ${copFormat(res.old_price_cents)} → ${copFormat(res.new_price_cents)} (Margen: ${res.product.margin_percentage}%)`);
      } catch (err) {
        showBanner("Error en precio dinámico: " + err.message, true);
      }
    }

    async function downloadWeeklyReport() {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const res = await apiFetchRaw("/api/v1/commerce/analytics/weekly-report");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const mdText = await res.text();
        const blob = new Blob([mdText], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "weekly_executive_report.md";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        showBanner("📊 Reporte Ejecutivo Semanal (.MD) descargado correctamente.");
      } catch (err) {
        showBanner("Error descargando reporte: " + err.message, true);
      }
    }

    async function shipOrderWithTracking(orderId) {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const carrier = prompt("Transportadora (ej. InterRapidísimo, Servientrega, Envía):", "InterRapidísimo");
        if (!carrier) return;
        const tracking = prompt("Número de Guía de Despacho:", `GUIA-${Date.now().toString().slice(-8)}`);
        if (!tracking) return;
        const shipped = await apiFetch(`/api/v1/commerce/orders/${orderId}/ship`, {
          method: "POST",
          body: JSON.stringify({ carrier_name: carrier, tracking_code: tracking })
        });
        await loadCatalogAndOrders();
        showBanner(`🚚 Orden #${shipped.id.slice(0, 8)} despachada vía ${shipped.carrier_name} (Guía: ${shipped.tracking_code}).`);
      } catch (err) {
        showBanner("Error al despachar orden: " + err.message, true);
      }
    }

    async function showOrderLifecycleMessages(orderId) {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const box = document.getElementById(`lifecycle-msgs-${orderId}`);
        if (box && !box.classList.contains("hidden")) {
          box.classList.add("hidden");
          return;
        }
        const data = await apiFetch(`/api/v1/commerce/orders/${orderId}/messages`);
        if (box) {
          box.innerHTML = `
            <div class="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-2 text-[11px]">
              <div class="space-y-1">
                <div class="flex justify-between items-center">
                  <span class="font-bold text-emerald-300">1. Confirmación</span>
                  <a href="${data.confirmation_whatsapp_url}" target="_blank" rel="noopener" class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-semibold">Enviar WhatsApp ↗</a>
                </div>
                <pre class="p-1.5 rounded bg-slate-900 text-slate-300 whitespace-pre-wrap">${data.confirmation_msg}</pre>
              </div>
              <div class="space-y-1">
                <div class="flex justify-between items-center">
                  <span class="font-bold text-cyan-300">2. Despacho & Guía</span>
                  <a href="${data.shipping_whatsapp_url}" target="_blank" rel="noopener" class="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-semibold">Enviar WhatsApp ↗</a>
                </div>
                <pre class="p-1.5 rounded bg-slate-900 text-slate-300 whitespace-pre-wrap">${data.shipping_msg}</pre>
              </div>
              <div class="space-y-1">
                <div class="flex justify-between items-center">
                  <span class="font-bold text-amber-300">3. Post-Entrega & Recompra 10%</span>
                  <a href="${data.post_delivery_whatsapp_url}" target="_blank" rel="noopener" class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold">Enviar WhatsApp ↗</a>
                </div>
                <pre class="p-1.5 rounded bg-slate-900 text-slate-300 whitespace-pre-wrap">${data.post_delivery_msg}</pre>
              </div>
            </div>
          `;
          box.classList.remove("hidden");
        }
        if (navigator.clipboard) {
          await navigator.clipboard.writeText(
            `${data.confirmation_msg}\\n\\n---\\n\\n${data.shipping_msg}\\n\\n---\\n\\n${data.post_delivery_msg}`
          ).catch(() => {});
        }
        showBanner(`💬 Mensajes de seguimiento (Confirmación, Guía y Post-Venta) listos para la orden #${orderId.slice(0, 8)}.`);
      } catch (err) {
        showBanner("Error obteniendo mensajes: " + err.message, true);
      }
    }

    async function markOrderDelivered(orderId) {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const delivered = await apiFetch(`/api/v1/commerce/orders/${orderId}/deliver`, {
          method: "POST"
        });
        await Promise.all([loadWallet(), loadCatalogAndOrders()]);
        showBanner(`Orden #${delivered.id.slice(0, 8)} marcada DELIVERED. Utilidad neta (${copFormat(delivered.net_profit_cents)}) liquidada en Wallet.`);
      } catch (err) {
        showBanner("Error al entregar orden: " + err.message, true);
      }
    }

    async function loadCatalogAndOrders() {
      const products = await apiFetch("/api/v1/commerce/products");
      const catalogEl = document.getElementById("catalogList");
      const selectEl = document.getElementById("jobProductSelect");
      selectEl.innerHTML = '<option value="">-- Sin producto vinculado --</option>' +
        products.map(p => `<option value="${p.id}">${p.title} (${copFormat(p.price_cents)})</option>`).join("");

      catalogEl.innerHTML = products.map(p => {
        const hasVariants = p.variants && p.variants.length > 0;
        const variantsBadges = hasVariants
          ? `<div class="flex flex-wrap gap-1 pt-1">` +
            p.variants.map(v => `<span class="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 text-[10px] font-semibold border border-blue-500/30">Talla ${v.size || v.variant_sku} (${v.stock_quantity} disp.)</span>`).join("") +
            `</div>`
          : "";
        const variantDropdown = hasVariants
          ? `<div class="pt-1">
               <label class="block text-[10px] text-blue-300 font-semibold mb-0.5">Seleccionar Variante / Talla:</label>
               <select id="variantSelect-${p.id}" class="w-full rounded-lg bg-slate-800 border border-slate-700 p-1 text-xs text-white">
                 ${p.variants.map(v => `<option value="${v.variant_sku}">Talla ${v.size || v.variant_sku} - ${v.color || 'Estándar'} (${v.stock_quantity} disponibles)</option>`).join("")}
               </select>
             </div>`
          : "";

        return `
        <div class="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
          <div class="flex justify-between items-start gap-2">
            <div>
              <div class="text-xs font-bold text-white">${p.title}</div>
              <div class="text-[11px] text-slate-400">SKU: ${p.sku} • COGS: ${copFormat(p.unit_cost_cents)} • Margen: ${p.margin_percentage}%</div>
            </div>
            <div class="flex items-center gap-1.5">
              <span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 text-xs font-bold">
                Stock: ${p.stock_quantity}
              </span>
              <button onclick="restockProduct('${p.id}', 5)" class="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-emerald-300 text-[10px] font-bold">
                +5 Stock
              </button>
            </div>
          </div>
          ${variantsBadges}
          ${variantDropdown}
          <div class="flex items-center justify-between">
            <div class="text-sm font-extrabold text-emerald-400">${copFormat(p.price_cents)}</div>
            <button onclick="triggerDynamicPrice('${p.id}')" class="py-1 px-2.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 text-[11px] font-semibold">
              ⚡ Ajuste Dinámico de Precio (IA)
            </button>
          </div>
          <div class="grid grid-cols-2 gap-2 pt-1">
            <button onclick="buyProduct('${p.id}', 'WALLET')" class="py-1.5 px-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-semibold">
              💳 Comprar con Wallet
            </button>
            <button onclick="buyProduct('${p.id}', 'CASH_ON_DELIVERY')" class="py-1.5 px-2 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 text-purple-300 text-xs font-semibold">
              🚚 Contraentrega
            </button>
          </div>
        </div>
      `;
      }).join("");

      const bundleCardEl = document.getElementById("crossSellBundleCard");
      if (products.length > 0) {
        try {
          const bundle = await apiFetch(`/api/v1/commerce/products/${products[0].id}/cross-sell`);
          if (bundle && bundle.bundle_name) {
            bundleCardEl.className = "p-3.5 rounded-xl border-2 border-purple-500/60 shadow-lg space-y-2";
            bundleCardEl.style.background = "linear-gradient(135deg, rgba(88, 28, 135, 0.4) 0%, rgba(15, 23, 42, 0.9) 100%)";
            bundleCardEl.innerHTML = `
              <div class="flex items-center justify-between">
                <span class="text-xs font-black uppercase tracking-wider text-purple-300">✨ Sugerencia de Combo IA (Cross-Selling)</span>
                <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-extrabold border border-emerald-500/30">
                  ${bundle.discount_percentage}% OFF
                </span>
              </div>
              <div class="text-xs font-bold text-white">${bundle.bundle_name}</div>
              <div class="text-[11px] text-slate-400">
                Combina <span class="text-white font-medium">${bundle.anchor_title}</span> + <span class="text-white font-medium">${bundle.complement_title}</span>
              </div>
              <div class="flex items-baseline gap-2 pt-1">
                <span class="text-sm font-black text-emerald-400">${copFormat(bundle.bundle_price_cents)}</span>
                <span class="text-xs line-through text-slate-500">${copFormat(bundle.original_total_cents)}</span>
                <span class="text-[11px] text-purple-300 font-semibold">(Ahorras ${copFormat(bundle.savings_cents)})</span>
              </div>
              <div class="pt-1">
                <button onclick="buyProductBundle('${bundle.anchor_product_id}', '${bundle.complement_product_id}', 'WALLET')" class="w-full btn btn-purple" style="font-size: 0.75rem;">
                  🛍️ Comprar Combo con 1 Clic (Wallet)
                </button>
              </div>
            `;
          } else {
            bundleCardEl.className = "hidden";
          }
        } catch (_) {
          bundleCardEl.className = "hidden";
        }
      } else {
        bundleCardEl.className = "hidden";
      }

      if (accessToken) {
        const [orders, summary] = await Promise.all([
          apiFetch("/api/v1/commerce/orders/me"),
          apiFetch("/api/v1/commerce/analytics/summary")
        ]);
        document.getElementById("invCostVal").textContent = copFormat(summary.inventory_cost_value_cents);
        document.getElementById("invRetailVal").textContent = `Valor Venta Potencial: ${copFormat(summary.inventory_retail_value_cents)}`;
        document.getElementById("netProfitVal").textContent = copFormat(summary.realized_net_profit_cents);
        document.getElementById("grossRevVal").textContent = `Ingresos Brutos: ${copFormat(summary.gross_revenue_cents)}`;

        document.getElementById("ordersList").innerHTML = orders.map(o => `
          <div class="p-2.5 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
            <div class="flex justify-between items-center">
              <div>
                <div class="font-semibold text-white">${o.items.map(i => i.title).join(", ")}</div>
                <div class="text-[10px] text-slate-400">
                  ${o.payment_method} • <span class="font-bold text-cyan-300">${o.status}</span> • Ganancia Neta: ${copFormat(o.net_profit_cents)}
                  ${o.coupon_code ? ` • 🎟️ ${o.coupon_code} (-${copFormat(o.discount_cents)})` : ""}
                  ${o.carrier_name ? ` • 🚚 ${o.carrier_name} (${o.tracking_code})` : ""}
                </div>
              </div>
              <span class="text-purple-300 font-bold">${copFormat(o.total_cents)}</span>
            </div>
            <div class="grid grid-cols-2 gap-1.5">
              ${o.status === "CONFIRMED" ? `
                <button onclick="shipOrderWithTracking('${o.id}')" class="py-1.5 px-2 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-300 font-semibold text-[11px]">
                  🚚 Despachar con Guía
                </button>
              ` : `
                <a href="${o.whatsapp_checkout_url}" target="_blank" rel="noopener" class="block text-center py-1.5 px-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 font-semibold text-[11px]">
                  📲 Enviar Orden por WhatsApp
                </a>
              `}
              ${o.status !== "DELIVERED" ? `
                <button onclick="markOrderDelivered('${o.id}')" class="py-1.5 px-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 font-semibold text-[11px]">
                  📦 Marcar Entregado & Liquidar
                </button>
              ` : `
                <span class="block text-center py-1.5 px-2 rounded-lg bg-slate-800 text-emerald-400 font-semibold text-[11px]">
                  ✅ Entregado y Liquidado
                </span>
              `}
            </div>
            <button onclick="showOrderLifecycleMessages('${o.id}')" class="w-full py-1.5 px-2 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 text-purple-200 font-semibold text-[11px]">
              💬 Copiar / Enviar Mensajes de Seguimiento (Confirmación, Guía, Post-Venta)
            </button>
            <div id="lifecycle-msgs-${o.id}" class="hidden"></div>
          </div>
        `).join("") || '<div class="text-slate-500">Sin órdenes registradas</div>';
      }
    }

    async function buyProduct(productId, paymentMethod) {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const sourceJobId = document.getElementById("orderSourceJobSelect").value || null;
        const couponInput = document.getElementById("orderCouponCodeInput");
        const couponCode = couponInput && couponInput.value.trim() ? couponInput.value.trim().toUpperCase() : null;
        const variantSelect = document.getElementById("variantSelect-" + productId);
        const variantSku = variantSelect && variantSelect.value ? variantSelect.value : null;

        const order = await apiFetch("/api/v1/commerce/orders", {
          method: "POST",
          body: JSON.stringify({
            items: [{
              product_id: productId,
              quantity: 1,
              ...(variantSku ? { variant_sku: variantSku } : {})
            }],
            payment_method: paymentMethod,
            shipping_address: "Calle 93 #11-27, Bogotá, Colombia",
            idempotency_key: `order-${paymentMethod.toLowerCase()}-${Date.now()}`,
            shipping_cost_cents: 1200000,
            source_job_id: sourceJobId,
            coupon_code: couponCode
          })
        });
        await Promise.all([loadWallet(), loadCatalogAndOrders(), loadMediaJobs()]);
        const discountNote = order.discount_cents > 0 ? ` (Cupón ${order.coupon_code}: -${copFormat(order.discount_cents)})` : "";
        showBanner(`Orden #${order.id.slice(0, 8)} confirmada vía ${paymentMethod}${discountNote}. Ganancia neta proyectada: ${copFormat(order.net_profit_cents)}.`);
      } catch (err) {
        showBanner("Error en compra: " + err.message, true);
      }
    }

    async function buyProductBundle(anchorId, complementId, paymentMethod = 'WALLET') {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const sourceJobId = document.getElementById("orderSourceJobSelect").value || null;
        const couponInput = document.getElementById("orderCouponCodeInput");
        const couponCode = couponInput && couponInput.value.trim() ? couponInput.value.trim().toUpperCase() : null;
        const idempotencyKey = `bundle-order-${paymentMethod.toLowerCase()}-${Date.now()}`;

        const order = await apiFetch("/api/v1/commerce/orders", {
          method: "POST",
          body: JSON.stringify({
            items: [
              { product_id: anchorId, quantity: 1 },
              { product_id: complementId, quantity: 1 }
            ],
            payment_method: paymentMethod,
            shipping_address: "Calle 93 #11-27, Bogotá, Colombia",
            idempotency_key: idempotencyKey,
            shipping_cost_cents: 1200000,
            source_job_id: sourceJobId,
            coupon_code: couponCode
          })
        });
        await Promise.all([loadWallet(), loadCatalogAndOrders(), loadMediaJobs()]);
        const discountNote = order.discount_cents > 0 ? ` (Cupón ${order.coupon_code}: -${copFormat(order.discount_cents)})` : "";
        showBanner(`🎉 ¡Combo #${order.id.slice(0, 8)} pedido con éxito! Total: ${copFormat(order.total_cents)}${discountNote}. Ganancia neta: ${copFormat(order.net_profit_cents)}.`);
      } catch (err) {
        showBanner("Error en compra de combo: " + err.message, true);
      }
    }

    async function scheduleJobSlot(jobId, slotName) {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const scheduled = await apiFetch(`/api/v1/media-ai/jobs/${jobId}/schedule`, {
          method: "POST",
          body: JSON.stringify({
            platform: "TIKTOK",
            slot: slotName
          })
        });
        await loadMediaJobs();
        showBanner(`Video agendado en ${scheduled.slot} para ${scheduled.scheduled_date}. Invitación .ICS lista para Google Calendar.`);
      } catch (err) {
        showBanner("Error al agendar franja: " + err.message, true);
      }
    }

    async function enqueueStudioJob() {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const jobType = document.getElementById("jobTypeSelect").value;
        const contentNiche = document.getElementById("contentNicheSelect").value;
        const source = document.getElementById("jobSourceInput").value;
        const linkedProd = document.getElementById("jobProductSelect").value || null;
        const useRealPipeline = document.getElementById("useRealPipelineCheck").checked;
        const burnSubtitles = document.getElementById("burnSubtitlesCheck").checked;
        const queued = await apiFetch("/api/v1/media-ai/jobs", {
          method: "POST",
          body: JSON.stringify({
            job_type: jobType,
            content_niche: contentNiche,
            source_url_or_prompt: source,
            linked_product_id: linkedProd,
            use_real_pipeline: useRealPipeline,
            burn_subtitles: burnSubtitles
          })
        });
        showBanner(`Job #${queued.id.slice(0, 8)} (${contentNiche}) encolado (202 Accepted). Procesando en segundo plano...`);
        await loadMediaJobs();
        setTimeout(loadMediaJobs, 300);
      } catch (err) {
        showBanner("Error al encolar Job: " + err.message, true);
      }
    }

    async function purgeExpiredMediaArtifacts(retentionDays = 30) {
      if (!accessToken) return showBanner("Primero haz clic en Auto-Login Demo.", true);
      try {
        const res = await apiFetch(`/api/v1/media-ai/maintenance/cleanup?retention_days=${retentionDays}`, {
          method: "POST"
        });
        const kb = (res.bytes_reclaimed / 1024).toFixed(2);
        showBanner(
          `🧹 Purga completada (>${res.retention_days}d): ${res.jobs_scanned} jobs escaneados, ` +
          `${res.files_deleted} archivos eliminados, ${kb} KB liberados (${res.bytes_reclaimed} bytes). ` +
          `Métricas ROI conservadas: ${res.retained_metrics_count}.`
        );
        await loadMediaJobs();
      } catch (err) {
        showBanner("Error al purgar artefactos antiguos: " + err.message, true);
      }
    }

    async function loadMediaJobs() {
      if (!accessToken) return;
      const [jobs, schedule, nicheAnalytics] = await Promise.all([
        apiFetch("/api/v1/media-ai/jobs"),
        apiFetch("/api/v1/media-ai/schedule"),
        apiFetch("/api/v1/media-ai/analytics/by-niche")
      ]);

      document.getElementById("streakBadge").textContent =
        `${schedule.scheduled_today_count}/${schedule.daily_goal}` + (schedule.goal_completed ? " ✅" : "");
      document.getElementById("totalConversionsBadge").textContent = schedule.total_conversions;
      document.getElementById("totalRevenueBadge").textContent = copFormat(schedule.total_revenue_attributed_cents);

      document.getElementById("topNicheBadge").textContent =
        nicheAnalytics.top_performing_niche
          ? `🏆 Vertical Líder: ${nicheAnalytics.top_performing_niche}`
          : "Vertical Líder: Sin ventas atribuidas aún";

      document.getElementById("nicheAnalyticsGrid").innerHTML = nicheAnalytics.niches.map(n => `
        <div class="p-3 rounded-xl bg-slate-900 border ${nicheAnalytics.top_performing_niche === n.content_niche ? 'border-emerald-500/50' : 'border-slate-800'} space-y-1">
          <div class="font-bold text-white flex justify-between items-center">
            <span>${n.content_niche}</span>
            ${nicheAnalytics.top_performing_niche === n.content_niche ? '<span class="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px]">TOP ROI</span>' : ''}
          </div>
          <div class="text-sm font-extrabold text-emerald-400">${copFormat(n.revenue_attributed_cents)}</div>
          <div class="text-[11px] text-slate-400">
            Videos: <span class="text-white font-semibold">${n.total_videos_created}</span> (${n.total_videos_scheduled} agendados)
          </div>
          <div class="text-[11px] text-slate-400">
            Ventas: <span class="text-cyan-300 font-semibold">${n.conversions_count}</span> • Tasa: <span class="text-amber-300 font-semibold">${n.conversions_per_video} conv/video</span>
          </div>
        </div>
      `).join("");

      const sourceSelect = document.getElementById("orderSourceJobSelect");
      const currentVal = sourceSelect.value;
      sourceSelect.innerHTML = '<option value="">-- Compra directa (sin atribución de video) --</option>' +
        jobs.map(j => `<option value="${j.id}">🎬 ${j.job_type} (${j.content_niche}) #${j.id.slice(0, 6)}</option>`).join("");
      sourceSelect.value = currentVal;

      document.getElementById("scheduleList").innerHTML = schedule.scheduled_posts.map(p => `
        <div class="p-2.5 rounded-lg bg-slate-900 border border-cyan-500/30 flex justify-between items-center">
          <div>
            <div class="font-bold text-white">${p.platform} • ${p.slot} (${p.scheduled_date})</div>
            <div class="text-[10px] text-emerald-400">Ventas: ${p.conversions_count} • Ingresos: ${copFormat(p.revenue_attributed_cents)}</div>
          </div>
          <a href="${p.ics_download_url}" download="publish_${p.job_id}.ics" class="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 font-semibold text-[10px]">
            🗓️ Descargar .ICS (Google Calendar)
          </a>
        </div>
      `).join("") || '<div class="text-slate-500">Aún no has agendado videos hoy</div>';

      document.getElementById("jobsList").innerHTML = jobs.map(j => {
        const p = j.result_payload || {};
        const hook = p.ugc_hook_0_3s || p.hook || null;
        const body = p.ugc_body_3_12s || p.body || null;
        const cta = p.ugc_cta_12_15s || p.cta || null;
        const combo = p.smart_combo_recommendation || null;
        const audioPeak = (p.audio_peak_timestamp !== undefined && p.audio_peak_timestamp !== null) ? p.audio_peak_timestamp : null;

        const statusBadge = j.status === "COMPLETED"
          ? '<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-bold border border-emerald-500/30">✅ COMPLETADO</span>'
          : j.status === "PROCESSING"
          ? '<span class="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 text-[10px] font-bold border border-cyan-500/30">⏳ PROCESANDO (' + j.progress_percent + '%)</span>'
          : '<span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-bold">' + j.status + ' (' + j.progress_percent + '%)</span>';

        const scriptSection = (hook || cta || combo || audioPeak !== null) ? `
          <div class="script-box">
            ${hook ? `
              <div class="script-row">
                <span class="tag-badge tag-hook">🎯 Hook 0-3s</span>
                <span class="text-white font-medium">${hook}</span>
              </div>
            ` : ""}
            ${body ? `
              <div class="script-row">
                <span class="tag-badge" style="background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3);">📝 Guion</span>
                <span class="text-slate-300">${body.length > 140 ? body.slice(0, 140) + '...' : body}</span>
              </div>
            ` : ""}
            ${cta ? `
              <div class="script-row">
                <span class="tag-badge tag-cta">📣 CTA Final</span>
                <span class="text-cyan-200 font-medium">${cta}</span>
              </div>
            ` : ""}
            ${audioPeak !== null ? `
              <div class="script-row">
                <span class="tag-badge tag-audio">🎵 Clímax Audio</span>
                <span class="text-emerald-300">Corte iniciado en ${audioPeak}s</span>
              </div>
            ` : ""}
            ${combo ? `
              <div class="script-row">
                <span class="tag-badge tag-combo">✨ Combo Sugerido</span>
                <span class="text-purple-200 font-medium">${combo.bundle_name || 'Combo complementario vinculado'}</span>
              </div>
            ` : ""}
          </div>
        ` : "";

        return `
        <div class="job-card">
          <div class="job-header">
            <div>
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-bold text-cyan-300 text-xs">${j.job_type}</span>
                <span class="px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[10px] font-semibold">${j.content_niche}</span>
                ${j.linked_product_id ? `<span class="px-1.5 py-0.5 rounded bg-purple-500/15 border border-purple-500/30 text-purple-300 text-[10px]">🔗 Prod #${j.linked_product_id.slice(0, 6)}</span>` : '<span class="text-[10px] text-slate-500">Sin producto vinculado</span>'}
              </div>
              <div class="text-[10px] text-slate-500 mt-1">ID: ${j.id.slice(0, 8)} • Pipeline: ${j.use_real_pipeline ? 'yt-dlp + FFmpeg' : 'Synthetic 9:16'} • Subtítulos: ${j.burn_subtitles ? 'TikTok Burn' : 'Solo SRT'}</div>
            </div>
            ${statusBadge}
          </div>

          <div class="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div class="${j.status === 'COMPLETED' ? 'bg-emerald-400' : 'bg-cyan-400'} h-full transition-all" style="width: ${j.progress_percent}%"></div>
          </div>

          ${scriptSection}

          <!-- Botones de Agendamiento y Descarga -->
          <div class="flex flex-wrap gap-2 pt-1">
            <button onclick="scheduleJobSlot('${j.id}', 'SLOT_1_MIDDAY')" class="btn btn-amber-outline btn-sm">
              📅 Agendar Franja 1 (12:30)
            </button>
            <button onclick="scheduleJobSlot('${j.id}', 'SLOT_2_EVENING')" class="btn btn-amber-outline btn-sm">
              📅 Agendar Franja 2 (19:30)
            </button>
            ${j.status === "COMPLETED" ? `
              <a href="/api/v1/media-ai/jobs/${j.id}/download-srt" download="captions_${j.id}.srt" class="btn btn-cyan-outline btn-sm">
                ⬇ .SRT (CapCut)
              </a>
              <a href="/api/v1/media-ai/jobs/${j.id}/download-pack" download="script_${j.id}.md" class="btn btn-purple-outline btn-sm">
                📄 Guion (.MD)
              </a>
              <a href="/api/v1/media-ai/jobs/${j.id}/download-mp4" download="short_9x16_${j.id}.mp4" class="btn btn-emerald-outline btn-sm">
                🎥 Descargar Short Listo para TikTok (.MP4)
              </a>
            ` : ""}
          </div>

          <!-- Payload Técnico Colapsable -->
          ${j.result_payload ? `
            <details style="margin-top: 0.25rem;">
              <summary style="cursor: pointer; font-size: 0.65rem; color: var(--text-dim); user-select: none;">
                ⚙️ Ver Payload Técnico JSON (${Object.keys(j.result_payload).length} campos)
              </summary>
              <pre style="margin-top: 0.35rem; padding: 0.5rem; border-radius: 0.5rem; background: #020617; border: 1px solid var(--border-subtle); color: #94a3b8; max-height: 180px; overflow: auto; font-size: 0.65rem; line-height: 1.3;">${JSON.stringify(j.result_payload, null, 2)}</pre>
            </details>
          ` : ""}
        </div>
      `;
      }).join("") || '<div class="text-slate-500">Sin trabajos en cola</div>';
    }

    async function initDashboard() {
      loadStoredTokens();
      if (accessToken || refreshToken) {
        try {
          const me = await apiFetch("/api/v1/identity/me");
          await syncAuthenticatedDashboard(me, true);
          return;
        } catch (_) {
          clearSessionTokens(false);
        }
      }
      await loadCatalogAndOrders();
    }

    initDashboard();
  </script>
</body>
</html>
"""


@router.get("/dashboard", response_class=HTMLResponse)
async def control_center_dashboard() -> HTMLResponse:
    """Serves the interactive Super App Control Center web UI."""
    return HTMLResponse(content=DASHBOARD_HTML, status_code=200)
