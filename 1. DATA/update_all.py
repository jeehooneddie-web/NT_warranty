"""
update_all.py
─────────────
OneDrive Excel → 집계 → HTML embed → git push 원클릭 자동화
실행: python update_all.py  또는  업데이트.bat 더블클릭
"""
import pandas as pd
import json, re, os, shutil, subprocess, sys

BASE      = 'C:/Users/user/Desktop/work for_'
DATA_DIR  = f'{BASE}/1. DATA'
HTML_PATH = f'{BASE}/dashboard-app/preview/index.html'
ONEDRIVE  = 'C:/Users/user/OneDrive - 내쇼날모터스/보증팀 원드라이브/1. Warranty Claim RAW'

RAW_SRC      = f'{ONEDRIVE}/2026 data RAW_Claim.xlsx'
RAW_TMP      = f'{DATA_DIR}/raw_claim_tmp.xlsx'
DEFECT_SRC   = f'{ONEDRIVE}/디펙트코드 리스트.xlsx'
DEFECT_TMP   = f'{DATA_DIR}/defect_list_tmp.xlsx'
TC_SRC       = f'{ONEDRIVE}/RecallTcRptRawData.xlsx'
TC_TMP       = f'{DATA_DIR}/tc_raw_tmp.xlsx'

def step(msg): print(f'\n[▶] {msg}')
def ok(msg):   print(f'    ✓ {msg}')
def err(msg):  print(f'    ✗ {msg}'); sys.exit(1)

# ── 1. 파일 복사 ──────────────────────────────────────────
step('OneDrive 파일 복사 중...')
for src, dst, name in [
    (RAW_SRC,    RAW_TMP,    'RAW 클레임'),
    (DEFECT_SRC, DEFECT_TMP, '디펙트코드 리스트'),
    (TC_SRC,     TC_TMP,     'TC 미실시 RAW'),
]:
    try:
        shutil.copy2(src, dst)
        ok(f'{name} 복사 완료')
    except PermissionError:
        err(f'{name} 파일이 Excel에서 열려 있습니다. 닫고 다시 실행하세요.')
    except FileNotFoundError:
        err(f'{name} 파일을 찾을 수 없습니다: {src}')

# ── 2. RAW 클레임 읽기 ────────────────────────────────────
step('RAW 클레임 집계 중...')
# header 행 자동 감지: B열(index 1)이 '청구/취소' 또는 '청구'를 포함하는 행을 헤더로 사용
_raw = pd.read_excel(RAW_TMP, sheet_name=2, header=None, engine='openpyxl', nrows=5)
_header_row = 0
for i in range(5):
    val = str(_raw.iloc[i, 1])
    if '청구' in val or '취소' in val or 'Claim' in val:
        _header_row = i
        break
df = pd.read_excel(RAW_TMP, sheet_name=2, header=_header_row, engine='openpyxl')
cols = df.columns.tolist()
ok(f'헤더 행: {_header_row}행  /  총 컬럼: {len(cols)}개  /  B열: {cols[1]}')
status_col = cols[1]; city_col = cols[5]; code_col = cols[12]
amount_col = cols[22]; task_col = cols[8]
k_col = cols[10]  # K열: Warranty Stage
# month/type은 수식열(AC/AE) 대신 원본열(N열 날짜, K/M열)로 직접 계산
df['_month'] = pd.to_datetime(df[cols[13]], errors='coerce').dt.strftime('%y-%m')
month_col = '_month'

def _compute_type(k_val, m_val):
    k = str(k_val).strip() if pd.notna(k_val) else ''
    m = str(m_val).strip() if pd.notna(m_val) else ''
    if 'goodwill' in k.lower(): return 'Goodwill'
    if k == 'Warranty plus': return 'WP'
    if 'LA' in m: return 'LOCAL TC'
    try:
        m_num = float(m.replace(',',''))
        if m_num < 100_000_000: return 'TC/RECALL'
        if m_num > 8_700_000_000 and not m.startswith('99'): return 'BSI'
        return 'Warranty'
    except Exception:
        return 'Warranty'

df['_type'] = df.apply(lambda r: _compute_type(r[k_col], r[code_col]), axis=1)
type_col = '_type'
ok(f'month/type 직접 계산 완료 (수식열 비의존)')

# 지점 코드 → 지점명 매핑 (숫자코드 또는 AS_ 형식 모두 처리)
BRANCH_MAP = {'26999':'전주','40699':'군산','41967':'목포','419668':'서산','44835':'평택'}

TYPES = ['BSI','Warranty','TC/RECALL','WP','LOCAL TC','Goodwill']
df_c = df[df[status_col].str.contains('청구', na=False)].copy()
df_c = df_c[df_c[type_col].isin(TYPES)].copy()
df_c[city_col] = df_c[city_col].astype(str).str.replace('AS_','', regex=False)
df_c[city_col] = df_c[city_col].replace(BRANCH_MAP)
df_c[code_col]  = df_c[code_col].astype(str).str.strip()
df_c[amount_col] = pd.to_numeric(df_c[amount_col], errors='coerce').fillna(0)
# M열이 '99'로 시작하는 경우 BSI → Warranty 재분류 (99코드는 BSI 아님)
mask_99 = (df_c[type_col] == 'BSI') & (df_c[code_col].str.startswith('99'))
df_c.loc[mask_99, type_col] = 'Warranty'
ok(f'청구 행 수: {len(df_c):,}  /  99코드 재분류: {mask_99.sum():,}건 (BSI→Warranty)')

# ── 3. BRANCH_DATA 집계 ───────────────────────────────────
step('BRANCH_DATA 집계 중...')
df_branch_count = df_c[df_c[task_col] == 1].copy()
branch_cnt = df_branch_count.groupby([city_col, month_col, type_col]).agg(count=(amount_col,'count')).reset_index()
branch_tot = df_c.groupby([city_col, month_col, type_col]).agg(total=(amount_col,'sum')).reset_index()
branch_agg = branch_cnt.merge(branch_tot, on=[city_col, month_col, type_col], how='outer').fillna(0)
branch_agg['count'] = branch_agg['count'].astype(int)

branch_data = {}
for _, r in branch_agg.iterrows():
    city = r[city_col]; mo = r[month_col]; tp = r[type_col]
    branch_data.setdefault(city, {}).setdefault(mo, {})[tp] = {
        'count': int(r['count']), 'total': int(r['total'])
    }

branch_js = 'const BRANCH_DATA = ' + json.dumps(branch_data, ensure_ascii=False, separators=(',',':')) + ';'
ok(f'지점 수: {len(branch_data)}')

# ── 4. 디펙트코드 리스트 읽기 ─────────────────────────────
step('디펙트코드 리스트 읽기 중...')
dl = pd.read_excel(DEFECT_TMP, sheet_name=0, header=0, engine='openpyxl')
dl_cols = dl.columns.tolist()
desc_map = {str(r[dl_cols[0]]).strip(): str(r[dl_cols[1]]).strip() for _, r in dl.iterrows()}
ok(f'코드 수: {len(desc_map):,}')

# ── 5. DEFECT_RAW 집계 ────────────────────────────────────
step('DEFECT_RAW 집계 중...')
agg = df_c.groupby([city_col, month_col, type_col, code_col]).agg(
    count=(amount_col,'count'), amount=(amount_col,'sum')
).reset_index()

matched_desc = {}
unmatched_set = set()
for code in agg[code_col].unique():
    if code in desc_map:
        matched_desc[code] = desc_map[code]
    else:
        unmatched_set.add(code)

defect_raw = [
    [r[city_col], r[month_col], r[type_col], r[code_col], int(r['count']), int(r['amount'])]
    for _, r in agg.iterrows()
]

um_agg = agg[agg[code_col].isin(unmatched_set)].groupby(code_col).agg(
    count=('count','sum'), amount=('amount','sum')
).reset_index().sort_values('count', ascending=False)
unmatched = [{'code':r[code_col],'count':int(r['count']),'amount':int(r['amount'])} for _,r in um_agg.iterrows()]

ok(f'집계 행: {len(defect_raw):,}  /  미매칭: {len(unmatched)}개')

# ── 6. 개인별 청구 현황 집계 (Task=1, 금액=클레임금액 cols[22]) ──────────
step('개인별 청구 현황 집계 중...')
task_col   = cols[8]
person_col = cols[23]
# 금액: 보증매출(BRANCH_DATA)과 동일하게 cols[22] 사용
p_amt_col  = cols[22]

# 청구 + 취소 모두 포함
df_person_base = df[df[status_col].str.contains('청구|취소', na=False)].copy()
df_person_base = df_person_base[df_person_base[type_col].isin(TYPES)].copy()
df_person_base[city_col] = df_person_base[city_col].str.replace('AS_','', regex=False)
df_person_base[p_amt_col] = pd.to_numeric(df_person_base[p_amt_col], errors='coerce').fillna(0)

# 개인별: Task=1 필터
df_task1 = df_person_base[df_person_base[task_col] == 1].copy()

person_agg = df_task1.groupby([person_col, month_col, type_col, status_col]).agg(
    count=(p_amt_col, 'count'), amount=(p_amt_col, 'sum')
).reset_index()

person_raw = [
    [r[person_col], r[month_col], r[type_col], r[status_col], int(r['count']), int(r['amount'])]
    for _, r in person_agg.iterrows()
]

# 전체합계: Task 필터 없이 전체 집계 (보증매출과 동일 기준)
total_agg = df_person_base.groupby([month_col, type_col, status_col]).agg(
    count=(p_amt_col, 'count'), amount=(p_amt_col, 'sum')
).reset_index()
for _, r in total_agg.iterrows():
    person_raw.append(['전체합계', r[month_col], r[type_col], r[status_col], int(r['count']), int(r['amount'])])

ok(f'개인별 집계 행: {len(person_raw)}  /  고유 ID: {df_task1[person_col].nunique()}명')

# ── 6-2. 일별 현황 집계 (당월 기준, Task=1, 청구) ──────────────────────
step('일별 현황 집계 중...')
import datetime as _dt
_cur_month = _dt.date.today().strftime('%y-%m')
df_daily = df[df[status_col].str.contains('청구', na=False)].copy()
df_daily = df_daily[df_daily[type_col].isin(TYPES)].copy()
df_daily = df_daily[df_daily[month_col] == _cur_month].copy()
df_daily['_date'] = pd.to_datetime(df_daily[cols[13]], errors='coerce').dt.strftime('%y-%m-%d')
df_daily[amount_col] = pd.to_numeric(df_daily[amount_col], errors='coerce').fillna(0)
df_daily_t1 = df_daily[df_daily[task_col] == 1].copy()
daily_agg = df_daily_t1.groupby([person_col, '_date', type_col]).agg(
    count=(amount_col, 'count'), amount=(amount_col, 'sum')
).reset_index()
daily_raw = [
    [r[person_col], r['_date'], r[type_col], int(r['count']), int(r['amount'])]
    for _, r in daily_agg.iterrows()
]
ok(f'일별 집계: {len(daily_raw):,}행 (당월 {_cur_month})')

# ── 7. TC 미실시율 집계 ────────────────────────────────────
step('TC 미실시율 집계 중...')
tc_df = pd.read_excel(TC_TMP, header=0, engine='openpyxl')
tc_cols = tc_df.columns.tolist()
tc_campaign = tc_cols[1]; tc_car = tc_cols[4]; tc_dealer = tc_cols[6]
tc_ro = tc_cols[11]; tc_result = tc_cols[9]; tc_date = tc_cols[5]

tc_dedup = tc_df.drop_duplicates(subset=[tc_campaign, tc_car, tc_dealer, tc_ro])
tc_clean = tc_dedup[tc_dedup[tc_ro].notna() & (tc_dedup[tc_ro].astype(str).str.strip() != '')].copy()
tc_clean['branch'] = tc_clean[tc_dealer].astype(str).str.replace('AS_', '', regex=False)
tc_clean['month']  = pd.to_datetime(tc_clean[tc_date], errors='coerce').dt.strftime('%y-%m')
tc_clean['is_N']   = tc_clean[tc_result].astype(str).str.strip() == 'N'

tc_agg = tc_clean.groupby(['branch', 'month']).agg(
    total=('is_N', 'count'), n_count=('is_N', 'sum')
).reset_index()

tc_data = {}
for _, r in tc_agg.iterrows():
    tc_data.setdefault(r['branch'], {})[r['month']] = {
        'total': int(r['total']), 'n_count': int(r['n_count'])
    }
ok(f'TC 집계 완료: {len(tc_clean)}행 → {sum(len(v) for v in tc_data.values())}개월치')

# ── 8. CLAIM_DATA 집계 (불승인/보완요청/보완완료, Task=1) ─
step('CLAIM_DATA 집계 중...')
df_claim_all = df[df[cols[6]].isin(['불승인', '보완요청', '보완완료'])].copy()
df_claim_all[cols[22]] = pd.to_numeric(df_claim_all[cols[22]], errors='coerce').fillna(0)

# 클레임번호별 전체 금액 합산 (Task 무관)
claim_amount_total = df_claim_all.groupby(cols[7])[cols[22]].sum().to_dict()

# Task=1 행만 표시 (금액은 클레임번호 단위 합산값으로 대체)
df_claim = df_claim_all[df_claim_all[cols[8]] == 1].copy()
claim_raw = []
for _, r in df_claim.iterrows():
    date_val = str(r[cols[13]])[:10] if pd.notna(r[cols[13]]) and str(r[cols[13]]) not in ('nan','NaT') else ''
    claim_no = str(r[cols[7]])
    claim_raw.append([
        claim_no,                                             # H: 클레임번호
        str(r[cols[5]]).replace('AS_',''),                    # F: 지점
        str(r[cols[6]]),                                      # G: 클레임상태
        str(r[cols[10]]),                                     # K: 워런티Stage
        str(r[cols[11]]),                                     # L: Claim Type
        str(r[cols[12]]),                                     # M: Defect Code
        date_val,                                             # N: 날짜
        int(claim_amount_total.get(claim_no, 0)),             # W: 클레임금액 (전체합산)
        str(r[cols[23]]),                                     # X: 담당확인자
    ])
ok(f'CLAIM_DATA: {len(claim_raw):,}행 (불승인/보완요청/보완완료, Task=1)')

# ── 9. WHOLESALE_DATA 집계 (클레임현황 시트) ──────────────────
step('WHOLESALE_DATA 집계 중...')
wholesale_data = {}
try:
    df_kh = pd.read_excel(RAW_TMP, sheet_name='클레임현황', header=0, engine='openpyxl')
    kc = df_kh.columns.tolist()
    # 열 인덱스: 지점=0, J=9, M=12, O=14, R=17, S=18, T=19, W=22
    kh_J = kc[9];  kh_M = kc[12]; kh_O = kc[14]; kh_R = kc[17]
    kh_S = 'S';    kh_T = 'T';    kh_W = 'W'
    for col in [kh_J, kh_M, kh_O, kh_R]:
        df_kh[col] = pd.to_numeric(df_kh[col], errors='coerce').fillna(0)
    df_kh[kh_S] = df_kh[kh_S].astype(str).str.strip()
    df_kh[kh_T] = df_kh[kh_T].astype(str).str.strip()
    df_kh[kh_W] = df_kh[kh_W].astype(str).str.strip()
    df_kh = df_kh[df_kh[kh_S].str.match(r'\d{2}-\d{2}')]  # 유효 월만

    for _, r in df_kh.groupby([kh_T, kh_S]).agg(
        amount=(kh_M,'sum'), parts=(kh_J,'sum'), count=(kh_M,'count')
    ).reset_index().iterrows():
        ct, mo = str(r[kh_T]), str(r[kh_S])
        wholesale_data.setdefault(ct, {}).setdefault(mo, {})['charge'] = {
            'amount': int(r['amount']), 'parts': int(r['parts']), 'count': int(r['count'])
        }
    for _, r in df_kh.groupby([kh_T, kh_S]).agg(
        amount=(kh_R,'sum'), parts=(kh_O,'sum')
    ).reset_index().iterrows():
        ct, mo = str(r[kh_T]), str(r[kh_S])
        wholesale_data.setdefault(ct, {}).setdefault(mo, {})['approve'] = {
            'amount': int(r['amount']), 'parts': int(r['parts'])
        }
    df_pend = df_kh[df_kh[kh_W] == '승인대기']
    for _, r in df_pend.groupby([kh_T, kh_S]).agg(
        amount=(kh_M,'sum'), parts=(kh_J,'sum')
    ).reset_index().iterrows():
        ct, mo = str(r[kh_T]), str(r[kh_S])
        wholesale_data.setdefault(ct, {}).setdefault(mo, {})['pending'] = {
            'amount': int(r['amount']), 'parts': int(r['parts'])
        }
    ok(f'Claim Type: {len(wholesale_data)}종  /  총 행: {len(df_kh):,}')
except Exception as _e:
    ok(f'클레임현황 시트 없음 또는 오류 → WHOLESALE_DATA 빈값 ({_e})')

# ── 8-1. JS 문자열 생성 ───────────────────────────────────
step('JS 데이터 문자열 생성 중...')
desc_js     = 'const DEFECT_DESC='    + json.dumps(matched_desc, ensure_ascii=False, separators=(',',':')) + ';'
raw_js      = 'const DEFECT_RAW='     + json.dumps(defect_raw,   ensure_ascii=False, separators=(',',':')) + ';'
um_js       = 'const DEFECT_UNMATCHED=' + json.dumps(unmatched,  ensure_ascii=False, separators=(',',':')) + ';'
person_js   = 'const PERSON_DATA='    + json.dumps(person_raw,   ensure_ascii=False, separators=(',',':')) + ';'
daily_js    = 'const PERSON_DAILY='   + json.dumps(daily_raw,    ensure_ascii=False, separators=(',',':')) + ';'
tc_js       = 'const TC_DATA='        + json.dumps(tc_data,      ensure_ascii=False, separators=(',',':')) + ';'
claim_js      = 'const CLAIM_DATA='      + json.dumps(claim_raw,      ensure_ascii=False, separators=(',',':')) + ';'
wholesale_js  = 'const WHOLESALE_DATA=' + json.dumps(wholesale_data, ensure_ascii=False, separators=(',',':')) + ';'
ok('완료')

# ── 7. HTML embed ─────────────────────────────────────────
step('HTML에 데이터 삽입 중...')
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

html = re.sub(r'const BRANCH_DATA\s*=\s*\{.*?\};',  branch_js,  html, flags=re.DOTALL)
html = re.sub(r'const DEFECT_DESC=\{.*?\};',         desc_js,    html, flags=re.DOTALL)
html = re.sub(r'const DEFECT_RAW=\[.*?\];',          raw_js,     html, flags=re.DOTALL)
html = re.sub(r'const DEFECT_UNMATCHED=\[.*?\];',    um_js,      html, flags=re.DOTALL)
html = re.sub(r'const PERSON_DATA=\[.*?\];',         person_js,  html, flags=re.DOTALL)
html = re.sub(r'const PERSON_DAILY=\[.*?\];',        daily_js,   html, flags=re.DOTALL)
html = re.sub(r'const TC_DATA=\{.*?\};',             tc_js,      html, flags=re.DOTALL)
html = re.sub(r'const CLAIM_DATA=\[.*?\];',          claim_js,      html, flags=re.DOTALL)
html = re.sub(r'const WHOLESALE_DATA=\{.*?\};',     wholesale_js,  html, flags=re.DOTALL)

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html)
ok(f'HTML 크기: {os.path.getsize(HTML_PATH)/1024:.1f}KB')

# ── 8. git commit & push ──────────────────────────────────
step('git commit & push 중...')
os.chdir(BASE)
subprocess.run(['git', 'add', 'dashboard-app/preview/index.html'], check=True)

from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d %H:%M')

# 변경사항이 있을 때만 커밋
status = subprocess.run(['git', 'status', '--porcelain', 'dashboard-app/preview/index.html'],
                        capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(['git', 'commit', '-m', f'데이터 자동 업데이트 ({today})'], check=True)
    subprocess.run(['git', 'push'], check=True)
    ok('배포 완료!')
else:
    ok('데이터 변경 없음 — 커밋 스킵 (이미 최신 상태)')

print('\n' + '='*50)
print('  모든 작업이 완료됐습니다.')
print('='*50 + '\n')
