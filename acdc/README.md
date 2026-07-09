# ACDC 옥수수·대두 분석 — 파일 안내

ACDC(Agro-Climatic Data by County, 1981–2015) 실데이터로 만든 **예측(ML) → 최적화** 파이프라인.
전체 서술 리포트는 **[REPORT.md](REPORT.md)**, 시각 리포트는 `report.html`.

## 한 번에 실행
```bash
cd acdc
python3 run_all.py        # EDA → 온도EDA → 모델 → 예측1/2 → 2단계 최적화 전부
```

## 폴더 구조
```
acdc/
├── REPORT.md            # 전체 분석 서술(한국어) — 여기부터 읽으세요
├── report.html          # 임베디드 차트 시각 리포트(아티팩트)
├── run_all.py           # 전체 파이프라인 실행
├── build_artifact.py    # report.html 생성
├── data/
│   ├── yielddata.csv     # 타깃: 카운티 작물 수확량 (bu/ac)
│   ├── pptMarAug.csv     # 피처: 생육기 강수 (mm)
│   ├── soil2011.csv      # 피처: 토양 (보수력·유기물·pH 등)
│   └── gdd_slim.csv      # 피처: 온도 GDD(유익열)·EDD(극한고온)  [압축본]
├── src/
│   ├── prepare.py        # 병합·피처·추세/기상충격 분해 (gdd_slim 자동 인식)
│   ├── eda.py            # EDA 그림 01–05 (추세·강수·토양·취약도·상관)
│   ├── eda_temp.py       # 온도 EDA 그림 13–16 (EDD 타임라인·반응·민감도)
│   ├── models_compare.py # [트랙1] 수확량 다중모델 비교 OLS/Ridge/Lasso/RF/GBM
│   ├── train.py          # [트랙1] 수확량 ML 학습·평가·해석·2012 스트레스
│   ├── weather_eda.py    # [트랙2] 날씨 예측 EDA (W1–W4: 분산분해·자기상관)
│   ├── weather_ml.py     # [트랙2] 날씨 예측 ML (climatology가 ML을 이김)
│   ├── climate_model.py  # [트랙2] 기후 모델 A (warming hole + 온난화 시나리오)
│   ├── scenario.py       # 예측1(생산성 지도) · 예측2(기후 시나리오)
│   ├── optimizer.py      # 2단계: 전환비용 감안 연속 LP 배치 (PuLP)
│   └── optimize_meta.py  # [v3] Phase4-5 단작 조합최적화 GA/SA vs MILP
├── tools/
│   └── shrink_gdd.py     # 큰 GDD 원본을 gdd_slim.csv로 압축(로컬 실행용)
├── figures/             # 생성 그림 01–18
└── outputs/             # model_*.json, scenario_*.csv, optimization.csv 등
```

## 그림 인덱스
| # | 파일 | 내용 |
|---|---|---|
| 01 | trend_and_shocks | 기술추세 + 기상충격 분해 |
| 02 | precip_response | 강수 언덕형 반응 |
| 03 | soil_whc | 토양 보수력 완충 |
| 04 | state_vulnerability | 주별 기상 취약도 |
| 05 | correlations | 피처 상관 |
| 06 | importance_corn | 순열 중요도(EDD 1위) |
| 07 | pdp_ppt_corn | 강수 부분의존도 |
| 08 | actual_vs_pred_corn | 실제 vs 예측 |
| 12 | pdp_edd_corn | 극한고온 부분의존도 |
| 13 | edd_timeline | 연도별 EDD와 흉작 정렬 |
| 14 | edd_response_corn | EDD→수확량 단조감소 |
| 15 | heat_sensitivity | 옥수수 vs 대두 고온 민감도 |
| 16 | soy_trend | 대두 추세+충격 |
| 17 | transition_tradeoff | 전환비용 트레이드오프 곡선 |
| 18 | alloc_shift_by_state | 주별 권고 재배치 |
| 19 | models_compare_corn | OLS/Ridge/Lasso/RF/GBM RMSE 비교 |
| 20 | heat_response_models | 유해고온 반응: 선형 vs 트리 |
| 21 | meta_convergence | GA/SA vs MILP 수렴 |
| 22 | climate_model | 기후모델 A: warming hole + 시나리오 |
| W1–W4 | 날씨 EDA | 분포·분산분해·추세·자기상관 |
| 23 | weather_ml_r2 | 날씨 예측: ML vs climatology vs persistence |
| 24 | weather_edd_pred | EDD 실제 vs 예측(연차편차 미포착) |

## 데이터 출처
ACDC (Purdue PURR, CC-BY, DOI:10.4231/R72F7KK2), 1981–2015. 대상: Corn Belt 12개 주.
온도는 원본 GDD 히스토그램을 `tools/shrink_gdd.py`로 옥수수 기준 GDD/EDD로 압축해 사용.
