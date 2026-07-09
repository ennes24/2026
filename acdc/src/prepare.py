"""
prepare.py — ACDC 데이터 병합 + 피처 구성 + 추세/기상충격 분해

이 파일이 하는 일 (한 문장): 흩어져 있는 4개 원본 파일(수확량·강수·토양)을
하나의 "카운티×연도" 표로 합치고, 모델이 쓸 피처를 만들고, 수확량을
'장기 기술추세'와 '그해 기상충격' 두 성분으로 분해한다.

왜 분해까지 하나?
  옥수수 수확량은 매년 품종·비료·농법 발전으로 꾸준히 오른다(기술추세).
  그 위에 그해 날씨가 좋으면 +, 가물면 - 로 출렁이는 게 '기상충격'이다.
  기후(온난화·가뭄) 이야기는 이 '기상충격' 성분에 담겨 있으므로,
  둘을 분리해두면 EDA·모델·시나리오 어디서든 재사용할 수 있다.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

# 옥수수·대두 주산지 12개 주 (repo README 기준). stco = state*1000 + county 이므로
# state FIPS 로 필터링한다. 비농업 카운티를 넣으면 결측·잡음만 늘어 모델이 흐려진다.
CORN_BELT_FIPS = {19: "IA", 17: "IL", 31: "NE", 27: "MN", 18: "IN", 20: "KS",
                  39: "OH", 46: "SD", 29: "MO", 38: "ND", 55: "WI", 48: "TX"}

# 모델에 실제로 넣을 토양 피처. sand/silt/clay 는 서로 합이 100이라 다 넣으면
# 다중공선성만 커진다 → 대표값 whc(보수력)·om(유기물)·spH(산도)·clay 정도만.
SOIL_FEATURES = ["whc", "om", "spH", "clay", "slope"]


def load_raw() -> dict[str, pd.DataFrame]:
    y = pd.read_csv(os.path.join(DATA, "yielddata.csv"))
    p = pd.read_csv(os.path.join(DATA, "pptMarAug.csv"))
    s = pd.read_csv(os.path.join(DATA, "soil2011.csv"))
    return {"yield": y, "ppt": p, "soil": s}


def has_temperature() -> str | None:
    """온도(GDD) 파일이 data/ 에 있으면 경로를 반환. 없으면 None.

    지금 세션에서는 egress 정책 때문에 ACDC 원본(GDD)을 못 받았다.
    나중에 gddAprOct.csv 를 data/ 에 넣으면 온도 피처가 자동으로 켜지도록
    이 훅을 남겨둔다.
    """
    # slim(이미 gdd/edd 계산된) 파일을 우선 인식, 없으면 원본 GDD 히스토그램.
    for name in ("gdd_slim.csv", "gddAprOct.csv", "gddMarAug.csv"):
        path = os.path.join(DATA, name)
        if os.path.exists(path):
            return path
    return None


def build_temperature_features(path: str) -> pd.DataFrame:
    """GDD 히스토그램(1°C 버킷)을 옥수수 기준 GDD/EDD 두 피처로 압축.

    - GDD (유익한 열): 10~29°C 구간 도일 합
    - EDD (해로운 고온): 30°C 이상 구간 도일 합
    GDD 는 가산적이라 해당 버킷들을 그냥 더하면 된다.
    """
    g = pd.read_csv(path)
    # 이미 집계된 slim 파일이면(gdd/edd 컬럼 존재) 그대로 사용.
    if {"gdd", "edd"}.issubset(g.columns):
        return g[["stco", "year", "gdd", "edd"]].copy()
    def bucket(t):  # +t°C 버킷 컬럼명
        return f"gddp{t}"
    gdd_cols = [bucket(t) for t in range(10, 30) if bucket(t) in g.columns]
    edd_cols = [bucket(t) for t in range(30, 54) if bucket(t) in g.columns]
    out = g[["stco", "year"]].copy()
    out["gdd"] = g[gdd_cols].sum(axis=1)
    out["edd"] = g[edd_cols].sum(axis=1)
    return out


def add_county_trend(df: pd.DataFrame, crop: str) -> pd.DataFrame:
    """카운티별 수확량 선형 추세를 적합해 3개 파생컬럼을 붙인다.

      {crop}_trend    : 그 카운티의 연도별 기대 수확량(기술추세 성분)
      {crop}_anom     : 실제 - 추세 = '그해 기상충격' (음수면 흉작)
      {crop}_anom_pct : 추세 대비 % 편차 (카운티 간 비교용, 규모 정규화)

    카운티마다 토양 등 재배환경이 달라 절대 수확량이 다르므로, 카운티별로
    각자의 추세선을 뽑아야 '그 카운티 기준에서 이번해가 얼마나 나빴나'를
    공정하게 볼 수 있다.
    """
    df = df.sort_values(["stco", "year"]).copy()
    trend = np.full(len(df), np.nan)
    for stco, idx in df.groupby("stco").groups.items():
        sub = df.loc[idx, ["year", crop]].dropna()
        if len(sub) >= 5:  # 추세를 뽑으려면 최소 5개년
            b1, b0 = np.polyfit(sub.year, sub[crop], 1)
            trend[df.index.get_indexer(idx)] = b0 + b1 * df.loc[idx, "year"]
    df[f"{crop}_trend"] = trend
    df[f"{crop}_anom"] = df[crop] - df[f"{crop}_trend"]
    df[f"{crop}_anom_pct"] = 100 * df[f"{crop}_anom"] / df[f"{crop}_trend"]
    return df


def build_panel(crop: str = "corn", corn_belt_only: bool = True) -> pd.DataFrame:
    """모델·EDA 가 바로 쓰는 최종 패널을 만든다."""
    raw = load_raw()
    df = (raw["yield"]
          .merge(raw["ppt"], on=["stco", "year"], how="left")
          .merge(raw["soil"], on="stco", how="left"))
    df["state"] = df["stco"] // 1000
    df["state_abbr"] = df["state"].map(CORN_BELT_FIPS)

    tpath = has_temperature()
    if tpath:
        df = df.merge(build_temperature_features(tpath), on=["stco", "year"], how="left")

    if corn_belt_only:
        df = df[df["state"].isin(CORN_BELT_FIPS)].copy()

    # 타깃 결측 행은 제외(대체 금지). 강수/토양 결측도 소수 있으면 제외.
    need = [crop, "ppt"] + SOIL_FEATURES
    df = df.dropna(subset=need).copy()

    df = add_county_trend(df, crop)
    return df


def feature_columns(df: pd.DataFrame) -> list[str]:
    """모델 입력 피처 목록. 온도 파일이 있으면 gdd/edd 도 자동 포함."""
    cols = ["ppt"] + SOIL_FEATURES + ["year", "state"]
    for extra in ("gdd", "edd"):
        if extra in df.columns:
            cols.append(extra)
    return cols


if __name__ == "__main__":
    for crop in ("corn", "soybean"):
        d = build_panel(crop)
        print(f"[{crop}] rows={len(d):,}  years={d.year.min()}-{d.year.max()}  "
              f"features={feature_columns(d)}  temp={'YES' if 'gdd' in d else 'NO'}")
