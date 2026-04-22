"""
DMS 트리거 서버 — BMW DMS 자동 업데이트를 모바일에서 실행
  - Selenium으로 기존 Chrome(CDP 9222) 세션 재사용
  - OTP 중계: 모바일 /otp → Selenium이 DMS OTP 입력창에 전달
  - SSE로 실행 로그 스트리밍
"""

import os, sys, json, queue, threading, socket, time, subprocess
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
SECRET_TOKEN = os.environ.get("DMS_TOKEN", "nm-dms-2026")
CHROME_PORT  = 9222
SCRIPTS_DIR  = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "1. DATA"))

# DMS 로그인 셀렉터 — DMS 화면 확인 후 수정 필요
SEL_USER_ID   = '#userId'
SEL_LOGIN_BTN = '#loginBtn'
SEL_OTP_INPUT = '#otpNo'
SEL_OTP_BTN   = '#otpConfirmBtn'

# ── 전역 상태 ──────────────────────────────────────────────────────────────
state = {
    "chrome_ok":    False,
    "dms_logged_in": False,
    "status": "idle",   # idle | logging_in | waiting_otp | running | done | error
    "msg": "",
    "option": None,
}
otp_q = queue.Queue(maxsize=1)
log_q = queue.Queue()

# ── 헬퍼 ──────────────────────────────────────────────────────────────────
def _check_token():
    t = request.headers.get("X-Token") or request.args.get("token")
    return t == SECRET_TOKEN

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
@app.route("/status")
def get_status():
    if not _check_token():
        return jsonify({"error": "unauthorized"}), 401
    state["chrome_ok"] = _chrome_alive()
    if state["chrome_ok"] and state["status"] == "idle":
        try:
            d = _get_driver()
            found = _find_dms_window(d)
            state["dms_logged_in"] = found and "login" not in d.current_url.lower()
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
        d = _get_driver()
        # DMS 탭 없으면 새 탭 열기
        if not _find_dms_window(d):
            d.execute_script("window.open('https://www.bmwdms.co.kr/')")
            time.sleep(3)
            _find_dms_window(d)

        # 이미 로그인 확인
        if "bmwdms.co.kr" in d.current_url and "login" not in d.current_url.lower():
            state["dms_logged_in"] = True
            state["status"] = "idle"
            state["msg"] = "이미 로그인됨"
            return

        # 로그인 페이지로 이동
        if "login" not in d.current_url.lower():
            d.get("https://www.bmwdms.co.kr/")
            time.sleep(2)

        wait = WebDriverWait(d, 20)
        # ID 필드 클릭 → Chrome 자동완성 유발
        id_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL_USER_ID)))
        id_el.click()
        time.sleep(0.5)
        id_el.send_keys(Keys.DOWN)
        time.sleep(0.8)

        # 로그인 버튼
        d.find_element(By.CSS_SELECTOR, SEL_LOGIN_BTN).click()
        time.sleep(2)

        # OTP 입력창 대기
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL_OTP_INPUT)))
        state["status"] = "waiting_otp"
        state["msg"] = "OTP를 입력하세요 (2분 내)"

        # 모바일 OTP 대기
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
        time.sleep(3)

        state["dms_logged_in"] = True
        state["status"] = "idle"
        state["msg"] = "로그인 완료"

    except Exception as e:
        state["status"] = "error"
        state["msg"] = f"로그인 오류: {e}"

# ── 스크립트 실행 ──────────────────────────────────────────────────────────
def _run_py(script_name, *args):
    path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = [sys.executable, path] + list(args)
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", cwd=SCRIPTS_DIR
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
            return

        # 옵션 0~3은 항상 대시보드 업데이트
        _log("▶ 대시보드 업데이트 중...")
        _run_py("update_all.py")
        _log("__DONE__")
        state["status"] = "idle"
        state["dms_logged_in"] = False
        state["msg"] = "완료 — 대시보드 새로고침 하세요"

    except Exception as e:
        _log(f"__ERROR__ {e}")
        state["status"] = "error"
        state["msg"] = str(e)

# ── 진입점 ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"  DMS 트리거 서버 시작 (포트 5001)")
    print(f"  토큰: {SECRET_TOKEN}")
    print(f"  스크립트 경로: {SCRIPTS_DIR}")
    app.run(host="0.0.0.0", port=5001, threaded=True)
