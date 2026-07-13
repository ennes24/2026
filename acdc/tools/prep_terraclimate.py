"""
prep_terraclimate.py — TerraClimate 7월 카운티 export를 우리 파넬용 slim으로 가공 (로컬 실행)

입력: GEE(gee_terraclimate.js) 또는 Climate Engine 에서 받은 카운티 CSV.
      컬럼에 (FIPS 또는 GEOID), year, 토양수분(soil), VPD(vpd)가 있으면 됨.
      컬럼명이 조금 달라도(대소문자·별칭) 자동으로 찾아 맞춘다.

출력: acdc/data/terraclimate_slim.csv  (stco, year, soil_jul, vpd_jul)

사용법:
  python3 prep_terraclimate.py terraclimate_july_county.csv ../data/terraclimate_slim.csv
"""
import sys
import pandas as pd


def _find(cols, *cands):
    low = {c.lower(): c for c in cols}
    for cand in cands:
        if cand in low:
            return low[cand]
    # 부분일치
    for cand in cands:
        for lc, orig in low.items():
            if cand in lc:
                return orig
    return None


def main(src, dst):
    df = pd.read_csv(src)
    fips_c = _find(df.columns, "geoid", "fips", "stco")
    year_c = _find(df.columns, "year")
    cols = {"soil_jul": _find(df.columns, "soil", "soilmoisture", "sm"),
            "vpd_jul":  _find(df.columns, "vpd"),
            "pr_jul":   _find(df.columns, "pr", "precip", "ppt"),
            "tmmx_jul": _find(df.columns, "tmmx", "tmax", "tmmax")}
    if not (fips_c and year_c):
        raise SystemExit(f"FIPS/year 컬럼을 못 찾음. 실제 컬럼: {list(df.columns)}")

    out = pd.DataFrame()
    out["stco"] = pd.to_numeric(df[fips_c], errors="coerce")
    out["year"] = pd.to_numeric(df[year_c], errors="coerce")
    for name, src_col in cols.items():
        if src_col:
            out[name] = pd.to_numeric(df[src_col], errors="coerce")
    out = out.dropna(subset=["stco", "year"]).copy()
    out["stco"] = out["stco"].astype(int)
    out["year"] = out["year"].astype(int)
    keep = ["stco", "year"] + [c for c in ("soil_jul", "vpd_jul", "pr_jul", "tmmx_jul") if c in out.columns]
    out = out[keep].round(3)
    out.to_csv(dst, index=False)
    print(f"OK  {src} -> {dst}:  {len(out):,} county-years, cols={keep}")
    print("prepare.py 에 soil_jul/vpd_jul 훅을 추가하면 피처로 편입됩니다(파일 확인 후 연결).")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python3 prep_terraclimate.py <terraclimate_county.csv> ../data/terraclimate_slim.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
