"""One-off helper (not part of the package) that assembles the three
notebooks in notebooks/ from cell definitions and executes them so their
outputs are baked in. Run from the repo root with the project venv active:

    python scripts/build_notebooks.py
"""
import nbformat as nbf
from nbclient import NotebookClient
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB_DIR = ROOT / "notebooks"


def make_nb(cells):
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    return nb


def md(text):
    return nbf.v4.new_markdown_cell(text)


def code(text):
    return nbf.v4.new_code_cell(text)


# ---------------------------------------------------------------------------
# 01_eda.ipynb
# ---------------------------------------------------------------------------
nb1 = make_nb([
    md("# 01. EDA — 기후 ↔ 작물 수확량 탐색적 분석\n\n"
       "합성(USDA/NOAA/Drought Monitor 스키마 호환) 패널 데이터를 불러와 기후 변수와 수확량의 관계를 살펴본다. "
       "데이터 생성 로직은 `src/generate_synthetic_data.py`, 병합/피처 엔지니어링은 `src/data_loader.py`에 있다."),
    code("import sys, pathlib\n"
         "_root = pathlib.Path.cwd()\n"
         "_root = _root.parent if _root.name == 'notebooks' else _root\n"
         "sys.path.insert(0, str(_root))\n"
         "import pandas as pd\n"
         "from src.data_loader import load_or_build_processed\n"
         "from src import visualize as viz\n"
         "\n"
         "panel, constraints = load_or_build_processed()\n"
         "panel.head()"),
    md("## 기본 통계"),
    code("panel.groupby('crop')['yield_bu_acre'].describe()"),
    md("## 연도별 평균 수확량 추세\n\n기술 발전(품종 개량 등)에 따른 완만한 상승 추세와 가뭄 연도(2002, 2006, 2012, 2017, 2022)의 하락이 함께 나타난다."),
    code("fig = viz.plot_yield_trend(panel)\n"
         "fig"),
    md("## 기후 변수 vs 수확량\n\n각 작물은 서로 다른 최적 온도·강수·가뭄 민감도를 가지도록 시뮬레이션되어 있다 (`CROP_PARAMS` 참고)."),
    code("fig = viz.plot_climate_yield_relationship(panel, 'corn')\n"
         "fig"),
    code("fig = viz.plot_climate_yield_relationship(panel, 'soybean')\n"
         "fig"),
    code("fig = viz.plot_climate_yield_relationship(panel, 'wheat')\n"
         "fig"),
    md("## 상관관계"),
    code("from src.data_loader import feature_columns\n"
         "cols = feature_columns() + ['yield_bu_acre']\n"
         "panel[panel['crop']=='corn'][cols].corr()['yield_bu_acre'].sort_values()"),
    md("## 주(State)별 제약조건 (토지·물)\n\n2단계 최적화에서 사용할 주별 가용 농경지(acre)와 관개용수 예산(acre-inch)이다."),
    code("constraints.sort_values('available_land_acres', ascending=False)"),
])

# ---------------------------------------------------------------------------
# 02_yield_prediction.ipynb
# ---------------------------------------------------------------------------
nb2 = make_nb([
    md("# 02. 작물 수확량 예측 (Stage 1: ML)\n\n"
       "Random Forest, XGBoost, LightGBM, CatBoost를 작물별로 비교·튜닝한다 (`src/model.py`). "
       "평가는 연도 기준 분할(2018년 이전 학습 / 2019년 이후 테스트)로 수행해 실제 예보 상황을 흉내낸다."),
    code("import sys, pathlib\n"
         "_root = pathlib.Path.cwd()\n"
         "_root = _root.parent if _root.name == 'notebooks' else _root\n"
         "sys.path.insert(0, str(_root))\n"
         "import pandas as pd\n"
         "from src.data_loader import load_or_build_processed\n"
         "from src.model import train_all_crops\n"
         "from src import visualize as viz\n"
         "\n"
         "panel, constraints = load_or_build_processed()\n"
         "results_by_crop, comparison = train_all_crops(panel)\n"
         "comparison.sort_values(['crop', 'rmse'])"),
    md("## 모델별 성능 비교 (RMSE)"),
    code("fig = viz.plot_model_comparison(comparison)\n"
         "fig"),
    md("## 최적 모델 — 실제값 vs 예측값"),
    code("for crop, info in results_by_crop.items():\n"
         "    best_name = info['best']\n"
         "    print(f\"{crop}: best model = {best_name}\")"),
    code("from src.data_loader import feature_columns\n"
         "from src.model import _time_split\n"
         "\n"
         "crop = 'corn'\n"
         "best_name = results_by_crop[crop]['best']\n"
         "best_model = results_by_crop[crop]['results'][best_name].estimator\n"
         "cols = feature_columns()\n"
         "data = panel[panel['crop'] == crop].dropna(subset=cols + ['yield_bu_acre'])\n"
         "_, test = _time_split(data)\n"
         "y_pred = best_model.predict(test[cols])\n"
         "fig = viz.plot_actual_vs_predicted(test['yield_bu_acre'].values, y_pred, crop, best_name)\n"
         "fig"),
    md("## 피처 중요도"),
    code("for crop, info in results_by_crop.items():\n"
         "    best_name = info['best']\n"
         "    fi = info['results'][best_name].feature_importance\n"
         "    viz.plot_feature_importance(fi, crop, best_name)\n"
         "print('saved feature importance plots for all crops')"),
    md("## 학습된 모델 저장\n\n`train_all_crops`가 이미 각 작물의 최적 모델을 `outputs/models/*.joblib`로 저장했다. "
       "다음 노트북(03_optimization)에서 이 모델들을 불러와 기후 시나리오별 수확량을 예측하는 데 사용한다."),
    code("import pathlib\n"
         "sorted(pathlib.Path('../outputs/models').glob('*.joblib')) if pathlib.Path('../outputs/models').exists() else sorted(pathlib.Path('outputs/models').glob('*.joblib'))"),
])

# ---------------------------------------------------------------------------
# 03_optimization.ipynb
# ---------------------------------------------------------------------------
nb3 = make_nb([
    md("# 03. 작물 배치 최적화 + 기후 시나리오 연결 (Stage 2)\n\n"
       "1단계에서 학습한 모델로 기후 시나리오별(`baseline` vs `drought_heat`) 수확량을 예측하고, "
       "토지·물 제약 하에서 전체 생산량을 최대화하는 작물 배치를 LP로 구한다 (`src/optimizer.py`, `src/scenarios.py`)."),
    code("import sys, pathlib\n"
         "_root = pathlib.Path.cwd()\n"
         "_root = _root.parent if _root.name == 'notebooks' else _root\n"
         "sys.path.insert(0, str(_root))\n"
         "import pandas as pd\n"
         "from src.data_loader import load_or_build_processed\n"
         "from src.model import load_best_models\n"
         "from src.optimizer import optimize_allocation\n"
         "from src import visualize as viz\n"
         "\n"
         "panel, constraints = load_or_build_processed()\n"
         "models = load_best_models()"),
    md("## 왜 제약이 필요한가: 목적함수만 '총생산 최대화'일 때\n\n"
       "물·최소 생산량 제약 없이 풀면 가장 수확량 높은 작물(옥수수) 한 가지로 전부 쏠리는 시시한 해가 나온다."),
    code("from src.scenarios import build_scenarios, predict_scenario_yields\n"
         "from src.generate_synthetic_data import CROP_PARAMS\n"
         "\n"
         "scenario_climate = build_scenarios(panel)\n"
         "baseline_yields = predict_scenario_yields(scenario_climate['baseline'], models)\n"
         "water_use = {c: p['water_use_acre_in'] for c, p in CROP_PARAMS.items()}\n"
         "\n"
         "degenerate = optimize_allocation(baseline_yields, constraints, water_use=water_use)\n"
         "degenerate.allocation.groupby('crop')['acres'].sum()"),
    md("결과를 보면 옥수수에 모든 면적이 쏠린다 — 제약이 더 필요하다는 뜻이다. "
       "`src/scenarios.py`는 **국가 단위 관개용수 예산의 일정 비율을 각 작물에 최소/최대로 배정**하는 정책 제약을 추가해 의미 있는 트레이드오프를 만든다."),
    md("## 기후 시나리오별 최적화 실행"),
    code("from src.scenarios import run_scenario_analysis\n"
         "\n"
         "out = run_scenario_analysis(panel, constraints, models)\n"
         "out['summary']"),
    code("print(f\"Production saved by reallocation under drought/heat: \"\n"
         "      f\"{out['production_saved_bu']:,.0f} bu ({out['production_saved_pct']:.2f}%)\")"),
    md("## 시각화: 시나리오별 총생산"),
    code("fig = viz.plot_scenario_comparison(out['summary'])\n"
         "fig"),
    md("## 시각화: 기준 vs 가뭄-적응 배치 (주 x 작물)"),
    code("fig = viz.plot_allocation_heatmap(out['baseline_result'].allocation, 'Baseline optimal allocation (acres)', 'allocation_baseline.png')\n"
         "fig"),
    code("fig = viz.plot_allocation_heatmap(out['adapted_result'].allocation, 'Drought/heat optimal allocation (acres)', 'allocation_drought_adapted.png')\n"
         "fig"),
    md("## 가뭄 시 주별 재배치 패턴\n\n작물별 국가 총 면적은 정책 제약(최소/최대 비중)에 의해 거의 동일하게 유지되지만, "
       "**어느 주에서 무엇을 심을지**는 기후 충격에 따라 달라진다 — 이것이 '적응(adaptation)'의 본질이다."),
    code("base = out['baseline_result'].allocation\n"
         "adapt = out['adapted_result'].allocation\n"
         "merged = base.merge(adapt, on=['state', 'crop'], suffixes=('_baseline', '_drought_adapted'))\n"
         "merged['acre_shift'] = merged['acres_drought_adapted'] - merged['acres_baseline']\n"
         "merged.loc[merged['acre_shift'].abs() > 1000, ['state', 'crop', 'acres_baseline', 'acres_drought_adapted', 'acre_shift']]\\\n"
         "    .sort_values('acre_shift')"),
    md("## 결론\n\n"
       "- 가뭄/고온 시나리오에서는 기준 대비 총생산이 크게 감소한다 (수확량 자체가 떨어지기 때문에 불가피).\n"
       "- 같은 작물 구성(정책상 최소/최대 비중)을 유지한 채로도, **어느 주가 어떤 작물을 맡을지 재배치하는 것만으로** 적응하지 않았을 때보다 생산을 추가로 지켜낼 수 있다.\n"
       "- 다만 그 효과는 제한적이다 — 이는 순수한 공간 재배치만으로는 기후 피해의 일부만 상쇄할 수 있고, "
       "관개 인프라 투자나 내건성 품종 개발 같은 다른 적응 전략이 함께 필요함을 시사한다."),
])

for name, nb in [
    ("01_eda.ipynb", nb1),
    ("02_yield_prediction.ipynb", nb2),
    ("03_optimization.ipynb", nb3),
]:
    path = NB_DIR / name
    client = NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}})
    client.execute()
    with open(path, "w") as f:
        nbf.write(nb, f)
    print(f"wrote + executed {path}")
