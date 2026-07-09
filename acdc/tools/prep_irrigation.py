"""
prep_irrigation.py — USDA NASS 또는 USGS 관개 데이터를 우리 파넬에 붙는 형태로 가공 (로컬 실행)

우리 데이터는 카운티 단위(stco = 5자리 FIPS = 주 2자리 + 카운티 3자리)다.
관개 원본을 받아 stco 키 + 관개비율 한 컬럼짜리 slim 파일(irrigation_slim.csv)로 만든다.
그러면 prepare.py 가 이 파일을 자동 인식해 피처로 편입한다(아래 지원 코드 추가 예정).

지원 형식 (둘 중 받은 것으로):
  --source nass  : USDA NASS Quick Stats CSV
                   (필요 컬럼 예: state_fips_code, county_code, Value, short_desc)
                   'CORN, IRRIGATED - ACRES HARVESTED' / 'CORN - ACRES HARVESTED' 두 줄로 비율 계산
  --source usgs  : USGS Water Use county CSV
                   (필요 컬럼 예: STATEFIPS, COUNTYFIPS, 'IR-...' 관개 면적/취수 컬럼)

사용법 예:
  python3 prep_irrigation.py --source nass --infile qs.corn.csv     --out ../data/irrigation_slim.csv
  python3 prep_irrigation.py --source usgs --infile usco2015.csv    --out ../data/irrigation_slim.csv

주의: NASS 값에는 콤마(1,234)와 '(D)'(비공개) 표기가 있으니 숫자만 남긴다.
"""
import argparse
import re
import pandas as pd


def _num(s):
    """'1,234' -> 1234.0, '(D)'/'(Z)'/'' -> NaN"""
    if pd.isna(s):
        return float("nan")
    t = re.sub(r"[^0-9.]", "", str(s))
    return float(t) if t not in ("", ".") else float("nan")


def from_nass(infile):
    df = pd.read_csv(infile, dtype=str)
    # 컬럼명이 대소문자/공백 섞여올 수 있어 표준화
    df.columns = [c.strip().lower() for c in df.columns]
    # FIPS 조합 (county 컬럼명이 버전마다 county_code / county_ansi 로 다름)
    county_col = "county_code" if "county_code" in df.columns else "county_ansi"
    val_col = "value" if "value" in df.columns else ("val" if "val" in df.columns else df.columns[-1])
    df = df[df["state_fips_code"].notna() & df[county_col].notna()].copy()
    st = df["state_fips_code"].str.zfill(2)
    co = df[county_col].str.zfill(3)
    df["stco"] = (st + co).astype(int)
    df["val"] = df[val_col].map(_num)
    desc = df["short_desc"].str.upper()

    irr = df[desc.str.contains("IRRIGATED") & desc.str.contains("ACRES HARVESTED")]
    tot = df[~desc.str.contains("IRRIGATED") & desc.str.contains("ACRES HARVESTED")]
    irr = irr.groupby("stco")["val"].sum()
    tot = tot.groupby("stco")["val"].sum()
    out = pd.DataFrame({"irr_acres": irr, "tot_acres": tot}).dropna()
    out["irrig_share"] = (out.irr_acres / out.tot_acres).clip(0, 1)
    return out.reset_index()[["stco", "irrig_share"]]


def from_usgs(infile):
    df = pd.read_csv(infile, dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    df["stco"] = (df["STATEFIPS"].str.zfill(2) + df["COUNTYFIPS"].str.zfill(3)).astype(int)
    # 관개 면적 컬럼 후보 (IR-... = irrigation). 데이터셋 버전마다 이름이 달라 자동 탐색.
    cand = [c for c in df.columns if c.startswith("IR-") and ("ACRES" in c or "IRTOT" in c or "WFR" in c)]
    if not cand:
        raise SystemExit(f"USGS 관개 컬럼을 못 찾음. 컬럼들: {list(df.columns)[:30]}")
    col = cand[0]
    print(f"[usgs] 관개 컬럼 사용: {col}")
    df["irr"] = df[col].map(_num)
    out = df.groupby("stco")["irr"].sum().reset_index()
    # 취수/면적 절대값이므로 '비율'이 아니라 그대로 넘기되 컬럼명 명시
    out = out.rename(columns={"irr": "irrig_value_usgs"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["nass", "usgs"], required=True)
    ap.add_argument("--infile", required=True)
    ap.add_argument("--out", default="../data/irrigation_slim.csv")
    a = ap.parse_args()
    out = from_nass(a.infile) if a.source == "nass" else from_usgs(a.infile)
    out.to_csv(a.out, index=False)
    print(f"OK  {a.infile} -> {a.out}:  {len(out):,} counties, cols={list(out.columns)}")
    print("이 파일을 acdc/data/ 에 두면 됩니다. (다음 단계: prepare.py 에서 자동 조인)")


if __name__ == "__main__":
    main()
