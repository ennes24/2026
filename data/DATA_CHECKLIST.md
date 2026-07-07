# 데이터 체크리스트 (담당·우선순위·다운로드 방법)

모형에서의 역할은 `PROJECT_PLAN.md` 6.3절(파라미터 표)과 8절 참고.
샌드박스에서 정부 사이트가 차단되므로, "다운로드" 항목은 팀원이 로컬에서 받아
`data/raw/`에 넣거나 세션에 업로드한다. "웹조사" 항목은 문헌·보도자료에서 수치를
찾아 출처와 함께 작은 표로 만들면 된다 (코드 아님, 문서 작업).

## 우선순위 P0 — 없으면 파이프라인 시작 불가

### ✅ 1. 가뭄지수 (확보 완료)
- `data/raw/drought_monitor.csv` — US Drought Monitor 실제 데이터 (12개 주, 2000-2023,
  주간 D0~D4를 연간 가중지수로 집계 완료)

### ⬜ 2. 주별 옥수수 생산량·수확량·재배면적 [다운로드]
- **역할**: ML 타깃 (Ŷᵢ), LP 제약 (3)의 우변
- **출처**: USDA NASS Quick Stats — https://quickstats.nass.usda.gov/
- **다운로드 방법** (한 번에 안 되면 Data Item별로 나눠서):
  1. Program: `SURVEY` / Sector: `CROPS` / Group: `FIELD CROPS` / Commodity: `CORN`
  2. Data Item에서 아래 3개 선택:
     - `CORN, GRAIN - PRODUCTION, MEASURED IN BU`
     - `CORN, GRAIN - YIELD, MEASURED IN BU / ACRE`
     - `CORN - ACRES PLANTED`
  3. Geographic Level: `STATE` / State: IA, IL, NE, MN, IN, KS, OH, SD, MO, ND, WI, TX
  4. Year: `2000`~`2023` / Period Type: `ANNUAL` / Period: `YEAR`
  5. 결과 화면 우측 상단 **Spreadsheet** 버튼 → CSV 저장
- **파일명**: `nass_corn.csv` (여러 개면 `nass_corn_production.csv` 등으로 나눠도 됨)

### ⬜ 3. 연도별 에탄올 의무량 (RVO) [웹조사 — 작은 표]
- **역할**: LP 제약 (1)의 M
- **출처**: EPA "Renewable Fuel Annual Standards" 페이지 (final volume 표) — 옥수수
  에탄올(conventional/implied) 기준, 2006~2023
- **형태**: 연도·의무량(billion gallons) 2열짜리 CSV면 충분. 출처 URL 기록.

### ⬜ 4. 주별 에탄올 공장 생산능력 Cᵢ [다운로드 — 작은 표]
- **역할**: LP 제약 (2)
- **출처**: EIA "U.S. Fuel Ethanol Plant Production Capacity" (연간 XLS, 주별 능력,
  2011~) — https://www.eia.gov/petroleum/ethanolcapacity/
  2011년 이전은 RFA(Renewable Fuels Association) 연례 Industry Outlook 보고서로 보완
- **형태**: 주·연도·능력(million gal/yr) CSV. 옥수수 환산(÷2.8)은 코드에서 처리.

## 우선순위 P1 — LP의 완성도를 좌우

### ⬜ 5. 주별 축산 사육두수 (사료 하한 Fᵢ 산정용) [다운로드]
- **역할**: LP 제약 (3), (5)
- **출처**: NASS Quick Stats (위와 동일한 사이트)
  - Sector: `ANIMALS & PRODUCTS` / Group: `LIVESTOCK`
  - Data Item: `CATTLE, ON FEED - INVENTORY`, `CATTLE, INCL CALVES - INVENTORY`,
    `HOGS - INVENTORY`
  - STATE / 12개 주 / 2000-2023
- **파일명**: `nass_livestock.csv`
- 두당 옥수수 소요량 계수는 웹조사(사료 배합 문헌값)로 별도 확보

### ⬜ 6. RIN 이월 재고 K [웹조사 — 문헌 확정됨]
- **역할**: LP 제약 (1) — "면제 실효성" 논쟁의 핵심 변수
- **핵심 인용**:
  - Tyner, Taheripour & Hurt (2012), "Potential Impacts of a Partial Waiver of the
    Ethanol Blending Rules" (Purdue) — 2012년 이월 RIN ~2.5-2.6B gal ≈ 옥수수 9억 bu
    상당, 면제 효과 $0.47~$1.30/bu (조건부)라는 실수치와 메커니즘의 원조
  - Irwin & Good, "An Update on RIN Stocks..." farmdoc daily (2012) 및 후속 시리즈 —
    연도별 RIN 재고 추정의 표준 공개 소스
    https://farmdocdaily.illinois.edu/2012/08/an-update-on-rin-stocks-and-im.html

### ⬜ 7. 수요탄력성 ε (사료·수출·식품 부문별) [웹조사 — 문헌 확정됨]
- **역할**: 목적함수 λ 보정, 바깥층 SC(X) 가격충격 계산
- **핵심 인용**: Roberts & Schlenker (2013), "Identifying Supply and Demand
  Elasticities of Agricultural Commodities: Implications for the US Ethanol Mandate",
  *American Economic Review* 103(6):2265-95 — 에탄올 의무제 평가 목적으로 추정된
  곡물 수요·공급 탄력성 (의무제의 가격효과 ~20%, CI 14-35%도 검증 기준값으로 사용).
  무료 PDF: https://www.nber.org/system/files/working_papers/w15921/w15921.pdf
- **보조**: EPA "Impacts of Ethanol Policy on Corn Prices: A Review" (부문별 추정치
  모음), Carter, Rausser & Smith (~40% 강효과 진영 — 감도분석 상한 시나리오),
  Frontiers in Energy Research (2022) RFS ex-post 평가 리뷰 (2012 백테스트 장에서
  "기존 연구는 전부 사후분석" 주장의 근거로도 인용)

### 📌 백테스트 직접 비교 대상: UNL 연구 (가장 가까운 선행연구)
- Dhoubhadel, Stockton & Azzam, "The Impact of Biofuels Policy and Drought on the
  U.S. Grain and Livestock Markets", *Journal of Agricultural and Applied Economics*
  — **"2012년 RFS를 23% 감축했으면 가뭄의 옥수수 가격 충격을 완전 상쇄"**라는 사후
  추정. 우리 모델이 2012 백테스트에서 내는 X*를 이 23%와 직접 비교한다.
  우리와의 차이(=우리 기여): 사후 vs 사전 예측 기반, 전국 단수치 vs 주별 배분,
  1개 연도 vs 심각도별 곡선.
  https://www.cambridge.org/core/journals/journal-of-agricultural-and-applied-economics/article/C634F113115722FBC306A710C9668587

### 상충 연구 4진영 정리 (감도분석의 시나리오 축)
| 진영 | 주장 | 우리 모델에서의 위치 |
|---|---|---|
| Carter, Rausser & Smith | 의무제 가격효과 ~40% (강효과) | 탄력성 하한(효과 큼) 시나리오 |
| Roberts & Schlenker (AER) | ~20% (CI 14-35%) | 기본(중앙) 시나리오 |
| 퍼듀 Tyner et al. | RIN 재고 크면 면제 실효 없음 (조건부) | K(RIN) 파라미터 상한 시나리오 |
| UNL Dhoubhadel et al. | 23% 감축이면 2012 충격 완전 상쇄 | 백테스트 X* 직접 비교 기준 |

## 우선순위 P2 — 개선·확장용 (없어도 1차 결과 가능)

### ⬜ 8. 생육기 기온·강수 [다운로드]
- ML 피처 보강용. NOAA Climate at a Glance에서 주별 시계열 CSV 다운로드 가능.
  1차 모델은 가뭄지수만으로 시작 가능하므로 후순위.

### ⬜ 9. 곡물 수송단가 τ [웹조사]
- USDA AMS Grain Transportation Report의 대표값 하나면 충분.

### ⬜ 10. 수출 하한 E [웹조사]
- USDA ERS Feed Grains Database 연간 수출량 → 최근 추세 하한으로 설정.

### ⬜ 11. 에탄올 산업 마진 [웹조사]
- 바깥층 SC(X)의 w₃ 항. Iowa State CARD의 에탄올 수익성 시계열(공개) 참고.

---

## 업로드 방식

- CSV/XLS/ZIP **원본 그대로** 올리면 됨 (컬럼 정리·집계는 코드에서 처리).
- 가뭄 데이터 때처럼 세션에 파일 업로드 또는 `data/raw/`에 커밋.

## 요약: 최소 시작 세트

**2번(NASS 옥수수) 하나만 받아오면** 1단계 ML(가뭄→생산량 예측)은 실데이터로 즉시
학습 가능. 3·4번(RVO·공장능력 작은 표)까지 오면 LP 기본형이 돌아감.
