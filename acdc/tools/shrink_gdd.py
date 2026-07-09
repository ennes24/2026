"""
shrink_gdd.py — 큰 GDD 파일을 업로드 가능한 작은 파일로 줄이기 (로컬에서 실행)

ACDC 의 gddAprOct.csv 는 온도축을 1°C 로 쪼갠 114개 컬럼이라 파일이 크다
(수백 MB). 우리 모델이 실제로 쓰는 건 옥수수 기준 두 값뿐:
  - gdd  (유익한 열)  = 10~29°C 버킷 합
  - edd  (해로운 고온) = 30°C 이상 버킷 합
그 둘만 미리 계산해 stco, year, gdd, edd 4컬럼으로 저장한다 → 크기가 수십분의 1.
결과는 보통 2~3MB(압축 시 수백 KB)라 git·Drive 어디든 올라간다.

메모리 안전: 파일이 아무리 커도 청크로 나눠 읽으므로 저사양 PC 에서도 돈다.

사용법:
  python3 shrink_gdd.py gddAprOct.csv gdd_slim.csv
그 다음 gdd_slim.csv 를 업로드(또는 repo 의 acdc/data/ 에 넣기)하면 끝.
prepare.py 가 gdd_slim.csv 를 자동 인식한다.

pandas 가 없으면:  pip install pandas
"""
import sys
import pandas as pd

CHUNK = 20000  # 한 번에 읽을 행 수 (메모리 절약)


def main(src, dst):
    gdd_cols = [f"gddp{t}" for t in range(10, 30)]   # 10~29°C
    edd_cols = [f"gddp{t}" for t in range(30, 54)]   # 30°C 이상
    first = True
    total = 0
    for chunk in pd.read_csv(src, chunksize=CHUNK):
        gc = [c for c in gdd_cols if c in chunk.columns]
        ec = [c for c in edd_cols if c in chunk.columns]
        out = chunk[["stco", "year"]].copy()
        out["gdd"] = chunk[gc].sum(axis=1).round(1)
        out["edd"] = chunk[ec].sum(axis=1).round(1)
        out.to_csv(dst, mode="w" if first else "a", header=first, index=False)
        first = False
        total += len(out)
    print(f"OK  {src} -> {dst}:  {total:,} rows, 4 columns")
    print("이제 이 파일만 업로드하면 됩니다 (raw 원본은 올릴 필요 없음).")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python3 shrink_gdd.py <gddAprOct.csv> <gdd_slim.csv>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
