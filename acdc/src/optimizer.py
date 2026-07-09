"""
optimizer.py — 2단계: 전환비용을 감안한 작물 배치 최적화 (Predict → Optimize)

문제: 각 카운티의 땅을 옥수수 vs 대두에 어떻게 나눌까?
  - 목적: 총생산(공통단위=톤) 최대화
  - 제약: 카운티별 땅은 100% (x=옥수수 비중, 1-x=대두 비중)
  - 전환비용: '지금 심는 배치(x0)'에서 많이 벗어날수록 페널티 λ·|x-x0|

1단계 연결: A_i(옥수수), B_i(대두)는 **ML이 예측한 수확량 Ŷ**을 톤/에이커로 환산한 값.
즉 예측이 최적화 목적함수 계수로 그대로 들어간다.

핵심 분석: λ를 0부터 키우며 '이론적 최적(λ=0)'과 '전환비용 감안 최적'을 비교.
  - λ=0  → 카운티마다 더 나은 작물로 100% 몰빵 (현실성 없는 상한)
  - λ↑   → 현 배치 근처에 머무름 (현실적)
산출물: "총생산 증가 vs 재배치량"의 트레이드오프 곡선.

공통단위: **수익($/에이커)**. 옥수수·대두는 무게(톤)로 비교하면 옥수수가 압도해
'전부 옥수수'로 시시하게 수렴한다(대두는 톤당 값이 2배↑). 그래서 대표 가격으로
수익을 계산해 비교한다 — 옥수수 $4.5/bu, 대두 $12/bu (감도분석 대상 파라미터).
한계: ACDC에 카운티 경작면적이 없어 카운티당 땅=1단위로 동일 가정(방향성 분석).
      x0(현 옥수수 비중)는 과거 수익 비율로 근사(진짜 면적 데이터 대체).
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pulp
from sklearn.ensemble import HistGradientBoostingRegressor

from prepare import build_panel, feature_columns, CORN_BELT_FIPS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")
PRICE_CORN, PRICE_SOY = 4.50, 12.00  # 대표 가격 $/bushel (감도분석 대상)


def _fit_predict(crop):
    df = build_panel(crop); feats = feature_columns(df)
    m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                      max_leaf_nodes=31, random_state=0).fit(df[feats], df[crop])
    latest = df[df.year == df.year.max()].copy()
    latest["pred"] = m.predict(latest[feats])
    hist = df.groupby("stco")[crop].mean().rename(f"{crop}_hist")
    return latest.set_index("stco")[["pred", "state_abbr"]], hist


def build_alloc_table():
    """카운티별 A(옥수수 톤/ac), B(대두 톤/ac), x0(현 옥수수 비중 근사)."""
    corn, corn_hist = _fit_predict("corn")
    soy, soy_hist = _fit_predict("soybean")
    idx = corn.index.intersection(soy.index)
    t = pd.DataFrame(index=idx)
    t["state_abbr"] = corn.loc[idx, "state_abbr"]
    t["A"] = corn.loc[idx, "pred"] * PRICE_CORN     # 옥수수 수익 $/ac (예측)
    t["B"] = soy.loc[idx, "pred"] * PRICE_SOY        # 대두 수익 $/ac (예측)
    # 현 옥수수 비중 x0: 과거 수익 비율로 근사(면적 데이터 부재)
    ch = (corn_hist.reindex(idx) * PRICE_CORN)
    sh = (soy_hist.reindex(idx) * PRICE_SOY)
    t["x0"] = (ch / (ch + sh)).clip(0, 1).fillna(0.5)
    return t.dropna(subset=["A", "B"])


def solve(t, lam):
    """전환비용 λ 하에서 카운티별 옥수수 비중 x를 최적화."""
    prob = pulp.LpProblem("alloc", pulp.LpMaximize)
    n = len(t)
    x = [pulp.LpVariable(f"x{i}", 0, 1) for i in range(n)]
    d = [pulp.LpVariable(f"d{i}", 0) for i in range(n)]  # |x-x0|
    A = t.A.values; B = t.B.values; x0 = t.x0.values
    # 목적: 총생산 - λ·Σ|x-x0|
    prob += (pulp.lpSum(A[i] * x[i] + B[i] * (1 - x[i]) for i in range(n))
             - lam * pulp.lpSum(d))
    for i in range(n):
        prob += d[i] >= x[i] - x0[i]
        prob += d[i] >= x0[i] - x[i]
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    xv = np.array([v.value() for v in x])
    prod = float(np.sum(A * xv + B * (1 - xv)))
    change = float(np.sum(np.abs(xv - x0)))
    return xv, prod, change


def run():
    t = build_alloc_table()
    base_prod = float(np.sum(t.A * t.x0 + t.B * (1 - t.x0)))
    print("=" * 70); print("2단계 — 전환비용 감안 작물 배치 최적화 (옥수수 vs 대두)"); print("=" * 70)
    print(f"카운티 {len(t):,}개 | 기준(현 배치) 총수익 ${base_prod:,.0f}/ac 합(상대단위)")

    # λ = 전환 페널티 ($ / 카운티 땅 100% 전환당). 수익 규모($100s)에 맞춰 스윕.
    lambdas = [0.0, 25, 50, 100, 150, 250, 500]
    rows = []
    x_by_lambda = {}
    for lam in lambdas:
        xv, prod, change = solve(t, lam)
        rows.append({"lambda": lam, "production": prod,
                     "gain_pct": 100 * (prod - base_prod) / base_prod,
                     "total_change": change, "avg_change_pct": 100 * change / len(t)})
        x_by_lambda[lam] = xv
    res = pd.DataFrame(rows)
    res.round(2).to_csv(os.path.join(OUT, "optimization.csv"), index=False)
    print(res.round(2).to_string(index=False))

    # 트레이드오프 곡선: 재배치량(x축) vs 총생산 증가%(y축)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(res.avg_change_pct, res.gain_pct, "o-", color="#7c3aed")
    for _, r in res.iterrows():
        ax.annotate(f"λ={r['lambda']:g}", (r.avg_change_pct, r.gain_pct),
                    textcoords="offset points", xytext=(6, 4), fontsize=8.5)
    ax.set(xlabel="Average land reallocated per county (%)",
           ylabel="Total production gain vs current (%)",
           title="Transition-cost tradeoff: how much to shift for how much gain")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "17_transition_tradeoff.png")); plt.close(fig)

    # 대표 λ(0.05)에서 주별 옥수수 비중 변화
    lam_rep = 150  # 트레이드오프 곡선의 무릎(knee): 적은 재배치로 이득 대부분 확보
    xv = x_by_lambda[lam_rep]
    t2 = t.copy(); t2["x_opt"] = xv; t2["corn_shift"] = t2["x_opt"] - t2["x0"]
    by_state = t2.groupby("state_abbr")["corn_shift"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#15803d" if v < 0 else "#b45309" for v in by_state.values]
    ax.barh(by_state.index, 100 * by_state.values, color=colors)
    ax.set(xlabel="Change in corn share (%pt)  [+corn / -soybean]",
           title=f"Recommended shift by state (transition-aware, λ={lam_rep})")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "18_alloc_shift_by_state.png")); plt.close(fig)

    g0 = res.loc[res['lambda'] == 0].iloc[0]
    gk = res.loc[res['lambda'] == lam_rep].iloc[0]
    print(f"\n[해석] λ=0(이론최적)은 카운티당 평균 {g0.avg_change_pct:.0f}% 재배치로 "
          f"+{g0.gain_pct:.1f}% 수익↑ — 전환비용 무시한 비현실적 상한.")
    print(f"       λ={lam_rep}(무릎)은 평균 {gk.avg_change_pct:.0f}%만 바꿔 +{gk.gain_pct:.1f}% 수익↑ "
          f"— 이득의 {100*gk.gain_pct/g0.gain_pct:.0f}%를 재배치 {100*gk.avg_change_pct/g0.avg_change_pct:.0f}%로 확보.")
    print("       → 여기서 더 짜내려면 churn만 급증 → 전환비용 감안 시 λ≈150이 합리적.")
    print("       주의: 카운티 면적·x0는 근사이므로 gain%의 절대크기보다 '곡선의 모양'이 결론.")
    print("\n그림 17·18 저장, 수치 → outputs/optimization.csv")
    return res


if __name__ == "__main__":
    run()
