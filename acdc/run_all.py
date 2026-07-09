"""ACDC 분석 전체 파이프라인 실행: EDA → 모델 → 두 갈래 예측."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import eda, train, scenario

if __name__ == "__main__":
    eda.run()
    print("\n")
    for crop in ("corn", "soybean"):
        train.print_report(train.train_crop(crop)); print()
    scenario.run()
    print("\n완료. 그림 → acdc/figures/, 수치 → acdc/outputs/")
