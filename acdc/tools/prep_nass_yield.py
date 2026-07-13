"""
prep_nass_yield.py — USDA NASS Quick Stats 카운티 옥수수 수확량 CSV를 우리 형식으로 가공

목적: ACDC yielddata.csv(1981–2015)에 이어붙일 2016–2025 옥수수 단수(bu/ac)를 만든다.
입력: Quick Stats 에서 받은 CSV (Program=SURVEY, Commodity=CORN, Category=YIELD,
      Data Item='CORN, GRAIN - YIELD, MEASURED IN BU / ACRE', Geographic Level=COUNTY).
      컬럼 예: Year, State ANSI, County ANSI, Value, Data Item ...

출력: acdc/data/yield_recent.csv  (stco, year, corn)  ← prepare.py 가 기존 수확량에 append

사용법:
  python3 prep_nass_yield.py qs_corn_yield.csv ../data/yield_recent.csv [--min-year 2016]
"""
import argparse
import re
import pandas as pd


def _num(s):
    if pd.isna(s):
        return float("nan")
    t = re.sub(r"[^0-9.]", "", str(s))
    return float(t) if t not in ("", ".") else float("nan")


def _find(cols, *cands):
    low = {c.lower().strip(): c for c in cols}
    for cand in cands:
        if cand in low:
            return low[cand]
    for cand in cands:
        for lc, orig in low.items():
            if cand in lc:
                return orig
    return None


def main(src, dst, min_year):
    df = pd.read_csv(src, dtype=str)
    yc = _find(df.columns, "year")
    sc = _find(df.columns, "state ansi", "state_ansi", "state fips", "state_fips_code")
    cc = _find(df.columns, "county ansi", "county_ansi", "county code", "county_code")
    vc = _find(df.columns, "value")
    di = _find(df.columns, "data item", "short_desc")
    if not all([yc, sc, cc, vc]):
        raise SystemExit(f"필요 컬럼 못 찾음. 실제: {list(df.columns)}")

    # grain 단수만 (silage·operations 제외), 카운티 단위만
    if di:
        d = df[df[di].str.upper().str.contains("YIELD") &
               df[di].str.upper().str.contains("GRAIN")].copy()
    else:
        d = df.copy()
    d = d[d[sc].notna() & d[cc].notna()].copy()
    d["stco"] = (d[sc].str.zfill(2) + d[cc].str.zfill(3))
    d = d[d["stco"].str.match(r"^\d{5}$")].copy()
    d["stco"] = d["stco"].astype(int)
    d["year"] = pd.to_numeric(d[yc], errors="coerce")
    d["corn"] = d[vc].map(_num)
    d = d.dropna(subset=["year", "corn"]).copy()
    d["year"] = d["year"].astype(int)
    d = d[d["year"] >= min_year]
    out = d.groupby(["stco", "year"], as_index=False)["corn"].mean().round(1)
    out.to_csv(dst, index=False)
    print(f"OK  {src} -> {dst}:  {len(out):,} county-years, {out.year.min()}-{out.year.max()}")
    print("prepare.py 가 이 파일을 기존 수확량(1981-2015)에 append 합니다.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--min-year", type=int, default=2016)
    a = ap.parse_args()
    main(a.src, a.dst, a.min_year)
