"""
shrink_gdd.py — 큰 GDD 파일을 업로드 가능한 작은 파일로 줄이기 (로컬에서 실행)

ACDC 의 gddAprOct.csv 는 온도축을 1°C 로 쪼갠 114개 컬럼이라 파일이 크다.
우리 모델이 실제로 쓰는 건 옥수수 기준 두 값뿐:
  - gdd  (유익한 열)  = 10~29°C 버킷 합
  - edd  (해로운 고온) = 30°C 이상 버킷 합
그 둘만 미리 계산해 stco, year, gdd, edd 4컬럼으로 저장한다. 크기가 수십분의 1.

사용법:
  python3 shrink_gdd.py gddAprOct.csv gdd_slim.csv
그 다음 gdd_slim.csv 를 업로드(또는 repo 의 acdc/data/ 에 넣기)하면 끝.
prepare.py 가 이 slim 파일을 자동 인식한다.
"""
import sys, pandas as pd

def main(src, dst):
    g = pd.read_csv(src)
    gdd_cols = [f"gddp{t}" for t in range(10, 30) if f"gddp{t}" in g.columns]
    edd_cols = [f"gddp{t}" for t in range(30, 54) if f"gddp{t}" in g.columns]
    out = g[["stco", "year"]].copy()
    out["gdd"] = g[gdd_cols].sum(axis=1)
    out["edd"] = g[edd_cols].sum(axis=1)
    out.to_csv(dst, index=False)
    print(f"{src} -> {dst}: {len(out):,} rows, 4 cols")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python3 shrink_gdd.py <gddAprOct.csv> <gdd_slim.csv>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
