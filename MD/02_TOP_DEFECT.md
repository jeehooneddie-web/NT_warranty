# TOP DEFECT (DEFECT_RAW / DEFECT_DESC / DEFECT_UNMATCHED) 계산 로직

> `update_all.py` Step 4~5 (112~143줄)
> 원본: `2026 data RAW_Claim.xlsx` + `디펙트코드 리스트.xlsx`

---

## 1. 원본 컬럼 구조

| 인덱스 | 컬럼 | 용도 |
|--------|------|------|
| cols[5] | 지점 | 집계 기준 |
| cols[12] | Defect Code (M) | 디펙트코드 |
| cols[13] | 날짜 (N) | YY-MM 월 추출 |
| cols[22] | 금액 | 금액 합산 |

---

## 2. 집계 기준

- 보증매출(BRANCH_DATA)과 동일 필터: **상태='청구'**, **Claim Type 유효**
- 지점+월+타입+디펙트코드 기준으로 **건수(count), 금액(amount) 합산**
- Task 필터 없음 (전체 행 집계)

---

## 3. 결과 데이터 구조

### DEFECT_RAW
```
[ 지점, 월, ClaimType, DefectCode, 건수, 금액 ]

예) ["군산", "26-01", "BSI", "LA0001234KR", 3, 1500000]
```
총 약 6,900개 행

### DEFECT_DESC
```json
{ "LA0001234KR": "엔진 오일 누유", ... }
```
약 12,700개 코드 설명 (매칭률 97%)

### DEFECT_UNMATCHED
```json
[
  { "code": "LA0001234KR", "count": 5, "amount": 2500000 },
  ...
]
```
미매칭 코드 목록 (주로 LAxxxxxxKR 형태)

---

## 4. 디펙트코드 매칭 로직

```
디펙트코드 리스트.xlsx (col[0]=코드, col[1]=설명) 읽기
    ↓
DEFECT_RAW의 각 코드를 리스트에서 조회
    ↓
매칭 성공  →  DEFECT_DESC에 추가
매칭 실패  →  DEFECT_UNMATCHED에 추가
```

---

## 5. 대시보드 표시

- 필터: 지점 / 타입 / 년도 / 월별 (보증매출과 독립 상태)
- 정렬: 건수순 / 금액순
- 탭: 상위 20개 / 미매칭 코드
- 미매칭 탭: CSV 내보내기 버튼
