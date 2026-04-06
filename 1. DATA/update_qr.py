"""
update_qr.py
─────────────
QR_CLAIM_DATA 생성 전용 스크립트
Claim 상세_전체 시트에서 2026년 클레임 추출 → HTML embed → git push
실행: python update_qr.py  또는  QR업데이트.bat 더블클릭
"""
import pandas as pd
import json, re, os, shutil, subprocess, sys

BASE      = 'D:/코딩/work for_'
DATA_DIR  = f'{BASE}/1. DATA'
HTML_PATH = f'{BASE}/dashboard-app/preview/index.html'
ONEDRIVE  = 'C:/Users/user/OneDrive - 내쇼날모터스/보증팀 원드라이브/1. Warranty Claim RAW'

RAW_SRC = f'{ONEDRIVE}/2026 data RAW_Claim.xlsx'
RAW_TMP = f'{DATA_DIR}/raw_claim_tmp.xlsx'

def step(msg): print(f'\n[▶] {msg}')
def ok(msg):   print(f'    ✓ {msg}')
def err(msg):  print(f'    ✗ {msg}'); sys.exit(1)

# ── 1. 파일 복사 ──────────────────────────────────────────
step('RAW 클레임 파일 복사 중...')
try:
    shutil.copy2(RAW_SRC, RAW_TMP)
    ok('복사 완료')
except PermissionError:
    err('RAW 클레임 파일이 Excel에서 열려 있습니다. 닫고 다시 실행하세요.')
except FileNotFoundError:
    err(f'파일을 찾을 수 없습니다: {RAW_SRC}')

# ── 2. QR_CLAIM_DATA 집계 (Claim 상세_전체, 2026년 수리일 기준) ──
step('QR_CLAIM_DATA 집계 중...')
df_cl = pd.read_excel(RAW_TMP, sheet_name='Claim 상세_전체', header=1, engine='openpyxl')
cc = df_cl.columns.tolist()
# H=클레임번호(7), M=DefectCode(12), S=차대번호(18), F=지점(5), AA=수리일(26)
cc_claim=cc[7]; cc_defect=cc[12]; cc_vin=cc[18]
cc_branch=cc[5]; cc_repair=cc[26]

df_cl['_rep'] = pd.to_datetime(df_cl[cc_repair], errors='coerce')
df_cl_2026 = df_cl[
    df_cl[cc_claim].notna() &
    df_cl[cc_claim].astype(str).str.startswith('WC') &
    (df_cl['_rep'].dt.year >= 2026)
].copy()

qr_seen = {}
qr_claim_rows = []
for _, r in df_cl_2026.iterrows():
    cn = str(r[cc_claim]).strip()[2:]   # WC 제거
    defect = r[cc_defect]
    if cn in qr_seen or pd.isna(defect): continue
    qr_seen[cn] = True
    vin = str(r[cc_vin]).strip() if pd.notna(r[cc_vin]) else ''
    vin7 = vin[-7:] if len(vin) >= 7 else vin
    branch = str(r[cc_branch]).replace('AS_','').strip()
    try:
        rep_str = pd.to_datetime(r[cc_repair]).strftime('%Y-%m-%d') if pd.notna(r[cc_repair]) else ''
    except Exception:
        rep_str = ''
    qr_claim_rows.append([cn, str(defect).strip(), vin7, branch, rep_str])

ok(f'QR_CLAIM_DATA: {len(qr_claim_rows):,}건 (2026년)')

# ── 3. HTML embed ─────────────────────────────────────────
step('HTML에 데이터 삽입 중...')
qr_claim_js = 'const QR_CLAIM_DATA=' + json.dumps(qr_claim_rows, ensure_ascii=False, separators=(',',':')) + ';'

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

html = re.sub(r'const QR_CLAIM_DATA=\[.*?\];', qr_claim_js, html, flags=re.DOTALL)

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html)
ok(f'HTML 크기: {os.path.getsize(HTML_PATH)/1024:.1f}KB')

# ── 4. git commit & push ──────────────────────────────────
step('git commit & push 중...')
os.chdir(BASE)
subprocess.run(['git', 'add', 'dashboard-app/preview/index.html'], check=True)

from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d %H:%M')

status = subprocess.run(['git', 'status', '--porcelain', 'dashboard-app/preview/index.html'],
                        capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(['git', 'commit', '-m', f'QR 고품 데이터 업데이트 ({today})'], check=True)
    subprocess.run(['git', 'push'], check=True)
    ok('배포 완료!')
else:
    ok('데이터 변경 없음 — 커밋 스킵')

print('\n' + '='*50)
print('  QR 고품 데이터 업데이트 완료.')
print('='*50 + '\n')
