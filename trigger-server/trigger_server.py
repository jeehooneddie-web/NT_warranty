"""
DMS 트리거 서버
  - 매일 08:30 자동 스케줄 실행
  - cloudflared 내부 실행 → URL 캡처 → ntfy 푸시
  - Selenium Chrome(CDP 9222) 세션 재사용
  - OTP 중계: 모바일 /otp → Selenium → DMS OTP 입력
  - SSE 실시간 로그 스트리밍
"""

import os, sys, json, queue, threading, socket, time, subprocess, re
import datetime, urllib.request, urllib.parse
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)
CORS(app, origins=[
    "https://jeehooneddie-web.github.io",
    "http://localhost",
    "http://127.0.0.1",
])

# ── 설정 ──────────────────────────────────────────────────────────────────
SECRET_TOKEN    = os.environ.get("DMS_TOKEN", "nm-dms-2026")
CHROME_PORT     = 9222
SCRIPTS_DIR     = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "1. DATA"))
NTFY_TOPIC      = "nm-dms-trigger-9f3k2"
DMS_PAGE_BASE   = "https://jeehooneddie-web.github.io/NT_warranty/dms.html"
SCHEDULE_HOUR   = 8
SCHEDULE_MINUTE = 30

SUPABASE_URL    = "https://vbvghhtroitmroxmfepr.supabase.co"
SUPABASE_KEY    = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZidmdoaHRyb2l0bXJveG1mZXByIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4MTAxMjEsImV4cCI6MjA5MDM4NjEyMX0.2sq5uGj4j6Fm_IgztrucJv5bbXyk4ZXkWeZxnDMjhZg"

# DMS 로그인 셀렉터
SEL_USER_ID   = '#originUsrId'
SEL_LOGIN_BTN = '#btnLogin'
SEL_OTP_INPUT = '#otpNo'
SEL_OTP_BTN   = '#btnReqAuth'

# ── 전역 상태 ──────────────────────────────────────────────────────────────
state = {
    "chrome_ok":     False,
    "dms_logged_in": False,
    "status": "idle",
    "msg": "",
    "option": None,
    "tunnel_url": "",
}
otp_q = queue.Queue(maxsize=1)
log_q = queue.Queue()

# ── ntfy 알림 ──────────────────────────────────────────────────────────────
def _notify(title, body, tags="white_check_mark", priority="default", actions=None):
    try:
        headers = {
            "Title":    title,       # ASCII only
            "Tags":     tags,
            "Priority": priority,
            "Click":    DMS_PAGE_BASE,
            "Content-Type": "text/plain; charset=utf-8",
        }
        if actions:
            headers["Actions"] = actions
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers=headers,
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  ntfy 전송: {title}", flush=True)
    except Exception as e:
        print(f"  ntfy 오류: {e}", flush=True)

def _dms_url(tunnel_url):
    """dms.html 직접 접속 URL (server + token 포함)"""
    return (f"{DMS_PAGE_BASE}"
            f"?server={urllib.parse.quote(tunnel_url, safe='')}"
            f"&token={urllib.parse.quote(SECRET_TOKEN, safe='')}")

def _notify_server_start(url):
    link = _dms_url(url)
    _notify(
        title="DMS Server Started",
        body=f"Tunnel: {url}",
        tags="rocket",
        actions=f"view, Open DMS, {link}"
    )

def _notify_login_required():
    url = state.get("tunnel_url", "")
    link = _dms_url(url) if url else DMS_PAGE_BASE
    _notify(
        title="DMS Login Required (08:30)",
        body="OTP login needed. Tap to open DMS.",
        tags="key",
        priority="high",
        actions=f"view, Open DMS, {link}"
    )

def _notify_done(option):
    labels = {0:"All DMS", 1:"Claim Detail", 2:"Claim Status", 3:"TC RawData", 4:"TC Verify"}
    _notify(
        title=f"DMS Update Done [{option}] {labels.get(option,'')}",
        body="업데이트 완료.",
        tags="white_check_mark"
    )

def _notify_failed(msg):
    _notify(title="DMS Update Failed", body=msg, tags="x", priority="high")

# ── 터널 자동 시작 ─────────────────────────────────────────────────────────
def start_tunnel():
    try:
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", "http://localhost:5001"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace"
        )
        for line in proc.stdout:
            m = re.search(r'https://[\w\-]+\.trycloudflare\.com', line)
            if m:
                url = m.group(0)
                state["tunnel_url"] = url
                print(f"\n  터널 URL: {url}\n", flush=True)
                _save_url(url)
                _save_url_supabase(url)
                _notify_server_start(url)
                break
        proc.wait()
    except FileNotFoundError:
        print("  [경고] cloudflared 없음", flush=True)
    except Exception as e:
        print(f"  [터널 오류] {e}", flush=True)

def _save_url(url):
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop", "DMS_URL.txt")
        with open(desktop, "w") as f:
            f.write(url + "\n")
    except Exception:
        pass

def _save_url_supabase(url):
    try:
        data = json.dumps({"key": "tunnel_url", "value": url,
                           "updated_at": datetime.datetime.utcnow().isoformat() + "Z"}).encode("utf-8")
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/server_config",
            data=data,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        print("  Supabase URL 저장 완료", flush=True)
    except Exception as e:
        print(f"  Supabase 저장 오류: {e}", flush=True)

# ── 스케줄러 ──────────────────────────────────────────────────────────────
def _scheduler_loop():
    """매일 08:30 자동 실행"""
    print(f"  스케줄러 시작 — 매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} 실행", flush=True)
    while True:
        now    = datetime.datetime.now()
        target = now.replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        wait = (target - now).total_seconds()
        print(f"  다음 실행: {target.strftime('%m/%d %H:%M')} ({int(wait//3600)}시간 후)", flush=True)
        time.sleep(wait)
        _run_scheduled()

def _run_scheduled():
    print("  [스케줄] 08:30 자동 실행 시작", flush=True)

    # 이미 실행 중이면 건너뜀
    if state["status"] == "running":
        print("  [스케줄] 이미 실행 중 — 건너뜀", flush=True)
        return

    # DMS 로그인 확인
    if not state["dms_logged_in"]:
        print("  [스케줄] DMS 미로그인 → 로그인 요청 알림 전송", flush=True)
        _notify_login_required()

        # 로그인 대기 최대 30분 (30초 × 60)
        for i in range(60):
            time.sleep(30)
            if state["dms_logged_in"]:
                print(f"  [스케줄] 로그인 확인 ({(i+1)*30}초 후) → 실행 시작", flush=True)
                break
        else:
            msg = "30분 내 DMS 로그인 없음 — 스케줄 취소"
            print(f"  [스케줄] {msg}", flush=True)
            _notify_failed(msg)
            return

    # 실행
    while not log_q.empty():
        try: log_q.get_nowait()
        except Exception: break

    state["status"] = "running"
    state["option"] = 0
    state["msg"]    = "스케줄 자동 실행 중 (08:30)"
    _run_scripts(0)

# ── 헬퍼 ──────────────────────────────────────────────────────────────────
def _check_token():
    t = request.headers.get("X-Token") or request.args.get("token")
    return t == SECRET_TOKEN

def _start_chrome():
    """Chrome 9222 포트로 실행 — 경로 자동 탐색"""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            subprocess.Popen([
                path,
                "--remote-debugging-port=9222",
                f"--user-data-dir={os.environ.get('TEMP', '')}\\chrome_dms",
                "--start-maximized",
                "https://bmwdms.co.kr/"
            ])
            print("  Chrome 시작됨", flush=True)
            return True
    print("  [오류] Chrome 경로를 찾을 수 없음", flush=True)
    return False

def _chrome_alive():
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect(("localhost", CHROME_PORT))
        return True
    except Exception:
        return False
    finally:
        s.close()

def _get_driver():
    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"localhost:{CHROME_PORT}")
    return webdriver.Chrome(options=opts)

def _find_dms_window(driver):
    for h in driver.window_handles:
        driver.switch_to.window(h)
        url = driver.current_url
        if "bmwdms.co.kr" in url and "report." not in url:
            return True
    return False

def _log(msg):
    log_q.put(msg)
    print(msg, flush=True)

# ── 라우트 ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    url = state.get("tunnel_url", "시작 중...")
    nxt = ""
    try:
        now    = datetime.datetime.now()
        target = now.replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        nxt = target.strftime("%m/%d %H:%M")
    except Exception:
        pass
    return (f"<h2>DMS 트리거 서버</h2>"
            f"<p>터널 URL: <b>{url}</b></p>"
            f"<p>다음 스케줄: <b>{nxt}</b></p>"
            f"<p>상태: {state['status']}</p>"), 200

@app.route("/status")
def get_status():
    if not _check_token():
        return jsonify({"error": "unauthorized"}), 401
    state["chrome_ok"] = _chrome_alive()
    if state["chrome_ok"] and state["status"] == "idle":
        try:
            d = _get_driver()
            found = _find_dms_window(d)
            if found:
                # GNB 메뉴 존재 여부로 실제 로그인 판단
                gnb = d.find_elements(By.CSS_SELECTOR, ".gnb-ul")
                state["dms_logged_in"] = len(gnb) > 0
            else:
                state["dms_logged_in"] = False
        except Exception:
            state["dms_logged_in"] = False
    return jsonify(state)

@app.route("/login", methods=["POST"])
def start_login():
    if not _check_token():
        return jsonify({"error": "unauthorized"}), 401
    if state["status"] not in ("idle", "error"):
        return jsonify({"error": "busy", "status": state["status"]}), 409
    while not otp_q.empty():
        try: otp_q.get_nowait()
        except Exception: break
    state["status"] = "logging_in"
    state["msg"] = "로그인 시작..."
    threading.Thread(target=_login_flow, daemon=True).start()
    return jsonify({"status": "login_started"})

@app.route("/otp", methods=["POST"])
def submit_otp():
    if not _check_token():
        return jsonify({"error": "unauthorized"}), 401
    if state["status"] != "waiting_otp":
        return jsonify({"error": "not_waiting"}), 409
    otp = (request.json or {}).get("otp", "").strip()
    if not otp:
        return jsonify({"error": "otp_required"}), 400
    try:
        otp_q.put_nowait(otp)
    except queue.Full:
        return jsonify({"error": "already_submitted"}), 409
    return jsonify({"status": "ok"})

@app.route("/run", methods=["POST"])
def run_update():
    if not _check_token():
        return jsonify({"error": "unauthorized"}), 401
    if state["status"] == "running":
        return jsonify({"error": "already_running"}), 409
    opt = (request.json or {}).get("option")
    if opt not in (0, 1, 2, 3, 4):
        return jsonify({"error": "invalid_option"}), 400
    if opt in (0, 1, 2, 3) and not state["dms_logged_in"]:
        return jsonify({"error": "dms_login_required"}), 403
    while not log_q.empty():
        try: log_q.get_nowait()
        except Exception: break
    state["status"] = "running"
    state["option"] = opt
    state["msg"] = f"옵션 [{opt}] 실행 중"
    threading.Thread(target=_run_scripts, args=(opt,), daemon=True).start()
    return jsonify({"status": "started", "option": opt})

@app.route("/logs")
def stream_logs():
    if not _check_token():
        return jsonify({"error": "unauthorized"}), 401
    def generate():
        while True:
            try:
                msg = log_q.get(timeout=25)
                yield f"data: {json.dumps({'msg': msg}, ensure_ascii=False)}\n\n"
                if msg == "__DONE__" or msg.startswith("__ERROR__"):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'ping': True})}\n\n"
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ── DMS 로그인 흐름 ────────────────────────────────────────────────────────
def _login_flow():
    try:
        # Chrome 9222 없으면 자동 시작
        if not _chrome_alive():
            state["msg"] = "Chrome 시작 중..."
            if not _start_chrome():
                state["status"] = "error"
                state["msg"] = "Chrome을 찾을 수 없습니다"
                return
            for _ in range(20):
                time.sleep(1)
                if _chrome_alive():
                    break
            else:
                state["status"] = "error"
                state["msg"] = "Chrome 시작 실패 (20초 초과)"
                return
            time.sleep(4)

        d = _get_driver()
        if not _find_dms_window(d):
            d.execute_script("window.open('https://www.bmwdms.co.kr/')")
            time.sleep(4)
            _find_dms_window(d)

        # GNB로 이미 로그인 여부 확인
        if d.find_elements(By.CSS_SELECTOR, ".gnb-ul"):
            state["dms_logged_in"] = True
            state["status"] = "idle"
            state["msg"] = "이미 로그인됨"
            return

        state["msg"] = "로그인 페이지 확인됨, 로그인 버튼 클릭 중..."
        wait = WebDriverWait(d, 20)

        # ID 필드가 비어있으면 자동완성 시도
        try:
            id_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL_USER_ID)))
            if not id_el.get_attribute("value"):
                id_el.click()
                time.sleep(0.5)
                id_el.send_keys(Keys.DOWN)
                time.sleep(1.0)
        except Exception:
            pass

        # 로그인 버튼 클릭
        login_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_LOGIN_BTN)))
        login_btn.click()
        state["msg"] = "로그인 버튼 클릭됨, OTP 대기 중..."
        time.sleep(2)

        # OTP 입력 필드 대기
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL_OTP_INPUT)))
        state["status"] = "waiting_otp"
        state["msg"] = "SMS OTP를 입력하세요 (2분 내)"

        try:
            otp = otp_q.get(timeout=120)
        except queue.Empty:
            state["status"] = "error"
            state["msg"] = "OTP 입력 시간 초과"
            return

        otp_el = d.find_element(By.CSS_SELECTOR, SEL_OTP_INPUT)
        otp_el.clear()
        otp_el.send_keys(otp)
        d.find_element(By.CSS_SELECTOR, SEL_OTP_BTN).click()
        time.sleep(2)

        # GNB 나타날 때까지 대기 (로그인 완료 확인)
        WebDriverWait(d, 15).until(
            lambda drv: len(drv.find_elements(By.CSS_SELECTOR, ".gnb-ul")) > 0
        )
        state["dms_logged_in"] = True
        state["status"] = "idle"
        state["msg"] = "로그인 완료"

    except Exception as e:
        state["status"] = "error"
        state["msg"] = f"로그인 오류: {e}"

# ── 스크립트 실행 ──────────────────────────────────────────────────────────
def _run_py(script_name, *args):
    path = os.path.join(SCRIPTS_DIR, script_name)
    cmd  = [sys.executable, path] + list(args)
    env  = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        cwd=SCRIPTS_DIR, env=env
    )
    for line in proc.stdout:
        _log(line.rstrip())
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"{script_name} 실패 (종료코드 {proc.returncode})")

def _run_scripts(opt):
    try:
        if opt == 0:
            _log("▶ [1+2] Warranty Claim Detail + Status...")
            _run_py("bmwdms_update.py", "12")
            _log("▶ [3] TC Non-execution RawData...")
            _run_py("tc_missilsiryul_test.py")
        elif opt == 1:
            _log("▶ [1] Warranty Claim Detail...")
            _run_py("bmwdms_update.py", "1")
        elif opt == 2:
            _log("▶ [2] Warranty Claim Status...")
            _run_py("bmwdms_update.py", "2")
        elif opt == 3:
            _log("▶ [3] TC Non-execution RawData...")
            _run_py("tc_missilsiryul_test.py")
        elif opt == 4:
            _log("▶ [4] TC Verify Files...")
            _run_py("tc_export.py")
            _log("__DONE__")
            state["status"] = "done"
            state["msg"] = "완료"
            _notify_done(4)
            return

        _log("▶ 대시보드 업데이트 중...")
        _run_py("update_all.py")
        _log("__DONE__")
        state["status"] = "idle"
        state["dms_logged_in"] = False
        state["msg"] = "완료"
        _notify_done(opt)

    except Exception as e:
        _log(f"__ERROR__ {e}")
        state["status"] = "error"
        state["msg"] = str(e)
        _notify_failed(str(e))

# ── 진입점 ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"  DMS 트리거 서버 시작 (포트 5001)", flush=True)
    print(f"  토큰: {SECRET_TOKEN}", flush=True)
    print(f"  스케줄: 매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}", flush=True)
    print(f"  ntfy 채널: ntfy.sh/{NTFY_TOPIC}", flush=True)

    # Chrome 9222 없으면 자동 시작
    if not _chrome_alive():
        print("  Chrome 9222 시작 중...", flush=True)
        _start_chrome()

    threading.Thread(target=start_tunnel,    daemon=True).start()
    threading.Thread(target=_scheduler_loop, daemon=True).start()

    app.run(host="0.0.0.0", port=5001, threaded=True)
