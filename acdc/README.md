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
│   ├── train.py          # ML 학습·평가·해석·2012 스트레스 테스트
│   ├── scenario.py       # 예측1(생산성 지도) · 예측2(기후 시나리오)
│   └── optimizer.py      # 2단계: 전환비용 감안 배치 최적화 (PuLP)
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

## 데이터 출처
ACDC (Purdue PURR, CC-BY, DOI:10.4231/R72F7KK2), 1981–2015. 대상: Corn Belt 12개 주.
온도는 원본 GDD 히스토그램을 `tools/shrink_gdd.py`로 옥수수 기준 GDD/EDD로 압축해 사용.
