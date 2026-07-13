"""
bucket_gdd.py — 온도 121버킷을 '압축하지 않고' 살려서 slim 으로 저장 (로컬 실행)

기존 shrink_gdd.py 는 121개 온도버킷을 gdd·edd 2개로 압축했다. 이 스크립트는 반대로
**생육기 온도분포의 모양 자체**를 피처로 쓰려고, 의미 있는 온도구간 버킷을 개별 컬럼으로
남긴다(옥수수는 대략 0~50°C 구간에 값이 몰림). 트리 모델은 다중공선성에 강해 버킷을
그대로 넣어도 문제없다.

목적: "gdd·edd 2개로 압축 vs 버킷 전체" 중 무엇이 예측을 더 잘하는지 실측 비교.

출력: acdc/data/gdd_buckets.csv  (stco, year, gddp0, gddp1, ..., gddp50)
크기: 약 107k행 × ~50컬럼 ≈ 15~20MB (압축하면 수 MB). Drive/ git 업로드 가능.

사용법:
  python3 bucket_gdd.py gddMarAug.csv ../data/gdd_buckets.csv
"""
import sys
import pandas as pd

CHUNK = 20000
LO, HI = 0, 50   # 남길 +온도 버킷 범위 (gddp0 ~ gddp50)


def main(src, dst):
    want = [f"gddp{t}" for t in range(LO, HI + 1)]
    first, total, kept = True, 0, None
    for chunk in pd.read_csv(src, chunksize=CHUNK):
        cols = [c for c in want if c in chunk.columns]
        kept = cols
        out = chunk[["stco", "year"] + cols].copy()
        for c in cols:
            out[c] = out[c].round(1)
        out.to_csv(dst, mode="w" if first else "a", header=first, index=False)
        first = False
        total += len(out)
    print(f"OK  {src} -> {dst}:  {total:,} rows, {len(kept)} temperature buckets ({kept[0]}..{kept[-1]})")
    print("이 파일을 acdc/data/ 에 넣으면 prepare.py 가 버킷 피처로 자동 인식합니다.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python3 bucket_gdd.py <gddMarAug.csv> ../data/gdd_buckets.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
