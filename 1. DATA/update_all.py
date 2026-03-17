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
df = pd.read_excel(RAW_TMP, sheet_name=3, header=1, engine='openpyxl')
cols = df.columns.tolist()
status_col = cols[1]; city_col = cols[5]; code_col = cols[12]
amount_col = cols[22]; month_col = cols[28]; type_col = cols[30]

TYPES = ['BSI','Warranty','TC/RECALL','WP','LOCAL TC','Goodwill']
df_c = df[df[status_col].str.contains('청구', na=False)].copy()
df_c = df_c[df_c[type_col].isin(TYPES)].copy()
df_c[city_col]  = df_c[city_col].str.replace('AS_','', regex=False)
df_c[code_col]  = df_c[code_col].astype(str).str.strip()
df_c[amount_col] = pd.to_numeric(df_c[amount_col], errors='coerce').fillna(0)
ok(f'청구 행 수: {len(df_c):,}')

# ── 3. BRANCH_DATA 집계 ───────────────────────────────────
step('BRANCH_DATA 집계 중...')
branch_agg = df_c.groupby([city_col, month_col, type_col]).agg(
    count=(amount_col,'count'), total=(amount_col,'sum')
).reset_index()

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

# ── 6. 개인별 청구 현황 집계 (Task=1, X열 기준) ──────────
step('개인별 청구 현황 집계 중...')
task_col   = cols[8]
person_col = cols[23]
u_amt_col  = cols[20]

df_task1 = df_c[df_c[task_col] == 1].copy()
df_task1[u_amt_col] = pd.to_numeric(df_task1[u_amt_col], errors='coerce').fillna(0)

person_agg = df_task1.groupby([person_col, month_col, type_col, status_col]).agg(
    count=(u_amt_col, 'count'), amount=(u_amt_col, 'sum')
).reset_index()

person_raw = [
    [r[person_col], r[month_col], r[type_col], r[status_col], int(r['count']), int(r['amount'])]
    for _, r in person_agg.iterrows()
]
ok(f'개인별 집계 행: {len(person_raw)}  /  고유 ID: {df_task1[person_col].nunique()}명')

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

# ── 8-1. JS 문자열 생성 ───────────────────────────────────
step('JS 데이터 문자열 생성 중...')
desc_js     = 'const DEFECT_DESC='    + json.dumps(matched_desc, ensure_ascii=False, separators=(',',':')) + ';'
raw_js      = 'const DEFECT_RAW='     + json.dumps(defect_raw,   ensure_ascii=False, separators=(',',':')) + ';'
um_js       = 'const DEFECT_UNMATCHED=' + json.dumps(unmatched,  ensure_ascii=False, separators=(',',':')) + ';'
person_js   = 'const PERSON_DATA='    + json.dumps(person_raw,   ensure_ascii=False, separators=(',',':')) + ';'
tc_js       = 'const TC_DATA='        + json.dumps(tc_data,      ensure_ascii=False, separators=(',',':')) + ';'
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
html = re.sub(r'const TC_DATA=\{.*?\};',             tc_js,      html, flags=re.DOTALL)

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html)
ok(f'HTML 크기: {os.path.getsize(HTML_PATH)/1024:.1f}KB')

# ── 8. git commit & push ──────────────────────────────────
step('git commit & push 중...')
os.chdir(BASE)
subprocess.run(['git', 'add', 'dashboard-app/preview/index.html'], check=True)

from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d %H:%M')
subprocess.run(['git', 'commit', '-m', f'데이터 자동 업데이트 ({today})'], check=True)
subprocess.run(['git', 'push'], check=True)
ok('배포 완료!')

print('\n' + '='*50)
print('  모든 작업이 완료됐습니다.')
print('='*50 + '\n')
