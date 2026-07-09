"""ACDC 분석 전체 파이프라인 (v3).

Phase 0-1  EDA + 온도 EDA
Phase 2    수확량 예측: 다중모델 비교(models_compare) + 해석(train)
Phase 3    기후 예측 모델 A (climate_model)
Phase 4-5  최적화: 연속 LP(전환비용, optimizer) + 단작 조합최적화 GA/SA/MILP(optimize_meta)
Phase 7    기후 시나리오 (scenario)
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import eda, eda_temp, models_compare, train, climate_model, scenario, optimizer, optimize_meta

if __name__ == "__main__":
    eda.run(); print("\n")
    eda_temp.run(); print("\n")
    models_compare.run("corn"); print("\n")
    for crop in ("corn", "soybean"):
        train.print_report(train.train_crop(crop)); print()
    climate_model.run(); print("\n")
    scenario.run(); print("\n")
    optimizer.run(); print("\n")
    optimize_meta.run()
    print("\n완료. 그림 → acdc/figures/, 수치 → acdc/outputs/, 리포트 → acdc/REPORT.md")
