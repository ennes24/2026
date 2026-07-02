# 기후변화 대응을 위한 미국 작물 생산량 예측 및 최적 배치

**Predict-then-Optimize for Climate-Resilient US Agriculture**
*ML Crop Yield Prediction + Constrained Allocation Optimization*

---

## 프로젝트 개요

기후변화는 미국 농업 생산성에 직접적인 영향을 미친다. 지역별 기온·강수·가뭄 등 기후 조건에 따라 작물 생산량이 달라지고, 동시에 물 부족 문제가 심화되면서 "어디에 무엇을 심을지"가 점점 더 중요한 의사결정이 되고 있다.

본 프로젝트는 이 문제를 **2단계 파이프라인**으로 푼다.

1. **예측 (Machine Learning)** — 기후·토양·농경지 데이터로 주요 작물(옥수수·대두·밀)의 지역별 수확량을 예측한다.
2. **최적화 (Optimization)** — 예측된 수확량을 입력으로, 제한된 토지와 물 자원 안에서 전체 식량 생산(또는 경제적 수익)을 최대화하는 작물 배치를 결정한다.

핵심은 두 단계의 **연결**이다. 기후 시나리오(평년 vs 가뭄·고온)를 1단계에 넣으면 작물별 예측 수확량이 달라지고, 그 결과 2단계의 최적 배치가 바뀐다. 이를 통해 *"기후가 악화될 때 작물 배치를 어떻게 조정하면 생산을 얼마나 지킬 수 있는가"*에 대한 정량적 근거를 제시한다.

---

## 왜 두 단계를 합치는가

| 단계 | 질문 | 기법 | 산출물 |
| --- | --- | --- | --- |
| 1. 예측 | "이 지역·이 기후에서 이 작물은 얼마나 나오나?" | 회귀 (ML) | 작물별 예측 수확량 |
| 2. 최적화 | "그럼 어디에 무엇을 얼마나 심어야 하나?" | LP / MIP | 지역별 최적 작물 배치 |

1단계의 예측 수확량이 2단계 목적함수의 **계수**로 그대로 들어간다. 예측만으로는 의사결정이 안 되고, 최적화만으로는 미래 기후를 반영할 수 없다. 둘을 합쳐야 "예측 → 의사결정"이 완성된다 (Predict-then-Optimize).

---

## 데이터에 대한 안내 (중요)

이 레포는 실제 USDA NASS / NOAA NCEI / US Drought Monitor / USGS API를 호출하는 대신, **동일한 스키마를 갖는 합성(synthetic) 데이터**를 `src/generate_synthetic_data.py`로 생성해서 사용한다. 실제 출처는 모두 API 키 등록과 대용량 벌크 다운로드가 필요해 일회성 에이전트 세션 안에서 재현 가능한 방식으로 받아오기 어렵기 때문이다.

합성 데이터는 작물별 농학적 특성(최적 생육 온도, 가뭄 민감도, 작물별 물 소요량 등)을 반영해 통계적으로 현실적인 기후↔수확량 관계를 만들도록 설계했다 (`src/generate_synthetic_data.py`의 `CROP_PARAMS`, `STATE_PROFILES` 참고). **실제 데이터로 교체하려면** `data/raw/` 아래 동일한 컬럼명의 CSV로 갈아끼우기만 하면 `data_loader.py` 이후 파이프라인은 그대로 동작한다.

**실제 데이터 받아오기**: `src/fetch_real_data.py`가 USDA NASS Quick Stats / NOAA NCEI / US Drought Monitor / USGS Water Use API를 직접 호출해 위 5개 CSV를 실제 데이터로 채워준다. USDA NASS와 NOAA NCEI는 무료 API 키가 필요하다 (각각 https://quickstats.nass.usda.gov/api , https://www.ncdc.noaa.gov/cdo-web/token 에서 이메일만 입력하면 즉시 발급). 발급받은 값은 레포 루트의 `.env` 파일(git-ignored)에 다음과 같이 넣는다.

```
USDA_NASS_API_KEY=...
NOAA_NCEI_TOKEN=...
```

```bash
pip install -r requirements.txt
python -m src.fetch_real_data
```

| 데이터 | 용도 | 단계 | 출처 (실 데이터 기준) |
| --- | --- | --- | --- |
| `usda_nass_yield.csv` | 작물별 수확량 | 1·2 공용 | https://quickstats.nass.usda.gov/ |
| `noaa_climate.csv` | 기온·강수 | 1 (피처) | https://www.ncei.noaa.gov/ |
| `drought_monitor.csv` | 가뭄지수 | 1 (피처) | https://droughtmonitor.unl.edu/ |
| `cropland_data_layer.csv` | 농경지 면적 | 2 (토지 제약) | https://www.nass.usda.gov/Research_and_Science/Cropland/ |
| `usgs_water_use.csv` | 농업용수 사용량 | 2 (물 제약) | https://www.usgs.gov/mission-areas/water-resources/science/water-use-data |

대상 범위: 12개 주요 곡물 생산 주(IA, IL, NE, MN, IN, KS, OH, SD, MO, ND, WI, TX) × 2000–2023년 × 3개 작물(옥수수·대두·밀).

> **현재 데이터 상태**: `data/raw/drought_monitor.csv`만 US Drought Monitor 실측 데이터(주간 D0–D4 area% 실측치를 연 단위로 집계, 2000년만 표본이 1주뿐이라 2001년 값으로 backfill)로 교체되어 있다. 나머지 4개(`usda_nass_yield.csv`, `noaa_climate.csv`, `cropland_data_layer.csv`, `usgs_water_use.csv`)는 여전히 합성 데이터다. **이 둘을 섞으면 학습 결과가 왜곡된다** — 합성 수확량은 합성 가뭄지수로부터 생성됐기 때문에, 실제 가뭄지수를 끼워 넣으면 그 인위적 상관관계가 깨져 `outputs/model_comparison.csv`의 R²가 하락한다 (특히 corn/soybean이 음수). 5개 소스를 전부 실제 데이터로 바꾸기 전까지는 `outputs/`의 수치를 실제 성능으로 해석하지 말 것.

---

## 1단계: 작물 생산량 예측 (ML)

**입력 변수 (Features)**: 평균/최고/최저기온, 강수량, 가뭄지수, 농경지 면적
**출력 변수 (Target)**: 작물 수확량 (bu/acre)

**모델**: Random Forest, XGBoost, LightGBM, CatBoost를 `RandomizedSearchCV` (5-fold CV)로 비교·튜닝한다. 평가는 연도 기준 시계열 분할(2018년 이전 학습 / 2019년 이후 테스트)로 수행해 실제 예보 상황을 흉내낸다.

**성능 평가**: RMSE, MAE, R² (`outputs/model_comparison.csv`)

구현: [`src/model.py`](src/model.py)

```bash
python -m src.model
```

---

## 2단계: 작물 배치 최적화

**의사결정 변수**: 각 주(State)에 재배할 작물별 면적 `x[state, crop]`

**목적함수**: 전체 작물 생산량(또는 경제적 수익) 최대화 = Σ (1단계 예측 수확량 × 면적)

**제약조건**
- 주별 농경지 면적 한계 (`available_land_acres`)
- 물 사용량 한계 — 작물별 물 소요량(acre-inch/acre)이 달라 트레이드오프 발생
- 작물별 최소 생산량 (기준 시나리오 최적 생산량의 일정 비율로 설정)

**최적화 기법**: PuLP (CBC solver) 기반 LP. `single_crop_per_state=True`로 호출하면 "한 주엔 한 작물만" 이진 제약을 추가한 MIP로 전환된다.

> **설계 노트**: 목적함수가 "총생산 최대화"뿐이면 최적해가 "가장 잘 나오는 작물만 전부 심기"로 수렴해 최적화가 시시해진다 (`src/optimizer.py`의 docstring과 `tests`/노트북에서 실제로 이 현상을 재현해 보였다). **물 사용량 제약**과 **작물별 최소 생산량 제약**이 동시에 binding되도록 설정해야 비로소 의미 있는 트레이드오프가 발생한다.

구현: [`src/optimizer.py`](src/optimizer.py)

---

## 연결: 기후 시나리오 분석

| 시나리오 | 1단계 입력 | 2단계 결과 |
| --- | --- | --- |
| `baseline` | 최근 5개년 평균 기후 | 기준 최적 배치 |
| `drought_heat` | 평균기온 +3°F, 강수량 ×0.75, 가뭄지수 +1.6 | 조정된 최적 배치 |

**핵심 분석** (`src/scenarios.py`): 기준 배치를 그대로 둔 채 기후가 악화됐을 때의 총생산(`drought_no_adaptation`) vs 재배치했을 때의 총생산(`drought_adapted`)을 비교한다. 그 차이가 *"적응(재배치)으로 지켜낸 생산량"*이며, `outputs/scenario_comparison.csv`와 `outputs/figures/scenario_comparison.png`에 정리된다.

```bash
python -m src.scenarios
```

---

## 실행 방법

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) 합성 원본 데이터 생성 (data/raw/)
python -m src.generate_synthetic_data

# 2) 전처리 (data/processed/panel.csv, state_constraints.csv)
python -m src.data_loader

# 3) 1단계: 작물별 수확량 모델 학습·비교 (outputs/models/, outputs/model_comparison.csv)
python -m src.model

# 4) 2단계 + 시나리오 연결: 기후 시나리오별 최적 배치 비교
python -m src.scenarios
```

또는 `notebooks/01_eda.ipynb` → `02_yield_prediction.ipynb` → `03_optimization.ipynb` 순서로 노트북을 실행해도 동일한 파이프라인을 단계별로 따라갈 수 있다.

---

## 레포 구조

```
.
├── README.md
├── requirements.txt
├── data/
│   ├── raw/              # 원본(합성) 데이터
│   └── processed/        # 정제된 패널 데이터 + 주별 제약조건
├── notebooks/
│   ├── 01_eda.ipynb              # 탐색적 분석
│   ├── 02_yield_prediction.ipynb # 1단계: ML
│   └── 03_optimization.ipynb     # 2단계 + 시나리오 연결
├── src/
│   ├── generate_synthetic_data.py # 합성 원본 데이터 생성
│   ├── data_loader.py             # 병합·피처 엔지니어링·제약조건 산출
│   ├── model.py                   # 1단계: 수확량 예측 모델
│   ├── optimizer.py               # 2단계: LP/MIP 배치 최적화
│   ├── scenarios.py               # 1단계 ↔ 2단계 연결, 기후 시나리오 비교
│   └── visualize.py                # 시각화 헬퍼
└── outputs/
    ├── models/            # 학습된 모델 (.joblib, git-ignored)
    ├── figures/           # 생성된 그래프
    ├── model_comparison.csv
    └── scenario_comparison.csv
```

---

## 기대 결과

- 미국 지역별 작물 생산량 예측 모델 (옥수수·대두·밀)
- 토지·물 제약 하의 지역별 최적 작물 배치 제안
- 기후변화가 생산성에 미치는 영향 및 적응 전략의 정량적 분석 ("재배치만으로 X% 더 생산 가능")
- 예측 → 최적화로 이어지는 의사결정 파이프라인

---

## 기술 스택

- **데이터/ML**: Python, pandas, scikit-learn, XGBoost, LightGBM, CatBoost
- **최적화**: PuLP (CBC solver)
- **시각화**: matplotlib, seaborn
