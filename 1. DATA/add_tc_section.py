import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')

HTML_PATH = 'D:/코딩/work for_/dashboard-app/preview/index.html'

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

# ── 1. Sidebar nav item ──────────────────────────────────────────────
NAV_PERSON = """      <div class="nav-item admin-only" data-view="view-person" onclick="showView('view-person')">
        <i data-lucide="users"></i>
        <span>개인별 청구</span>
      </div>"""

NAV_TC = """      <div class="nav-item admin-only" data-view="view-tc" onclick="showView('view-tc')">
        <i data-lucide="percent"></i>
        <span>TC 미실시율</span>
      </div>"""

if 'data-view="view-tc"' not in html:
    html = html.replace(NAV_PERSON, NAV_PERSON + '\n\n' + NAV_TC, 1)
    print('✓ 사이드바 nav 추가')
else:
    print('- 사이드바 nav 이미 존재')

# ── 2. View HTML ─────────────────────────────────────────────────────
VIEW_ANCHOR = '      </div><!-- /view-person -->'

VIEW_TC_HTML = VIEW_ANCHOR + """

      <!-- =============================================
           뷰: TC 미실시율
           ============================================= -->
      <div id="view-tc" class="view hidden">
        <div class="sales-card p-5 mb-4">
          <div class="flex flex-wrap gap-6 items-start">
            <div>
              <span class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">지점</span>
              <div class="flex gap-2 flex-wrap">
                <button onclick="toggleTcBranch('all')" id="tc-fbranch-all" class="sales-pill active">전체</button>
                <button onclick="toggleTcBranch('군산')" id="tc-fbranch-군산" class="sales-pill">군산</button>
                <button onclick="toggleTcBranch('목포')" id="tc-fbranch-목포" class="sales-pill">목포</button>
                <button onclick="toggleTcBranch('서산')" id="tc-fbranch-서산" class="sales-pill">서산</button>
                <button onclick="toggleTcBranch('전주')" id="tc-fbranch-전주" class="sales-pill">전주</button>
                <button onclick="toggleTcBranch('평택')" id="tc-fbranch-평택" class="sales-pill">평택</button>
              </div>
            </div>
          </div>
        </div>
        <div id="tc-kpi-row" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-4"></div>
        <div class="sales-card p-5 mb-4">
          <h2 class="text-sm font-semibold text-slate-300 mb-3">월별 미실시율 추이 (%)</h2>
          <div style="height:300px;"><canvas id="tc-trend-chart"></canvas></div>
        </div>
        <div class="sales-card p-5">
          <h2 class="text-sm font-semibold text-slate-300 mb-3">지점별 상세</h2>
          <div id="tc-table-wrap" class="overflow-x-auto"></div>
        </div>
      </div><!-- /view-tc -->"""

if 'id="view-tc"' not in html:
    html = html.replace(VIEW_ANCHOR, VIEW_TC_HTML, 1)
    print('✓ view-tc HTML 추가')
else:
    print('- view-tc HTML 이미 존재')

# ── 3. showView() title + render ─────────────────────────────────────
OLD_TITLES = "      'view-person':           '개인별 청구 현황',"
NEW_TITLES = "      'view-person':           '개인별 청구 현황',\n      'view-tc':               'TC 미실시율',"
if "'view-tc'" not in html:
    html = html.replace(OLD_TITLES, NEW_TITLES, 1)
    print('✓ title map 추가')

OLD_RENDER = "    if (viewId === 'view-person') renderPersonChart();"
NEW_RENDER = "    if (viewId === 'view-person') renderPersonChart();\n    if (viewId === 'view-tc') renderTcView();"
if 'renderTcView' not in html:
    html = html.replace(OLD_RENDER, NEW_RENDER, 1)
    print('✓ renderTcView 호출 추가')

# ── 4. TC_DATA constant ───────────────────────────────────────────────
with open('D:/코딩/work for_/1. DATA/tc_data.json', encoding='utf-8') as f:
    tc_data = json.load(f)
tc_js = 'const TC_DATA=' + json.dumps(tc_data, ensure_ascii=False, separators=(',',':')) + ';'

if 'const TC_DATA=' not in html:
    idx = html.find('const PERSON_DATA=')
    end = html.find('];', idx) + 2
    html = html[:end] + '\n' + tc_js + html[end:]
    print('✓ TC_DATA 상수 추가')
else:
    html = re.sub(r'const TC_DATA=\{.*?\};', tc_js, html, flags=re.DOTALL)
    print('✓ TC_DATA 상수 교체')

# ── 5. renderTcView() JS function ─────────────────────────────────────
PERSON_NAMES_LINE = '  const PERSON_NAMES = {};'

TC_JS = r"""  const PERSON_NAMES = {};

  // ===================== TC 미실시율 =====================
  const TC_BRANCHES = ['군산','목포','서산','전주','평택'];
  const TC_BRANCH_COLORS = {
    '군산': '#1d4ed8', '목포': '#0891b2', '서산': '#059669',
    '전주': '#7c3aed', '평택': '#d97706'
  };
  let tcActiveBranches = new Set(['군산','목포','서산','전주','평택']);
  let tcTrendChart = null;

  function toggleTcBranch(branch) {
    if (branch === 'all') {
      tcActiveBranches = new Set(TC_BRANCHES);
    } else {
      tcActiveBranches = new Set([branch]);
    }
    document.querySelectorAll('[id^="tc-fbranch-"]').forEach(el => el.classList.remove('active'));
    if (tcActiveBranches.size === TC_BRANCHES.length) {
      document.getElementById('tc-fbranch-all').classList.add('active');
    } else {
      tcActiveBranches.forEach(b => {
        const el = document.getElementById('tc-fbranch-' + b);
        if (el) el.classList.add('active');
      });
    }
    renderTcView();
  }

  function renderTcView() {
    const activeBranches = tcActiveBranches.size === TC_BRANCHES.length
      ? TC_BRANCHES : [...tcActiveBranches];

    const allMonths = new Set();
    TC_BRANCHES.forEach(b => { if (TC_DATA[b]) Object.keys(TC_DATA[b]).forEach(m => allMonths.add(m)); });
    const months = [...allMonths].sort();

    // KPI 카드
    const kpiRow = document.getElementById('tc-kpi-row');
    kpiRow.innerHTML = '';
    TC_BRANCHES.forEach(b => {
      if (!TC_DATA[b]) return;
      const vals = Object.values(TC_DATA[b]);
      const total = vals.reduce((s, v) => s + v.total, 0);
      const n = vals.reduce((s, v) => s + v.n_count, 0);
      const rate = total ? (n / total * 100).toFixed(1) : '-';
      const isActive = tcActiveBranches.has(b) || tcActiveBranches.size === TC_BRANCHES.length;
      kpiRow.innerHTML += '<div class="sales-card p-4 cursor-pointer ' + (isActive ? '' : 'opacity-40') + '" onclick="toggleTcBranch(\'' + b + '\')">'
        + '<div class="text-[11px] text-slate-400 mb-1">' + b + '</div>'
        + '<div class="text-2xl font-bold" style="color:' + TC_BRANCH_COLORS[b] + '">' + rate + '%</div>'
        + '<div class="text-[10px] text-slate-500 mt-1">N ' + n.toLocaleString() + ' / ' + total.toLocaleString() + '</div>'
        + '</div>';
    });

    // 월별 추이 차트
    const datasets = activeBranches.map(b => ({
      label: b,
      data: months.map(m => {
        const v = TC_DATA[b] && TC_DATA[b][m];
        return v ? parseFloat((v.n_count / v.total * 100).toFixed(1)) : null;
      }),
      borderColor: TC_BRANCH_COLORS[b],
      backgroundColor: TC_BRANCH_COLORS[b] + '33',
      tension: 0.3, fill: false, pointRadius: 5, pointHoverRadius: 7,
    }));

    if (tcTrendChart) tcTrendChart.destroy();
    const ctx = document.getElementById('tc-trend-chart').getContext('2d');
    tcTrendChart = new Chart(ctx, {
      type: 'line',
      data: { labels: months, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
          tooltip: { callbacks: { label: ctx => ' ' + ctx.dataset.label + ': ' + ctx.raw + '%' } },
          datalabels: {
            color: '#ffffff', font: { size: 10, weight: 'bold' },
            formatter: v => v !== null ? v + '%' : '',
            anchor: 'top', align: 'top',
          }
        },
        scales: {
          x: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } },
          y: { ticks: { color: '#94a3b8', callback: v => v + '%' }, grid: { color: '#334155' }, min: 0, max: 100 }
        }
      }
    });

    // 상세 테이블
    const wrap = document.getElementById('tc-table-wrap');
    let th = '<tr><th class="text-left px-3 py-2 text-slate-400 text-xs font-semibold">지점</th>';
    months.forEach(m => { th += '<th class="px-3 py-2 text-slate-400 text-xs font-semibold text-center">' + m + '</th>'; });
    th += '<th class="px-3 py-2 text-slate-400 text-xs font-semibold text-center">전체</th></tr>';
    let rows = '';
    TC_BRANCHES.forEach(b => {
      if (!TC_DATA[b]) return;
      const isActive = tcActiveBranches.has(b) || tcActiveBranches.size === TC_BRANCHES.length;
      let row = '<tr class="' + (isActive ? '' : 'opacity-40') + '">';
      row += '<td class="px-3 py-2 text-sm font-semibold" style="color:' + TC_BRANCH_COLORS[b] + '">' + b + '</td>';
      let tot = 0, nTot = 0;
      months.forEach(m => {
        const v = TC_DATA[b] && TC_DATA[b][m];
        if (v) {
          const r = (v.n_count / v.total * 100).toFixed(1);
          row += '<td class="px-3 py-2 text-center text-sm text-slate-300">' + r + '%<br><span class="text-[10px] text-slate-500">' + v.n_count + '/' + v.total + '</span></td>';
          tot += v.total; nTot += v.n_count;
        } else {
          row += '<td class="px-3 py-2 text-center text-slate-600">-</td>';
        }
      });
      const totalRate = tot ? (nTot / tot * 100).toFixed(1) + '%' : '-';
      row += '<td class="px-3 py-2 text-center text-sm font-bold text-white">' + totalRate + '<br><span class="text-[10px] text-slate-500">' + nTot + '/' + tot + '</span></td></tr>';
      rows += row;
    });
    wrap.innerHTML = '<table class="w-full border-collapse"><thead class="bg-slate-800">' + th + '</thead><tbody class="divide-y divide-slate-700">' + rows + '</tbody></table>';
  }
  // ===================== /TC 미실시율 ====================="""

if 'renderTcView' not in html:
    html = html.replace(PERSON_NAMES_LINE, TC_JS, 1)
    print('✓ renderTcView() 함수 추가')
else:
    print('- renderTcView() 이미 존재')

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'\n✓ HTML 저장 완료: {len(html)/1024:.1f}KB')
