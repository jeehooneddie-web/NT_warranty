# 고품 로케이션 조회 (view-qr-location)

> 구현 완료: 2026-04
> 관리자 전용 (`admin-only`)

---

## 1. 기능 개요

고품 QR 스캔 시 저장된 로케이션 탭 데이터를 조회하고,
위치(R열) 값을 인라인으로 수정해 Google Sheet에 반영하는 뷰.

---

## 2. 데이터 소스

| 항목 | 값 |
|------|-----|
| CSV URL 상수 | `QR_LOC_CSV_URL` (`gid=1388680909`, 로케이션 탭 공개 게시) |
| 쓰기 엔드포인트 | `QR_WEBHOOK_DEFAULT` (Apps Script, action=`update_location`) |
| localStorage 오버라이드 | `qr_webhook_url` 키 — 없으면 DEFAULT 사용 |

---

## 3. 로케이션 탭 컬럼 구조 (0-indexed)

| 인덱스 | 열 | 내용 |
|--------|----|------|
| 0 | A | 스캔시간 |
| 2 | C | 지점 |
| 3 | D | 클레임번호 |
| 4 | E | 차대번호 |
| 6 | G | 디펙트코드 |
| 17 | R | 위치 (수정 대상) |

헤더 감지: `allRows[0][3] === '클레임번호'` 여부로 자동 판단

---

## 4. 주요 함수

| 함수 | 역할 |
|------|------|
| `runQRLocation()` | CSV fetch → 헤더 파싱 → 필터 → 테이블 렌더 |
| `editLocRow(rowId, sheetRow, locEnc)` | 위치 셀을 inline input으로 교체 |
| `cancelLocEdit(rowId, locEnc)` | 수정 취소 → 원래 값 복원 |
| `saveLocRow(rowId, sheetRow, locEnc)` | Apps Script POST → 성공 시 셀 업데이트 |
| `resetQRLocation()` | 필터 초기화 |

---

## 5. sheetRow 계산 방식

```javascript
const hasHeader = String(allRows[0]?.[3] || '').trim() === '클레임번호';
const headerOffset = hasHeader ? 1 : 0;
const dataRows = allRows.slice(headerOffset).filter(r => r[COL.claimNo]);
_qlRows = dataRows.map((r, i) => ({
  r,
  sheetRow: i + headerOffset + 1  // 1-indexed, 헤더 포함
}));
```

→ `sheetRow`를 직접 Apps Script에 전달해 `sheet.getRange(sheetRow, 18).setValue(...)` 실행

---

## 6. Apps Script update_location 액션

```javascript
// POST body (Content-Type: text/plain — CORS preflight 우회)
{
  action: 'update_location',
  sheetRow: 5,           // 1-indexed 시트 행번호
  newLocation: 'A-01',   // 새 위치값
  sheetName: '로케이션'
}

// 성공 응답
{ status: 'ok', row: 5 }
```

---

## 7. 필터 항목

| 필터 ID | 대상 컬럼 |
|---------|----------|
| `ql-branch` | 지점 (COL.branch) |
| `ql-claim` | 클레임번호 (COL.claimNo) |
| `ql-chassis` | 차대번호 (COL.chassisNo) |
| `ql-defect` | 디펙트코드 (COL.defectCode) |

---

## 8. 주요 이슈 이력

| 이슈 | 원인 | 해결 |
|------|------|------|
| 위치가 "16"으로 표시 | 하드코딩된 컬럼 인덱스 오류 | 헤더 기반 동적 매핑으로 수정 |
| 저장해도 Sheet 미반영 | localStorage에 구버전 webhook URL 잔존 | 페이지 로드 시 구버전 URL 자동 삭제 로직 추가 |
| "Failed to fetch" | `application/json` → CORS preflight 실패 | `Content-Type: text/plain`으로 변경 |
| `no-cors`로 오류 숨김 | opaque response → 응답 읽기 불가 | `mode: 'no-cors'` 제거, 응답 텍스트 직접 파싱 |
