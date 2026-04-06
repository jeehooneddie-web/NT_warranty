# National Motors 보증팀 사내 대시보드 — CLAUDE.md

> Agent 지침서. Claude Code가 이 프로젝트를 작업할 때 항상 먼저 읽는 파일.
> 마지막 갱신: 2026-04-06

---

## 1. 프로젝트 핵심 정보

| 항목 | 값 |
|------|-----|
| 배포 URL | https://jeehooneddie-web.github.io/NT_warranty/ |
| 메인 파일 | `dashboard-app/preview/index.html` (~635KB, 단일 파일 SPA) |
| Git 루트 | `d:/코딩/work for_` |
| 배포 방식 | push to main → GitHub Actions → GitHub Pages 자동 배포 |
| 배포 반영 | push 후 **1~3분** 소요 |

---

## 2. Agent 작업 규칙 (필독)

### 2-1. 파일 수정 원칙
```
index.html은 635KB 단일 파일 — 전체 출력 절대 금지
수정은 항상 str_replace 방식으로 최소 범위만 변경
수정 전 반드시 grep으로 대상 패턴·라인 확인 후 진행
```

```bash
# 패턴 확인 먼저
grep -n "view-xxx\|TARGET_PATTERN" "dashboard-app/preview/index.html" | head -20

# 라인 전후 50줄 확인 후 str_replace
```

### 2-2. 작업 완료 기준
요청 → 코드 수정 → git push → 완료를 한 번에 처리.
아래 경우만 예외적으로 사전 확인:
- 보안 관련 변경 (인증 로직, RLS 정책)
- 데이터 구조 변경 (기존 데이터 호환성에 영향)
- 2개 이상 뷰에 동시 영향을 주는 변경

### 2-3. git push 명령어
```bash
cd "d:/코딩/work for_" \
  && git add dashboard-app/preview/index.html \
  && git commit -m "메시지" \
  && git push
```

### 2-4. 응답 스타일
- 설명 최소화, 코드 우선
- MD 문서는 `MD/` + `memory/` 양쪽에 동시 저장
- 불필요한 확인 질문 최소화

---

## 3. 기술 스택

| 분류 | 기술 |
|------|------|
| UI | Tailwind CSS CDN / Lucide Icons CDN |
| 차트 | Chart.js |
| 드래그 | SortableJS |
| 번역 | Google Translate 무료 API |
| 인증/DB | Supabase Auth + REST (OTP, user_roles, menu_settings) |
| 상태 저장 | sessionStorage (로그인) / localStorage (테마·필터순서·메뉴캐시) |
| QR 스캔 | html5-qrcode@2.3.8 (CDN) |
| 고품 저장 | Google Apps Script 웹훅 + Google Sheets CSV |
| 서버 | 없음 — 순수 HTML + JS |

---

## 4. 인증 / 보안 구조

### 4-1. 인증 방식
```
이메일 OTP (6자리) — Supabase Auth + Gmail SMTP (smtp.gmail.com:587)
허용 도메인: @nationalmotors.co.kr + jeehoon.eddie@gmail.com
```

### 4-2. 로그인 플로우
```
이메일 입력 → 도메인 검증(프론트)
    → signInWithOtp({ email })
    → Gmail SMTP → OTP 발송
    → /auth/v1/verify 직접 fetch   ← SDK verifyOtp() 우회 (PKCE hanging 이슈)
    → access_token 수신 → _accessToken 전역 변수 저장
    → user_roles 조회 → applyRole() → 로그인 완료
```

### 4-3. 역할 체계
| 역할 | 레벨 | 접근 범위 |
|------|------|----------|
| `admin` | 3 | 전체 메뉴 + 구성원·메뉴 관리 |
| `member` | 2 | 관리자가 허용한 메뉴 |
| `user` | 1 | 번역기 전용 (비로그인) |

### 4-4. Supabase 클라이언트
```javascript
const SUPABASE_URL = 'https://vbvghhtroitmroxmfepr.supabase.co';
const SUPABASE_KEY = '...anon key...';  // public anon key — 하드코딩 무방
const _sb = supabase.createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: { flowType: 'implicit' }  // PKCE hanging 방지
});
let _accessToken = '';  // verifyOtp / _handleSession 시 저장
```

### 4-5. Supabase 테이블

#### user_roles
```sql
email      text PK
name       text
role       text   -- 'admin' | 'member' | 'user'
created_at timestamptz
```
RLS: 본인 행은 누구나 SELECT 가능 (`email = auth.jwt()->>'email'`), 수정·삭제는 admin만

#### menu_settings
```sql
key        text PK   -- 'view-sales', 'view-top-defect' 등
min_role   text      -- 'admin' | 'member' | 'all'
hidden     boolean
updated_at timestamptz
```
RLS: SELECT는 전체 공개, 수정은 admin만

#### my_role() 함수
```sql
-- security definer: RLS 재귀 무한루프 방지용
select role from public.user_roles where email = auth.jwt()->>'email' limit 1;
```

### 4-6. 메뉴 권한 로드 우선순위
```
1순위: Supabase menu_settings (anon key 공개 읽기)
2순위: localStorage 캐시
3순위: DEFAULT_MENU_CFG (코드 내 기본값 — 전부 admin)
```

### 4-7. 보안 절대 규칙
- `test.html`의 auto-login 코드를 `index.html`에 **절대 복사 금지**
- 배포본에 인증 우회 코드 잔존 금지
- RLS 정책 변경 시 반드시 확인 후 진행

---

## 5. 전체 뷰 목록

### 공개 뷰
| view ID | 메뉴명 | 설명 |
|---------|--------|------|
| view-dashboard | 대시보드 | 초기 진입 화면 |
| view-notices | 공지사항 | 공지 열람 |
| view-inquiries | 문의하기 | 일반 사용자 문의 |
| view-translator | 보증번역기 | 한→영 7개 항목 번역 |
| view-warranty | 보증기간 조회 | 디펙트코드별 보증기간 |
| view-qr-scanner | 고품 QR 스캔 | QR 스캔 → Google Sheets 저장 |
| view-qr-compare | 고품 QR 비교 | 로그인 없이 접근 가능 |

### 관리자 전용 (숨김 — 사이드바 미노출)
| view ID | 메뉴명 | 설명 |
|---------|--------|------|
| view-admin-inquiries | 문의 관리 | 문의 답변·처리 |
| view-admin-notices | 공지 관리 | 공지 작성·수정·삭제 |

### 관리자 전용 (admin-only, 사이드바 노출)
| view ID | 메뉴명 | 데이터 변수 | 설명 |
|---------|--------|------------|------|
| view-sales | 보증 매출 | `BRANCH_DATA` | Chart.js 누적막대 |
| view-top-defect | TOP DEFECT | `DEFECT_RAW` | 상위 20개 |
| view-person | 개인별 청구현황 | `PERSON_DATA`, `PERSON_DAILY` | 월별/순위/일별 |
| view-tc | TC 미실시율 | `TC_DATA` | 지점별 미실시율 |
| view-tc-top20 | TC 미실시 TOP20 | `TC_DATA` | view-tc 하위 |
| view-claim | 클레임 검토 | `CLAIM_DATA` | 불승인/보완요청/완료 |
| view-wholesale | 클레임 볼륨 | `WHOLESALE_DATA` | 보증마감/회계마감 |
| view-qr-match | 고품 반납 현황 | `QR_CLAIM_DATA` | QR↔클레임 매칭 |
| view-qr-location | 고품 로케이션 조회 | — | 위치 조회·수정 |
| view-user-mgmt | 사용자 관리 | Supabase `user_roles` | — |
| view-admin-menus | 메뉴 관리 | Supabase `menu_settings` | 메뉴 노출 설정 |

---

## 6. 데이터 변수 구조

> 모든 변수는 `update_all.py`가 `index.html`에 regex로 embed

```javascript
// 보증 매출 — 지점 > 월 > ClaimType > {count, total}
const BRANCH_DATA = { "군산": { "26-01": { "BSI": { count: 117, total: 45383974 }, ... } } };

// TOP DEFECT — [지점, 월, ClaimType, DefectCode, 건수, 금액]
const DEFECT_RAW  = [ ["군산", "26-01", "BSI", "LA0001234KR", 3, 1500000], ... ];

// 디펙트코드 설명 — { 코드: "설명" }
const DEFECT_DESC = { "LA0001234KR": "엔진 오일 누유", ... };  // 약 12,700개

// 미매칭 코드 — [{ code, count, amount }]
const DEFECT_UNMATCHED = [ { code: "...", count: 5, amount: 2500000 }, ... ];

// 개인별 청구 — [담당자ID, 월, ClaimType, 상태, 건수, 금액]
// '전체합계' 행 포함 (Task 필터 없이 전체 집계)
const PERSON_DATA = [ ["홍길동", "26-01", "BSI", "청구", 5, 12000000], ... ];

// 일별 현황 (당월만) — [담당자ID, 날짜, ClaimType, 건수, 금액]
const PERSON_DAILY = [ ["홍길동", "26-03-15", "BSI", 2, 5000000], ... ];

// TC 미실시율 — 지점 > 월 > {total, n_count}
const TC_DATA = { "군산": { "26-01": { total: 168, n_count: 79 } } };
// 미실시율(%) = n_count / total × 100

// TC 캠페인별 미실시 집계 — [지점, 월, 캠페인코드, 캠페인명, total, n_count]
const TC_TOP_DATA = [ ... ];

// 당월 발행 TC (발행월==입고월) — 동일 구조
const TC_SAME_MONTH_DATA = [ ... ];

// 클레임 검토 — [클레임번호, 지점, 클레임상태, WarrantyStage, ClaimType,
//               DefectCode, 날짜, 금액, 담당확인자, 차대번호, Credit수신일자]
// [10] Credit수신일자: 클레임현황 시트에서 승인대기 행의 수신일자 매핑
const CLAIM_DATA = [ ... ];

// 클레임 볼륨 — 기준 > ClaimType > 월 > { charge, approve, pending }
// 기준: '보증마감' | '회계마감'
// 각 항목: { amount, parts, count }
// 승인대기는 보증마감기준(U열) 없음 → 클레임확정월(S열) 기준으로 별도 집계
const WHOLESALE_DATA = { "보증마감": { "BSI": { "26-01": { charge: {...}, approve: {...}, pending: {...} } } } };

// 고품 반납 매칭 — [클레임번호(WC제거), DefectCode, 차대번호뒤7, 지점, 클레임생성일, 타입]
// 기준: 2026년 이상 + WC로 시작하는 클레임번호 + 상태='청구'
const QR_CLAIM_DATA = [ ["248610", "6312356700", "CE31331", "전주", "2026-03-18", "Warranty"], ... ];
```

---

## 7. ClaimType 분류 로직

> BRANCH_DATA·DEFECT_RAW·QR_CLAIM_DATA 공통 사용

```
K열(Warranty Stage) 기준 우선:
  'goodwill' 포함          →  Goodwill
  'warranty plus' 포함     →  WP

M열(Defect Code) 기준:
  'LA' 포함                →  LOCAL TC
  숫자 변환 후:
    < 100,000,000          →  TC/RECALL
    > 8,700,000,000
    AND NOT '99' 시작      →  BSI
    그 외                  →  Warranty

예외: BSI인데 코드가 '99'로 시작  →  Warranty 재분류
```

---

## 8. 원본 엑셀 파일 구조

### 파일 1: `2026 data RAW_Claim.xlsx`
**경로:** `C:\Users\user\OneDrive - 내쇼날모터스\보증팀 원드라이브\1. Warranty Claim RAW\`

| 시트명 | 행수 | 주요 역할 |
|--------|------|----------|
| `Claim 상세_전체` | 116,277행 × 32열 | BMW DMS RAW — `update_all.py` 주 처리 대상 |
| `클레임현황` | 46,562행 × 25열 | 집계 데이터 — 파일2가 SUMIFS로 참조 |
| `KR REJECT LIST_RAW` | 38행 | KR Reject 수동 관리 |
| `마감 캘린더` | 112행 | 마감 날짜 관리 |

#### Claim 상세_전체 주요 열 (update_all.py 참조 인덱스)
| 인덱스 | 열 | 용도 |
|--------|-----|------|
| cols[1] | B | 청구/취소 구분 |
| cols[5] | F | 지점 (AS_ 포함) |
| cols[6] | G | 클레임상태 (불승인/보완요청/보완완료) |
| cols[7] | H | 클레임번호 |
| cols[8] | I | Task (1만 집계하는 뷰 있음) |
| cols[10] | K | Warranty Stage |
| cols[11] | L | Claim Type |
| cols[12] | M | Defect Code |
| cols[13] | N | 클레임생성일자 |
| cols[18] | S | 차대번호 |
| cols[22] | W | 총클레임금액 |
| cols[23] | X | 담당자 |

### 파일 2: `2026_STAGE2,3 Whole sale data_ Total.xlsx`
파일1 `클레임현황`을 외부 참조(SUMIFS)하여 월별/유형별 집계. Excel 참조 파일이며,
`update_all.py`는 파일1의 `클레임현황` 시트를 직접 읽어 WHOLESALE_DATA를 집계 (파일2 미사용).
시트 3개: `클레임 PART only_RAW(보증마감기준)` / `클레임 PART only_RAW(회계마감기준)` / `클레임 청구 볼륨_RAW`

---

## 9. 데이터 업데이트 흐름

```
C:\Users\user\Desktop\업데이트.bat 더블클릭
    └→ 1. DATA/update_all.py 실행

처리 순서 (실제 줄번호 기준):
  Step 2  (44~95줄)    RAW 클레임 읽기 + ClaimType 계산
  Step 3  (97~114줄)   BRANCH_DATA   ← Claim 상세_전체 sheet_name=2
  Step 4  (116~121줄)  디펙트코드 리스트 읽기
  Step 5  (123~147줄)  DEFECT_RAW·DESC·UNMATCHED
  Step 6  (149~200줄)  PERSON_DATA·PERSON_DAILY
  Step 7  (202~287줄)  TC_DATA·TC_TOP_DATA·TC_SAME_MONTH_DATA ← RecallTcRptRawData.xlsx
  Step 8  (289~334줄)  CLAIM_DATA (+ Credit수신일자 매핑)
  Step 8-0(397~445줄)  QR_CLAIM_DATA ← Claim 상세_전체
  Step 9  (336~395줄)  WHOLESALE_DATA← 클레임현황 시트 (직접 읽기)

    ↓ 집계 완료
각 변수 → index.html에 regex embed
    ↓
git push → GitHub Pages 배포
```

### TC 자동화 별도 흐름
```
tc_missilsiryul_test.py
    → DMS(RecallTcRptRawData) 자동 다운로드
    → RecallTcRptRawData.xlsx → OneDrive 저장
    → update_all.py Step 7에서 처리
```

---

## 10. 지점코드 매핑

```javascript
// update_all.py 및 QR 스캐너 공통
const DEALER_MAP = {
  '26999':  '전주',
  '40699':  '군산',
  '41967':  '목포',
  '41968':  '서산',   // QR에서는 '41968'
  '419668': '서산',   // 클레임 RAW에서는 '419668'
  '44835':  '평택',
  'AS_군산': '군산',
  'AS_목포': '목포',
  'AS_서산': '서산',
  'AS_전주': '전주',
  'AS_평택': '평택'
};
```

> **주의:** 서산 딜러코드가 파일마다 다름 (`41967` vs `41968` vs `419668`) — 수정 시 반드시 확인

---

## 11. QR 스캐너 / 고품 반납 구조

### QR 데이터 필드 (쉼표 구분 CSV, 17필드)
| 인덱스 | 필드 | 예시 |
|--------|------|------|
| f[0] | Dealer No | 26999 |
| f[1] | 클레임번호 | 248610 |
| f[2] | 차대번호 | CE31331 |
| f[3] | 모델 | JR51 |
| f[4] | 디펙트코드 | 6312356700 |
| f[7] | 수리일 | 260319 → 2026-03-19 변환 |
| f[9] | 부품번호 | 63117214939 |
| f[10] | 부품명 | LED module |
| f[11] | Part 순서 | 1 |
| f[12] | 전체 Part 수 | 4 |

### Google Sheets 연동
```
QR_WEBHOOK_DEFAULT  : POST → Apps Script → Sheets 행 추가
QR_CSV_URL          : GET  → 공개 CSV (CORS 우회용)
localStorage 키     : qr_scans_today (당일 스캔 목록)
```

### 고품 반납 매칭 로직
```javascript
// WC 접두어 정규화
const normNo = v => String(v).replace(/^WC/i, '').trim();

// scanMap: 클레임번호 → 최초 수거일자
// _qmResults: { no, defect, vin7, branch, date, type, matched, scanDate }

// 타입 pill 필터: [전체][Warranty][TC/RECALL][Goodwill][WP][BSI][LOCAL TC]
// BSI·LOCAL TC는 반납 대상 아님 — pill로 분리 확인
```

---

## 12. 신규 뷰 추가 패턴

```
1. 사이드바 nav-item 추가 (admin-only 여부 결정)
2. VIEW_TITLES['view-xxx'] = '제목' 등록
3. <div id="view-xxx" class="view hidden"> HTML 작성
4. showView() 내 렌더 함수 호출 추가
5. update_all.py에 집계 + embed regex 추가 (데이터 필요 시)
6. MD/0X_뷰명_변수명.md 작성 후 MD/ + memory/ 양쪽 저장
```

---

## 13. 환경 차이

| 항목 | test.html | index.html (배포) |
|------|-----------|-------------------|
| 로그인 | auto-login 있음 | OTP 필수 |
| 보안 규칙 | 느슨함 | 엄격 적용 |
| 용도 | 로컬 개발 확인 | 실제 배포 |

> test.html 코드를 index.html에 그대로 가져오지 않는다.

---

## 14. 알려진 이슈 & 주의사항

```
⚠ Supabase verifyOtp() hanging  → /auth/v1/verify 직접 fetch로 우회 (수정 금지)
⚠ setSession() hanging           → non-blocking .catch(()=>{}) 처리 (수정 금지)
⚠ RLS 재귀 무한루프              → my_role() security definer 함수로 해결 (수정 금지)
⚠ 서산 딜러코드 불일치           → 41967 / 41968 / 419668 혼재 — 매핑 확인 필수
⚠ 승인대기 WHOLESALE_DATA        → 보증마감기준(U열) 없음, 클레임확정월(S열) 별도 집계
⚠ QR 스캔                        → HTTPS 환경에서만 카메라 동작
⚠ Google Translate 무료 API      → 과도한 요청 시 차단 가능
⚠ Chart.js BRANCH_DATA           → 구조 변경 시 렌더 함수도 함께 수정
⚠ SortableJS 필터 순서           → localStorage 저장 — 초기화 시 localStorage 삭제
⚠ DEFECT_DESC 매칭률             → 약 97% (나머지 DEFECT_UNMATCHED로 분리)
```

---

## 15. 배포 후 검증 체크리스트

```
□ git push 완료 확인
□ 1~3분 후 배포 URL 접속
□ 수정된 뷰 직접 확인
□ admin / member 권한 분리 정상 여부
□ 브라우저 콘솔 에러 없음
□ 모바일 레이아웃 이상 없음 (필요 시)
```

---

## 16. 에러 발생 시 디버그 순서

```
1. 브라우저 콘솔 에러 메시지 확인
2. grep으로 관련 함수·변수 위치 파악
3. 해당 뷰의 MD/0X 파일 참조
4. 인증 관련 → _accessToken 값, RLS 정책 확인
5. 데이터 관련 → update_all.py 마지막 실행 로그 확인
6. QR 관련 → QR_WEBHOOK_DEFAULT / QR_CSV_URL URL 유효성 확인
```

---

## 17. 상황별 참조 파일

| 상황 | 참조 파일 |
|------|----------|
| UI 색상·컴포넌트 수정 | `memory/ui_design_system.md` |
| 지점명·딜러코드 오류 | `memory/dealer_branch_mapping.md` |
| 보증매출 집계 로직 | `MD/01_보증매출_BRANCH_DATA.md` |
| TOP DEFECT 로직 | `MD/02_TOP_DEFECT.md` |
| 개인별 청구현황 로직 | `MD/03_개인별청구현황_PERSON_DATA.md` |
| TC 미실시율 로직 | `MD/04_TC미실시율_TC_DATA.md` |
| 클레임 검토 로직 | `MD/05_클레임검토_CLAIM_DATA.md` |
| 클레임 볼륨 로직 | `MD/06_클레임볼륨_WHOLESALE_DATA.md` |
| QR 스캐너 구조 | `MD/07_고품QR스캐너.md` |
| 고품 반납 현황 구조 | `MD/08_고품수거비교.md` |
| 인증·RLS·메뉴 권한 | `MD/09_로그인_보안_AUTH.md` |
| 엑셀 파일 구조 (RAW_Claim, Wholesale) | `MD/파일구조_설명.md` |
| MD 저장 규칙 | `MD/00_MD_관리규칙.md` |

---

## 18. MD 파일 관리 규칙

```
새 MD 파일 → 항상 두 곳 동시 저장:
  ① d:/코딩/work for_/MD/          (Git, Claude Code 접근)
  ② C:/Users/user/OneDrive - 내쇼날모터스/보증팀 원드라이브/MD/  (공유·백업)

네이밍: 번호_카테고리명_데이터명.md
결과 스냅샷: 결과/ 하위 폴더에 저장
```
