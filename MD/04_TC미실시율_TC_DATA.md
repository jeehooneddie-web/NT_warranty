# TC 미실시율 (TC_DATA) 계산 로직

> `update_all.py` Step 7 (198~220줄)
> 원본: `RecallTcRptRawData.xlsx` (DMS → 리포트 → RECALL/TC → 지점별 미실시 현황 → RawData 다운로드)

---

## 1. 원본 RawData 컬럼 구조

| 인덱스 | 컬럼명 | 용도 |
|--------|--------|------|
| [1] | 캠페인코드 | 중복 제거 키 |
| [4] | 차량번호 | 중복 제거 키 |
| [5] | 날짜 | 월(YY-MM) 추출 |
| [6] | 딜러(지점) | 지점명 (`AS_군산` 등) |
| [9] | 결과값 | `N` = 미실시 판정 기준 |
| [11] | RO번호 | 유효 행 필터링 |

---

## 2. 계산 순서

### Step 1 — 중복 제거
```
캠페인코드 + 차량번호 + 딜러 + RO번호 기준 dedup
```

### Step 2 — 유효 행 필터링
```
RO번호가 비어있는 행 제외 (NaN 또는 빈 문자열)
```

### Step 3 — 지점명 정리
```
AS_군산 → 군산 / AS_목포 → 목포 / AS_서산 → 서산
AS_전주 → 전주 / AS_평택 → 평택
```

### Step 4 — 월 추출
```
날짜(col[5]) → pd.to_datetime → strftime('%y-%m')
예) 2026-01-15 → 26-01
```

### Step 5 — 미실시 판정
```
결과값(col[9]) == 'N'  →  is_N = True  (미실시)
결과값(col[9]) != 'N'  →  is_N = False (실시 완료)
```

### Step 6 — 지점 + 월별 집계
```
total   = 해당 지점+월의 전체 행수 (방문대수)
n_count = is_N == True 인 행수      (미실시 대수)
```

---

## 3. 결과 데이터 구조 (TC_DATA)

```json
{
  "군산": {
    "26-01": { "total": 168, "n_count": 79 },
    "26-02": { "total": 123, "n_count": 45 }
  }
}
```

---

## 4. 미실시율 계산 (대시보드 렌더링 시)

```
미실시율(%) = n_count / total × 100
```

- 월 복수 선택 시: 선택 월의 total, n_count 합산 후 계산
- 분기 선택 시: 해당 분기 월(Q1=01~03월) 합산 후 계산

---

## 5. DMS 조회 설정

| 항목 | 값 |
|------|----|
| 조회기간 | 분기 시작일 ~ 오늘 (자동 계산) |
| 딜러 | 001632 내쇼날 모터스 |
| 사업장 | 전체 |
| 지점 | 선택 (전체) |
| 다운로드 | RawData 다운로드 (`btnRawDataExcelDownload`) |
| Kendo 위젯 | `kendoExtMaskedDatePicker` (DatePicker API) |

---

## 6. 자동화 흐름

```
DMS 지점별 미실시 현황
    ↓  (tc_missilsiryul_test.py)
RecallTcRptRawData.xlsx  →  OneDrive 저장
    ↓  (update_all.py Step 7)
TC_DATA 집계
    ↓  (HTML regex embed)
index.html 갱신  →  git push  →  GitHub Pages
```
