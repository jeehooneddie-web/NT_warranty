# 보증 매출 (BRANCH_DATA) 계산 로직

> `update_all.py` Step 3 (94~110줄)
> 원본: `2026 data RAW_Claim.xlsx` — sheet_name=2

---

## 1. 원본 컬럼 구조

| 인덱스 | 컬럼 | 용도 |
|--------|------|------|
| cols[1] | 상태 | '청구' 포함 여부 필터 |
| cols[5] | 지점 | AS_군산 등 |
| cols[8] | Task | 건수 집계 시 Task=1만 |
| cols[10] | Warranty Stage (K) | Claim Type 판별 |
| cols[12] | Defect Code (M) | Claim Type 판별 |
| cols[13] | 날짜 (N) | YY-MM 월 추출 |
| cols[22] | 금액 | 매출 합산 |

---

## 2. Claim Type 분류 로직

```
K열(Warranty Stage) 기준 우선:
  'goodwill' 포함  →  Goodwill
  'Warranty plus'  →  WP

M열(Defect Code) 기준:
  'LA' 포함        →  LOCAL TC
  숫자 변환 후:
    < 100,000,000  →  TC/RECALL
    > 8,700,000,000 AND NOT '99' 시작  →  BSI
    그 외           →  Warranty

예외: BSI인데 코드가 '99'로 시작  →  Warranty 재분류
```

---

## 3. 집계 기준

| 항목 | 기준 |
|------|------|
| 필터 | 상태(cols[1])에 '청구' 포함 |
| **건수(count)** | Task=1 행만 집계 |
| **금액(total)** | Task 무관 전체 집계 (중복 제거 없음) |

---

## 4. 결과 데이터 구조 (BRANCH_DATA)

```json
{
  "군산": {
    "25-01": {
      "BSI":      { "count": 117, "total": 45383974 },
      "Warranty": { "count": 30,  "total": 19713408 },
      "TC/RECALL":{ "count": 46,  "total": 19841939 },
      "Goodwill": { "count": 1,   "total": 3648904  },
      "WP":       { "count": 0,   "total": 0        },
      "LOCAL TC": { "count": 18,  "total": 1183280  }
    }
  }
}
```

---

## 5. 지점코드 매핑

| 코드 | 지점명 |
|------|--------|
| 26999 | 전주 |
| 40699 | 군산 |
| 41967 | 목포 |
| 419668 | 서산 |
| 44835 | 평택 |
| AS_군산 등 | 직접 변환 |

---

## 6. 대시보드 표시

- 차트: Chart.js 누적막대(지점별 타입별) + Total 라인
- KPI: 매출중심(A) / 균형형(C) 토글
- 필터: 지점 / 타입 / 년도 / 월별
