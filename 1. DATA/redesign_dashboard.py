import sys, re
sys.stdout.reconfigure(encoding='utf-8')

HTML_PATH = 'c:/Users/user/Desktop/work for_/dashboard-app/preview/index.html'
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

# ── 1. view-dashboard HTML 교체 ────────────────────────────────────────
OLD_DASH = html[html.index('      <div id="view-dashboard" class="view">'):html.index('      </div><!-- /view-dashboard -->')+len('      </div><!-- /view-dashboard -->')]

NEW_DASH = '''      <div id="view-dashboard" class="view">

        <!-- KPI 타일 4개 -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5" id="dash-kpi-row">
          <!-- JS로 채움 -->
        </div>

        <!-- 중간: 지점별 보증 현황 + TC 미실시율 -->
        <div class="grid grid-cols-3 gap-4 mb-5">

          <!-- 지점별 보증 청구 현황 -->
          <div class="col-span-2 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden" style="border-top:3px solid #1d4ed8">
            <div class="px-5 py-3 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
              <h2 class="text-sm font-bold text-slate-700 dark:text-white">지점별 보증 청구 현황</h2>
              <span id="dash-branch-month" class="text-xs px-2 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 rounded-full font-medium"></span>
            </div>
            <div id="dash-branch-table"></div>
          </div>

          <!-- TC 미실시율 -->
          <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden" style="border-top:3px solid #ef4444">
            <div class="px-5 py-3 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
              <h2 class="text-sm font-bold text-slate-700 dark:text-white">TC 미실시율</h2>
              <span class="text-xs text-slate-400">목표 <b class="text-yellow-500">35%</b></span>
            </div>
            <div id="dash-tc-table" class="px-5 py-4"></div>
          </div>
        </div>

        <!-- 하단: TOP 결함코드 + 타입별 현황 -->
        <div class="grid grid-cols-3 gap-4">

          <!-- TOP 10 결함코드 -->
          <div class="col-span-2 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden" style="border-top:3px solid #059669">
            <div class="px-5 py-3 border-b border-slate-100 dark:border-slate-700">
              <h2 class="text-sm font-bold text-slate-700 dark:text-white">TOP 10 결함코드 <span class="text-xs font-normal text-slate-400 ml-1">전체 기간</span></h2>
            </div>
            <div class="p-4" style="height:290px"><canvas id="dash-defect-chart"></canvas></div>
          </div>

          <!-- 타입별 현황 -->
          <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden" style="border-top:3px solid #7c3aed">
            <div class="px-5 py-3 border-b border-slate-100 dark:border-slate-700">
              <h2 class="text-sm font-bold text-slate-700 dark:text-white">타입별 청구 현황 <span class="text-xs font-normal text-slate-400 ml-1">전체 기간</span></h2>
            </div>
            <div id="dash-type-table" class="px-5 py-3"></div>
          </div>
        </div>

      </div><!-- /view-dashboard -->'''

html = html.replace(OLD_DASH, NEW_DASH, 1)
print('✓ view-dashboard HTML 교체')

# ── 2. showView: initDashboardSort → initDashboard ────────────────────
html = html.replace(
    "if (viewId === 'view-dashboard') setTimeout(initDashboardSort, 50);",
    "if (viewId === 'view-dashboard') setTimeout(initDashboard, 50);"
)
print('✓ showView 콜백 교체')

# ── 3. initDashboardSort 함수 교체 ────────────────────────────────────
OLD_SORT_START = '  function initDashboardSort() {'
OLD_SORT_END   = '  }\n\n  function initSalesChart() {'
idx_start = html.index(OLD_SORT_START)
idx_end   = html.index(OLD_SORT_END) + len('  }\n\n')
OLD_SORT_BLOCK = html[idx_start:idx_end]

NEW_INIT_DASH = r"""  let _dashDefectChart = null;

  function initDashboard() {
    const BRANCH_ORDER = ['전주','평택','군산','목포','서산'];
    const TYPE_COLORS  = {'BSI':'#1d4ed8','Warranty':'#0891b2','TC/RECALL':'#059669','Goodwill':'#7c3aed','WP':'#d97706','LOCAL TC':'#dc2626'};
    const TYPES_ORDER  = ['BSI','Warranty','TC/RECALL','WP','LOCAL TC','Goodwill'];

    // ── 최근월 탐색 ──
    const allMonths = new Set();
    BRANCH_ORDER.forEach(b => { if(BRANCH_DATA[b]) Object.keys(BRANCH_DATA[b]).forEach(m => allMonths.add(m)); });
    const sortedMonths = [...allMonths].sort();
    const latestMonth  = sortedMonths[sortedMonths.length - 1];
    const prevMonth    = sortedMonths[sortedMonths.length - 2] || null;

    // ── 최근월 지점별 집계 ──
    let totalCount = 0, totalAmount = 0;
    let prevTotalCount = 0;
    const branchStats = {};
    BRANCH_ORDER.forEach(b => {
      const md = (BRANCH_DATA[b] && BRANCH_DATA[b][latestMonth]) || {};
      let cnt = 0, amt = 0;
      Object.values(md).forEach(v => { cnt += v.count; amt += v.total; });
      branchStats[b] = {count: cnt, amount: amt};
      totalCount  += cnt;
      totalAmount += amt;
      if (prevMonth && BRANCH_DATA[b] && BRANCH_DATA[b][prevMonth]) {
        Object.values(BRANCH_DATA[b][prevMonth]).forEach(v => { prevTotalCount += v.count; });
      }
    });
    const countChange = prevTotalCount ? ((totalCount - prevTotalCount) / prevTotalCount * 100).toFixed(1) : null;

    // ── TC 최근월 ──
    const tcMonths = new Set();
    BRANCH_ORDER.forEach(b => { if(TC_DATA[b]) Object.keys(TC_DATA[b]).forEach(m => tcMonths.add(m)); });
    const latestTcMonth = [...tcMonths].sort().pop() || '';
    let tcN = 0, tcTotal = 0;
    BRANCH_ORDER.forEach(b => {
      const v = TC_DATA[b] && TC_DATA[b][latestTcMonth];
      if (v) { tcN += v.n_count; tcTotal += v.total; }
    });
    const tcRate = tcTotal ? (tcN / tcTotal * 100).toFixed(1) : '-';
    const tcOver = tcRate !== '-' && parseFloat(tcRate) > 35;

    // ── TOP 결함코드 (전체) ──
    const codeStats = {};
    DEFECT_RAW.forEach(r => { codeStats[r[3]] = (codeStats[r[3]] || 0) + r[4]; });
    const topEntry = Object.entries(codeStats).sort((a,b) => b[1]-a[1])[0] || ['-', 0];

    // ── KPI 카드 ──
    const kpiRow = document.getElementById('dash-kpi-row');
    if (!kpiRow) return;
    const kpis = [
      { label:'청구 건수',   sub: latestMonth,   value: totalCount.toLocaleString(), unit:'건',
        change: countChange, icon:'file-text', color:'#1d4ed8', bg:'#eff6ff' },
      { label:'청구 금액',   sub: latestMonth,   value: (totalAmount/1000000).toFixed(0), unit:'백만원',
        icon:'circle-dollar-sign', color:'#0891b2', bg:'#ecfeff' },
      { label:'TC 미실시율', sub: latestTcMonth, value: tcRate, unit:'%',
        icon:'percent', color: tcOver ? '#ef4444' : '#059669', bg: tcOver ? '#fef2f2' : '#f0fdf4' },
      { label:'TOP 결함코드', sub: (DEFECT_DESC[topEntry[0]] || topEntry[0]).slice(0,18),
        value: topEntry[1].toLocaleString(), unit:'건',
        icon:'alert-triangle', color:'#d97706', bg:'#fffbeb' },
    ];
    kpiRow.innerHTML = kpis.map(k => {
      const chg = k.change ? (parseFloat(k.change) >= 0
        ? '<div class="text-xs mt-2 text-emerald-500">↑ ' + k.change + '% 전월 대비</div>'
        : '<div class="text-xs mt-2 text-red-400">↓ ' + Math.abs(k.change) + '% 전월 대비</div>')
        : '<div class="h-4 mt-2"></div>';
      return '<div class="bg-white dark:bg-slate-800 rounded-xl p-5 shadow-sm border border-slate-200 dark:border-slate-700" style="border-left:4px solid ' + k.color + '">'
        + '<div class="flex items-start justify-between mb-3">'
        +   '<div><div class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">' + k.label + '</div>'
        +   '<div class="text-[10px] text-slate-400 mt-0.5 truncate max-w-[120px]">' + k.sub + '</div></div>'
        +   '<div class="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style="background:' + k.bg + '">'
        +     '<i data-lucide="' + k.icon + '" class="w-5 h-5" style="color:' + k.color + '"></i>'
        +   '</div>'
        + '</div>'
        + '<div class="text-3xl font-bold text-slate-800 dark:text-white">' + k.value
        +   '<span class="text-sm font-normal text-slate-400 ml-1">' + k.unit + '</span></div>'
        + chg
        + '</div>';
    }).join('');

    // ── 지점별 보증 현황 테이블 ──
    document.getElementById('dash-branch-month').textContent = latestMonth;
    const maxCount = Math.max(...Object.values(branchStats).map(s => s.count), 1);
    let tbl = '<table class="w-full text-sm">'
      + '<thead><tr class="bg-slate-50 dark:bg-slate-700/40">'
      + '<th class="px-4 py-2.5 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase">지점</th>'
      + '<th class="px-4 py-2.5 text-right text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase">건수</th>'
      + '<th class="px-4 py-2.5 text-right text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase">금액 (백만)</th>'
      + '<th class="px-4 py-2.5 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase w-36">비율</th>'
      + '</tr></thead><tbody class="divide-y divide-slate-100 dark:divide-slate-700">';
    BRANCH_ORDER.forEach(b => {
      const s = branchStats[b] || {count:0, amount:0};
      const pct = Math.round(s.count / maxCount * 100);
      tbl += '<tr class="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">'
        + '<td class="px-4 py-3 font-semibold text-slate-700 dark:text-slate-200">' + b + '</td>'
        + '<td class="px-4 py-3 text-right font-mono font-bold text-slate-800 dark:text-white">' + s.count.toLocaleString() + '</td>'
        + '<td class="px-4 py-3 text-right font-mono text-slate-500 dark:text-slate-400">' + (s.amount/1000000).toFixed(1) + '</td>'
        + '<td class="px-4 py-3"><div class="flex items-center gap-2">'
        +   '<div class="flex-1 bg-slate-200 dark:bg-slate-600 rounded-full h-2.5">'
        +     '<div class="bg-blue-500 h-2.5 rounded-full transition-all" style="width:' + pct + '%"></div>'
        +   '</div>'
        +   '<span class="text-[11px] text-slate-400 w-8 text-right">' + pct + '%</span>'
        + '</div></td>'
        + '</tr>';
    });
    const totalAmt = (totalAmount/1000000).toFixed(1);
    tbl += '<tr class="bg-blue-50 dark:bg-blue-900/20 font-bold">'
      + '<td class="px-4 py-2.5 text-blue-700 dark:text-blue-300 text-xs font-bold uppercase">합계</td>'
      + '<td class="px-4 py-2.5 text-right font-mono text-blue-700 dark:text-blue-300">' + totalCount.toLocaleString() + '</td>'
      + '<td class="px-4 py-2.5 text-right font-mono text-blue-700 dark:text-blue-300">' + totalAmt + '</td>'
      + '<td class="px-4 py-2.5"></td>'
      + '</tr></tbody></table>';
    document.getElementById('dash-branch-table').innerHTML = tbl;

    // ── TC 미실시율 ──
    let tcHTML = '';
    BRANCH_ORDER.forEach(b => {
      const v = TC_DATA[b] && TC_DATA[b][latestTcMonth];
      if (!v) return;
      const rate = parseFloat((v.n_count / v.total * 100).toFixed(1));
      const over = rate > 35;
      tcHTML += '<div class="mb-4">'
        + '<div class="flex items-center justify-between mb-1.5">'
        +   '<span class="text-xs font-bold text-slate-700 dark:text-slate-200">' + b + '</span>'
        +   '<span class="text-sm font-bold ' + (over ? 'text-red-500' : 'text-emerald-500') + '">' + rate + '%</span>'
        + '</div>'
        + '<div class="bg-slate-200 dark:bg-slate-600 rounded-full h-3 relative overflow-visible">'
        +   '<div class="' + (over ? 'bg-red-500' : 'bg-emerald-500') + ' h-3 rounded-full transition-all" style="width:' + Math.min(rate,100) + '%"></div>'
        +   '<div class="absolute top-0 h-3 border-l-2 border-yellow-400" style="left:35%"></div>'
        + '</div>'
        + '<div class="text-[10px] text-slate-400 mt-0.5">미실시 ' + v.n_count + ' / 모수 ' + v.total + '</div>'
        + '</div>';
    });
    tcHTML += '<div class="pt-1 border-t border-slate-200 dark:border-slate-600 text-[10px] text-slate-400 flex items-center gap-1.5">'
      + '<div class="w-4 border-t-2 border-yellow-400"></div>목표 기준선 35%</div>';
    document.getElementById('dash-tc-table').innerHTML = tcHTML;

    // ── TOP 10 결함코드 가로 차트 ──
    const top10 = Object.entries(codeStats).sort((a,b) => b[1]-a[1]).slice(0,10);
    const defLabels = top10.map(([code]) => {
      const desc = DEFECT_DESC[code] || code;
      return desc.length > 22 ? desc.slice(0,22) + '…' : desc;
    });
    const defValues = top10.map(([,v]) => v);
    if (_dashDefectChart) _dashDefectChart.destroy();
    const defCtx = document.getElementById('dash-defect-chart');
    if (defCtx) {
      _dashDefectChart = new Chart(defCtx.getContext('2d'), {
        type: 'bar',
        data: {
          labels: defLabels,
          datasets: [{ data: defValues, backgroundColor: '#1d4ed8bb', borderColor: '#1d4ed8', borderWidth:1, borderRadius:4 }]
        },
        options: {
          indexAxis: 'y',
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            datalabels: {
              color: '#94a3b8', font: { size: 9 }, anchor: 'end', align: 'end',
              formatter: v => v.toLocaleString()
            }
          },
          scales: {
            x: { ticks: { color: '#94a3b8', font: {size:10} }, grid: { color: '#334155' } },
            y: { ticks: { color: '#cbd5e1', font: {size: 9} }, grid: { display: false } }
          }
        }
      });
    }

    // ── 타입별 현황 ──
    const typeStats = {};
    DEFECT_RAW.forEach(r => {
      const t = r[2], cnt = r[4], amt = r[5];
      if (!typeStats[t]) typeStats[t] = {count:0, amount:0};
      typeStats[t].count  += cnt;
      typeStats[t].amount += amt;
    });
    const typeTotal = Object.values(typeStats).reduce((s,v) => s+v.count, 0);
    const maxTypeCount = Math.max(...Object.values(typeStats).map(v => v.count), 1);
    let typeHTML = '<table class="w-full text-xs">'
      + '<thead><tr class="border-b border-slate-200 dark:border-slate-600">'
      + '<th class="pb-2 text-left text-[11px] font-bold text-slate-400 uppercase">타입</th>'
      + '<th class="pb-2 text-right text-[11px] font-bold text-slate-400 uppercase">건수</th>'
      + '<th class="pb-2 text-right text-[11px] font-bold text-slate-400 uppercase">비율</th>'
      + '</tr></thead><tbody class="divide-y divide-slate-100 dark:divide-slate-700">';
    TYPES_ORDER.forEach(t => {
      const s = typeStats[t]; if (!s) return;
      const pct = (s.count / typeTotal * 100).toFixed(1);
      const barPct = Math.round(s.count / maxTypeCount * 100);
      typeHTML += '<tr>'
        + '<td class="py-2.5"><div class="flex items-center gap-2">'
        +   '<div class="w-2.5 h-2.5 rounded-sm flex-shrink-0" style="background:' + TYPE_COLORS[t] + '"></div>'
        +   '<span class="font-semibold text-slate-700 dark:text-slate-200">' + t + '</span>'
        + '</div></td>'
        + '<td class="py-2.5 text-right font-mono font-bold text-slate-700 dark:text-slate-200">' + s.count.toLocaleString() + '</td>'
        + '<td class="py-2.5 text-right text-slate-400">' + pct + '%</td>'
        + '</tr>';
    });
    typeHTML += '</tbody></table>';
    document.getElementById('dash-type-table').innerHTML = typeHTML;

    if (typeof lucide !== 'undefined') lucide.createIcons();
  }

  function initSalesChart() {
"""

html = html[:idx_start] + NEW_INIT_DASH + html[idx_start + len(OLD_SORT_BLOCK):]
print('✓ initDashboard() 함수 교체')

# ── 4. 페이지 로드 시 initDashboard 호출 ──────────────────────────────
# view-dashboard는 기본 뷰이므로 DOMContentLoaded에서 호출
OLD_LUCIDE = "    lucide.createIcons();"
NEW_LUCIDE = "    lucide.createIcons();\n    initDashboard();"
if 'initDashboard()' not in html.split('function initDashboard')[0]:
    # find the lucide.createIcons() in the DOMContentLoaded block
    idx = html.find('    lucide.createIcons();')
    if idx != -1:
        html = html[:idx] + "    lucide.createIcons();\n    initDashboard();" + html[idx + len("    lucide.createIcons();"):]
        print('✓ DOMContentLoaded에 initDashboard() 추가')

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'\n✓ 저장 완료: {len(html)/1024:.1f}KB')
