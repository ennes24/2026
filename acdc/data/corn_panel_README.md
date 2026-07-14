# corn_panel_cornbelt_1981_2015.csv — 분석용 병합 패널 (데이터 사전)

원본 6개 파일을 카운티(`stco`)·연도(`year`)로 **하나로 병합**한 깔끔한 표.
`notebooks/corn_yield_model_standalone.ipynb` 가 쓰는 데이터가 바로 이것이며, 그 노트북에는
이 파일이 **압축 내장**되어 있어 별도 다운로드가 필요 없다.

- **범위**: Corn Belt 12개 주 (IA IL NE MN IN KS OH SD MO ND WI TX)
- **기간**: 1981–2015
- **행/열**: 34,627 행 × 16 열 (카운티 1,113개)

| 컬럼 | 뜻 | 단위 | 출처 |
|---|---|---|---|
| `stco` | 카운티 FIPS (주2+카운티3) | 코드 | — |
| `state` | 주 FIPS (`stco // 1000`) | 코드 | — |
| `year` | 연도 | 1981–2015 | — |
| `corn` | 옥수수 수확량 (**타깃**) | bu/ac | NASS yielddata |
| `gdd` | 유익열 도일 (10–29℃) | ℃·일 | ACDC gddMarAug (압축) |
| `edd` | 극한고온 도일 (30℃↑) | ℃·일 | ACDC gddMarAug (압축) |
| `ppt` | 생육기 총강수 | mm | ACDC pptMarAug |
| `whc` | 토양 보수력 | — | gSSURGO soil2011 |
| `om` | 토양 유기물 | — | gSSURGO soil2011 |
| `spH` | 토양 산도 | pH | gSSURGO soil2011 |
| `clay` | 점토 함량 | — | gSSURGO soil2011 |
| `slope` | 경사 | — | gSSURGO soil2011 |
| `dsci_jul` | **7월 가뭄지수 DSCI** (2000년~; 이전은 결측) | 0–500 | USDM |
| `soil_jul` | **7월 토양수분** | — | TerraClimate |
| `pr_jul` | **7월 강수** | mm | TerraClimate |
| `tmmx_jul` | **7월 최고기온** | (스케일값) | TerraClimate |

**결측 안내**: `dsci_jul` 는 USDM이 2000년부터라 1981–1999가 NaN(19,629행). 트리 모델
(HistGradientBoosting)이 결측을 자체 처리하므로 35년을 다 살린다.

**재생성**: `python3 notebooks/_build_standalone_notebook.py` 가 원본에서 이 패널을 다시 만들고
노트북에 내장까지 한다.
