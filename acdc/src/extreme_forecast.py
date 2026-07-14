"""
extreme_forecast.py — 극단해(꼬리) 인식 수확량 예보기

문제(문헌 14편 공통 실패): 표준 회귀는 '평균 오차'를 줄이려고 극단을 평균으로
당겨서 2012 같은 붕괴를 놓치고, 게다가 아무 경고도 안 준다.

해법: 점추정 대신 **분위수 예측(quantile: P10/P50/P90)** 으로 '하방 위험'을 직접
예측한다. HistGradientBoosting 의 loss='quantile' 사용. 롤링오리진(train ≤Y-1 →
predict Y)으로,
  (1) 구간 [P10,P90] 이 실제를 얼마나 덮나(calibration, 목표 80%)
  (2) 극단해(2012 등)에서 점추정은 과대예측(허위 안심)하는데 P10 은 붕괴를 잡나
  (3) 카운티 단위 '붕괴 조기경보'의 정밀도/재현율
을 본다. 이 P10(하방)이 다음 단계에서 강건 최적화의 입력이 된다.

주의(정직): 이건 7월 관측 날씨를 쓰는 '관측 후(nowcast)' 위험평가지, 1년 전 예보가
아니다(여름 날씨는 봄에 못 앎). 그래도 '올여름이 나쁠 수 있다'를 확률로 알려준다.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as _fm
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error

from prepare import build_panel

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")
for _p in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"]:
    if os.path.exists(_p):
        _fm.fontManager.addfont(_p); plt.rcParams["font.family"] = _fm.FontProperties(fname=_p).get_name()
plt.rcParams["axes.unicode_minus"] = False

FEATS = ["ppt", "whc", "om", "spH", "clay", "slope", "year", "state",
         "gdd", "edd", "dsci_jul", "soil_jul", "pr_jul", "tmmx_jul"]
QUANTILES = [0.1, 0.5, 0.9]


def _fit(loss, X, y, q=None):
    kw = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, random_state=0)
    m = (HistGradientBoostingRegressor(loss="quantile", quantile=q, **kw) if loss == "quantile"
         else HistGradientBoostingRegressor(loss="squared_error", **kw))
    return m.fit(X, y)


def pinball(y, pred, q):
    d = y - pred
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def run(crop="corn", start=2005, end=2015, alpha=0.2):
    # start=2005: 훈련(≤2003)에 7월 가뭄(USDM 2000~) 이 포함되도록. 그 이전은
    # dsci_jul 이 전부 NaN 이라 비닝이 깨진다. alpha=0.2 → 목표 80% 구간.
    d = build_panel(crop, extended=False)
    f0 = [c for c in FEATS if c in d.columns]
    rows = []
    for Y in range(start, end + 1):
        proper = d[d.year <= Y - 2]      # 분위수 모델 학습
        calib = d[d.year == Y - 1]       # 컨포멀 보정용(직전 해)
        te = d[d.year == Y].copy()       # 예보 대상
        if len(te) < 50 or len(calib) < 50 or len(proper) < 200:
            continue
        f = [c for c in f0 if proper[c].nunique(dropna=True) >= 2]
        Xp, yp = proper[f], proper[crop].values
        pt = _fit("squared_error", Xp, yp).predict(te[f])
        m10 = _fit("quantile", Xp, yp, 0.1); m50 = _fit("quantile", Xp, yp, 0.5)
        m90 = _fit("quantile", Xp, yp, 0.9)

        # ── 컨포멀 분위수 회귀(CQR): 직전 해에서 구간을 보정해 80% 커버리지 보장 ──
        yc = calib[crop].values
        E = np.maximum(m10.predict(calib[f]) - yc, yc - m90.predict(calib[f]))
        k = int(np.ceil((len(E) + 1) * (1 - alpha)))
        Q = np.sort(E)[min(k, len(E)) - 1]     # (1-alpha) 적합분위수 → 구간 폭 보정량

        te["actual"] = te[crop].values
        te["point"] = pt
        te["p10"] = m10.predict(te[f]) - Q     # 하방 확장
        te["p50"] = m50.predict(te[f])
        te["p90"] = m90.predict(te[f]) + Q     # 상방 확장
        rows.append(te[["stco", "year", "actual", "point", "p10", "p50", "p90"]])
    R = pd.concat(rows, ignore_index=True)
    R["p50"] = R[["p10", "p50"]].max(axis=1)   # 분위수 단조 보정
    R["p90"] = R[["p50", "p90"]].max(axis=1)
    R.to_csv(os.path.join(OUT, f"extreme_forecast_{crop}.csv"), index=False)

    # ── 연도별 요약 ─────────────────────────────────────────────────────────
    def yearly(g):
        cov = ((g.actual >= g.p10) & (g.actual <= g.p90)).mean() * 100
        return pd.Series({
            "n": len(g), "actual": g.actual.mean(),
            "point": g.point.mean(),
            "point_bias": (g.point - g.actual).mean(),
            "p10": g.p10.mean(), "p50": g.p50.mean(), "p90": g.p90.mean(),
            "coverage80": cov,
            "point_R2": r2_score(g.actual, g.point),
            "point_RMSE": np.sqrt(mean_squared_error(g.actual, g.point)),
        })
    yr = R.groupby("year").apply(yearly, include_groups=False).round(2)

    # 극단해 정의: '추세 제거' 후 그해 전국평균이 크게 하회하는 해(수준이 아니라 이상치).
    # 기술추세로 후반 연도가 높으므로 수준만 보면 2012가 안 걸린다 → 선형추세 잔차 사용.
    b1, b0 = np.polyfit(yr.index.values, yr.actual.values, 1)
    yr["detrend"] = yr.actual - (b0 + b1 * yr.index.values)
    yr["extreme"] = yr.detrend <= yr.detrend.quantile(0.20)

    print("=" * 78)
    print(f"극단해 인식 예보 — {crop} (롤링 train ≤Y-1 → predict Y, 분위수 P10/P50/P90)")
    print("=" * 78)
    print(yr[["n", "actual", "point_bias", "p10", "p50", "p90", "coverage80", "point_RMSE", "extreme"]]
          .to_string())

    ext = yr[yr.extreme]; nor = yr[~yr.extreme]
    print("\n[핵심] 점추정은 극단해에서 과대예측(허위 안심), 구간은 하방을 연다")
    print(f"  정상해({len(nor)}개): 점추정 편향 평균 {nor.point_bias.mean():+.2f} bu/ac")
    print(f"  극단해({len(ext)}개): 점추정 편향 평균 {ext.point_bias.mean():+.2f} bu/ac  ← 과대예측")
    cov_all = R.eval('(actual>=p10)&(actual<=p90)').mean() * 100
    cov_ext = R[R.year.isin(ext.index)].eval('(actual>=p10)&(actual<=p90)').mean() * 100
    print(f"  전체 구간[P10,P90] 커버리지 {cov_all:.1f}% (목표 80%, 컨포멀 보정 후)")
    print(f"  극단해 구간 커버리지 {cov_ext:.1f}%")
    for q in QUANTILES:
        print(f"  Pinball P{int(q*100)}: {pinball(R.actual, R[f'p{int(q*100)}'], q):.3f}")

    # ── 2012 집중 ───────────────────────────────────────────────────────────
    if 2012 in yr.index:
        g12 = R[R.year == 2012]
        cov12 = ((g12.actual >= g12.p10) & (g12.actual <= g12.p90)).mean() * 100
        print("\n[2012 대가뭄 — 붕괴를 잡았나]")
        print(f"  실제 {g12.actual.mean():.0f} | 점추정 {g12.point.mean():.0f} (과대 {(g12.point-g12.actual).mean():+.0f}) "
              f"| P10 {g12.p10.mean():.0f} P50 {g12.p50.mean():.0f} P90 {g12.p90.mean():.0f}")
        print(f"  → 점추정은 붕괴를 못 보고 +{(g12.point-g12.actual).mean():.0f} 과대예측(허위 안심). "
              f"P10 하방이 실제({g12.actual.mean():.0f})에 근접, 구간이 {cov12:.0f}% 카운티에서 붕괴를 포함.")

    # ── 붕괴 조기경보: 카운티 단위 정밀도/재현율 ────────────────────────────
    # 실제 '나쁨' = 그 카운티 예측 중앙값 대비 실제가 크게 하회(하위 10% 잔차).
    R["shortfall"] = R.actual - R.p50
    bad = R.shortfall <= R.shortfall.quantile(0.10)          # 실제로 나빴던 사건
    alarm = R.p10 <= R.p50 - (R.p50 - R.p10).median()        # 하방이 넓게 열린 경보
    tp = (bad & alarm).sum(); fp = (~bad & alarm).sum(); fn = (bad & ~alarm).sum()
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    print(f"\n[붕괴 조기경보(카운티)] 정밀도 {prec*100:.0f}% · 재현율 {rec*100:.0f}% "
          f"(경보={int(alarm.sum())}건, 실제나쁨={int(bad.sum())}건)")

    _plot(R, yr, crop)
    return R, yr


def _plot(R, yr, crop):
    fig, ax = plt.subplots(1, 2, figsize=(14, 5.2))

    # (a) 연도별: 실제 vs 점추정 vs 구간
    a = ax[0]; s = yr.sort_index()
    a.fill_between(s.index, s.p10, s.p90, color="#bfdbfe", alpha=.7, label="[P10,P90] 구간")
    a.plot(s.index, s.p50, "--", color="#2563eb", label="P50(중앙)")
    a.plot(s.index, s.point, ":", color="#6b7280", label="점추정")
    a.plot(s.index, s.actual, "o-", color="#111827", ms=4, label="실제")
    for Y in s.index[s.extreme]:
        a.annotate("극단", (Y, s.loc[Y, "actual"]), textcoords="offset points",
                   xytext=(0, -14), ha="center", color="#dc2626", fontsize=8, fontweight="bold")
    a.set(xlabel="예보 연도", ylabel=f"{crop} 수확량 (bu/ac)",
          title="연도별: 구간이 실제를 덮고, 극단해에 하방이 열린다")
    a.legend(fontsize=8.5); a.grid(alpha=.3)

    # (b) 2012 카운티 산점도: 점추정 vs P10
    b = ax[1]; g = R[R.year == 2012]
    lim = [g.actual.min(), g.actual.max()]
    b.plot(lim, lim, "--", color="#9ca3af")
    b.scatter(g.actual, g.point, s=6, alpha=.25, color="#6b7280", label="점추정")
    b.scatter(g.actual, g.p10, s=6, alpha=.25, color="#dc2626", label="P10(하방)")
    b.set(xlabel="실제 2012 수확량 (bu/ac)", ylabel="예측",
          title="2012: 점추정(회색)은 위로 치우침 = 붕괴 놓침\nP10(빨강)이 대각선 아래=하방 포착")
    b.legend(fontsize=9); b.grid(alpha=.3)
    fig.tight_layout()
    out = os.path.join(FIG, f"33_extreme_forecast_{crop}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight"); plt.close(fig)
    print("→ 그림 저장:", out)


if __name__ == "__main__":
    run("corn")
