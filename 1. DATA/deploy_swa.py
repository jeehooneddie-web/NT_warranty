"""SWA 단독 배포 스크립트 — 코드 변경 후 warranty.nationalmotors.co.kr 즉시 반영용"""
import sys, subprocess, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(BASE, 'dashboard-app', 'preview')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config_azure import SWA_DEPLOYMENT_TOKEN
except ImportError:
    print('⚠ config_azure.py 없음 — SWA 배포 불가')
    sys.exit(1)

print('Azure Static Web Apps 배포 중...')
result = subprocess.run(
    ['swa.cmd', 'deploy', APP_DIR,
     '--deployment-token', SWA_DEPLOYMENT_TOKEN,
     '--env', 'production'],
    capture_output=True, text=True, errors='replace'
)
if result.returncode == 0:
    print('✅ SWA 배포 완료 → https://warranty.nationalmotors.co.kr')
else:
    print(f'⚠ SWA 배포 실패:\n{result.stderr}')
    sys.exit(1)
