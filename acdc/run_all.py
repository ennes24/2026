"""ACDC 분석 전체 파이프라인: EDA → 온도EDA → 모델 → 예측1/2 → 2단계 최적화."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import eda, eda_temp, train, scenario, optimizer

if __name__ == "__main__":
    eda.run()
    print("\n")
    eda_temp.run()
    print("\n")
    for crop in ("corn", "soybean"):
        train.print_report(train.train_crop(crop)); print()
    scenario.run()
    print("\n")
    optimizer.run()
    print("\n완료. 그림 → acdc/figures/, 수치 → acdc/outputs/, 리포트 → acdc/REPORT.md")
