"""
prep_drought.py — US Drought Monitor 카운티 export를 7월 DSCI slim으로 가공 (로컬 실행)

입력: droughtmonitor.unl.edu 에서 받은 카운티 주간 CSV (Cumulative 형식).
      컬럼 예: MapDate, FIPS, County, State, None, D0, D1, D2, D3, D4, ValidStart, ValidEnd, ...
      D0~D4 = 누적 면적%(그 등급 '이상'). 매주 1행씩, 전 카운티.

출력: acdc/data/drought_slim.csv  (stco, year, dsci_jul[, dsci_jja, d2_jul])
      DSCI = D0+D1+D2+D3+D4 (0~500). 개화기 7월 평균을 카운티×연으로 집계.

왜 7월인가: 옥수수는 7월 개화·수분기 물 스트레스가 수확량을 결정한다. 계절 총강수엔
그 시기 정보가 희석돼 있어, 7월 DSCI가 그 공백을 메운다(실측: R² +0.05로 최대 개선).

사용법:
  python3 prep_drought.py <usdm_county_export.csv> ../data/drought_slim.csv
파일이 크면(수백 MB) 청크로 읽으므로 저사양에서도 동작.
"""
import sys
import pandas as pd

CHUNK = 200000


def main(src, dst):
    keep = ["FIPS", "D0", "D1", "D2", "D3", "D4", "ValidStart"]
    parts = []
    for ch in pd.read_csv(src, usecols=keep, chunksize=CHUNK, dtype={"FIPS": str}):
        dt = pd.to_datetime(ch["ValidStart"])
        ch = ch.assign(month=dt.dt.month, year=dt.dt.year)
        ch = ch[ch["month"].isin([6, 7, 8])]           # 생육기 핵심만 남겨 메모리 절약
        ch["dsci"] = ch[["D0", "D1", "D2", "D3", "D4"]].sum(axis=1)
        parts.append(ch[["FIPS", "year", "month", "dsci", "D2"]])
    d = pd.concat(parts, ignore_index=True)

    jul = (d[d.month == 7].groupby(["FIPS", "year"])
           .agg(dsci_jul=("dsci", "mean"), d2_jul=("D2", "mean")).reset_index())
    jja = (d.groupby(["FIPS", "year"]).agg(dsci_jja=("dsci", "mean")).reset_index())
    out = jul.merge(jja, on=["FIPS", "year"], how="outer")
    out["stco"] = pd.to_numeric(out["FIPS"], errors="coerce")
    out = out.dropna(subset=["stco"]).copy()
    out["stco"] = out["stco"].astype(int)
    out = out[["stco", "year", "dsci_jul", "dsci_jja", "d2_jul"]].round(1)
    out.to_csv(dst, index=False)
    print(f"OK  {src} -> {dst}:  {len(out):,} county-years, {out.year.min()}-{out.year.max()}")
    print("prepare.py 가 dsci_jul 을 피처로 자동 편입합니다(1981-1999는 NaN, 트리가 처리).")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python3 prep_drought.py <usdm_county_export.csv> ../data/drought_slim.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
