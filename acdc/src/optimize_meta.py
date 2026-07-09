"""
optimize_meta.py — Phase 4-5 (v3): 단작 조합최적화 + 메타휴리스틱(GA/SA) vs 정확해(MILP)

문제(단작): 각 카운티는 작물 하나만 고른다(z_c ∈ {옥수수, 대두}).
  목적:  Σ_c A_c·rev[c, 선택]  −  λ·(현재 작물과 다르게 고른 카운티 수)     ← 전환비용
  제약:  대두 최소 배정  Σ_c A_c·[대두 선택] ≥ D_soy                       ← 이 커플링이
         이 문제를 '카운티별로 따로 못 푸는' 진짜 조합최적화로 만든다.

rev[c,k] = ML 예측 수확량 × 가격 (Predict-then-Optimize 연결).
왜 GA/SA 인가: 커플링 제약이 붙은 binary 배정은 카운티·작물이 늘수록 조합이 폭발한다
(강의: MILP 한계 → 메타휴리스틱). 여기선 정확해(MILP)와 GA/SA 를 품질·시간으로 비교.

한계: A_c=카운티당 1단위 동일 가정(면적 데이터 부재), x0 는 과거 수익 기준 근사.
"""
from __future__ import annotations
import os, time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pulp
from sklearn.ensemble import HistGradientBoostingRegressor

from prepare import build_panel, feature_columns

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")
PRICE = {"corn": 4.50, "soybean": 12.00}
LAMBDA = 150.0     # 전환비용 (카운티 1곳 바꿀 때 벌점, $)
SOY_MIN_FRAC = 0.35  # 대두 최소 배정 비율 (윤작·수요 제약)
RNG = np.random.default_rng(0)


def _pred_rev(crop):
    df = build_panel(crop); feats = feature_columns(df)
    m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                      max_leaf_nodes=31, random_state=0).fit(df[feats], df[crop])
    latest = df[df.year == df.year.max()].copy()
    latest["rev"] = m.predict(latest[feats]) * PRICE[crop]
    hist = df.groupby("stco")[crop].mean() * PRICE[crop]
    return latest.set_index("stco")["rev"], hist


def load_problem():
    rc, hc = _pred_rev("corn"); rs, hs = _pred_rev("soybean")
    idx = rc.index.intersection(rs.index)
    t = pd.DataFrame({"rev_corn": rc.loc[idx], "rev_soy": rs.loc[idx],
                      "hist_corn": hc.reindex(idx), "hist_soy": hs.reindex(idx)}).dropna()
    t["x0"] = (t.hist_corn >= t.hist_soy).astype(int)  # 현재: 1=옥수수, 0=대두 (근사)
    return t


def objective(z, t, lam=LAMBDA):
    """z: 1=옥수수, 0=대두. 총수익 - 전환비용. (제약은 별도 검사)"""
    rev = np.where(z == 1, t.rev_corn.values, t.rev_soy.values).sum()
    changed = np.sum(z != t.x0.values)
    return rev - lam * changed


def soy_count(z):  # 대두로 배정된 카운티 수 (A_c=1)
    return np.sum(z == 0)


# ---------- 정확해: MILP ----------
def solve_milp(t, lam=LAMBDA):
    n = len(t); prob = pulp.LpProblem("single_crop", pulp.LpMaximize)
    z = [pulp.LpVariable(f"z{i}", cat="Binary") for i in range(n)]  # 1=옥수수
    rc = t.rev_corn.values; rs = t.rev_soy.values; x0 = t.x0.values
    # 전환비용: x0=1이면 (1-z), x0=0이면 z  → 선형
    chg = [(1 - z[i]) if x0[i] == 1 else z[i] for i in range(n)]
    prob += (pulp.lpSum(rc[i] * z[i] + rs[i] * (1 - z[i]) for i in range(n))
             - lam * pulp.lpSum(chg))
    prob += pulp.lpSum(1 - z[i] for i in range(n)) >= int(SOY_MIN_FRAC * n)  # 대두 최소
    t0 = time.time(); prob.solve(pulp.PULP_CBC_CMD(msg=0)); dt = time.time() - t0
    zopt = np.array([int(round(v.value())) for v in z])
    return zopt, objective(zopt, t, lam), dt


# ---------- 메타휴리스틱: GA ----------
def penalized(z, t, lam):
    pen = 1e6 * max(0, int(SOY_MIN_FRAC * len(t)) - soy_count(z))  # 제약위반 벌점
    return objective(z, t, lam) - pen


def solve_ga(t, lam=LAMBDA, pop=80, gens=150):
    n = len(t); x0 = t.x0.values
    P = RNG.integers(0, 2, size=(pop, n)); P[0] = x0.copy()  # 현재 배분을 시드로
    hist = []
    t0 = time.time()
    for g in range(gens):
        fit = np.array([penalized(ind, t, lam) for ind in P])
        hist.append(fit.max())
        # 토너먼트 선택
        newP = [P[fit.argmax()].copy()]  # 엘리트
        while len(newP) < pop:
            a, b = RNG.integers(0, pop, 2); p1 = P[a] if fit[a] > fit[b] else P[b]
            a, b = RNG.integers(0, pop, 2); p2 = P[a] if fit[a] > fit[b] else P[b]
            mask = RNG.integers(0, 2, n).astype(bool)          # 균등 교차
            child = np.where(mask, p1, p2)
            flip = RNG.random(n) < 0.01                        # 돌연변이
            child[flip] ^= 1
            newP.append(child)
        P = np.array(newP)
    dt = time.time() - t0
    fit = np.array([penalized(ind, t, lam) for ind in P]); best = P[fit.argmax()]
    return best, objective(best, t, lam), dt, hist


# ---------- 메타휴리스틱: SA ----------
def solve_sa(t, lam=LAMBDA, iters=40000, T0=8000.0, cool=0.9995):
    n = len(t); z = t.x0.values.copy(); cur = penalized(z, t, lam)
    best = z.copy(); best_f = cur; T = T0; hist = []
    t0 = time.time()
    for it in range(iters):
        i = RNG.integers(0, n); z[i] ^= 1                      # 이웃: 한 카운티 스왑
        f = penalized(z, t, lam); d = f - cur
        if d > 0 or RNG.random() < np.exp(d / max(T, 1e-9)):
            cur = f
            if f > best_f: best_f, best = f, z.copy()
        else:
            z[i] ^= 1                                          # 되돌림
        T *= cool
        if it % 400 == 0: hist.append(best_f)
    dt = time.time() - t0
    return best, objective(best, t, lam), dt, hist


def revenue_only(z, t):
    return float(np.where(z == 1, t.rev_corn.values, t.rev_soy.values).sum())


def run():
    t = load_problem(); n = len(t)
    soy0 = int(soy_count(t.x0.values))
    print("=" * 70); print("Phase 4-5 — 단작 조합최적화: MILP vs GA vs SA"); print("=" * 70)
    print(f"카운티 {n}개 | 대두 최소 {int(SOY_MIN_FRAC*n)}곳(현재 {soy0}곳) | λ={LAMBDA:g}")
    print("문제: '대두 35% 윤작 요건'을 최소 손실로 충족하는 단작 배치를 찾는다.")

    z_m, f_m, dt_m = solve_milp(t)
    z_g, f_g, dt_g, hg = solve_ga(t)
    z_s, f_s, dt_s, hs = solve_sa(t)

    rows = [("MILP (exact)", f_m, dt_m, 0.0, int(np.sum(z_m != t.x0.values))),
            ("GA", f_g, dt_g, 100*(f_m-f_g)/abs(f_m), int(np.sum(z_g != t.x0.values))),
            ("SA", f_s, dt_s, 100*(f_m-f_s)/abs(f_m), int(np.sum(z_s != t.x0.values)))]
    res = pd.DataFrame(rows, columns=["method", "objective", "time_s", "gap_%_vs_exact", "counties_changed"])
    res.round(3).to_csv(os.path.join(OUT, "optimize_meta.csv"), index=False)
    print(f"\n{'method':<14}{'objective':>12}{'time(s)':>9}{'gap%':>7}{'changed':>9}")
    for _, r in res.iterrows():
        print(f"{r.method:<14}{r.objective:>12,.0f}{r.time_s:>9.2f}{r['gap_%_vs_exact']:>7.2f}{r.counties_changed:>9}")
    print(f"\n→ MILP 이 최적해(기준). GA gap {res.iloc[1]['gap_%_vs_exact']:.2f}%, "
          f"SA gap {res.iloc[2]['gap_%_vs_exact']:.2f}% — 메타휴리스틱이 근접해 도달(H5).")
    print(f"→ 이 규모(659×2작물)에선 정확 MILP 가 더 빠르고 최적 — 강의 서사대로 "
          "'작물·카운티가 늘면' GA/SA 우위가 드러난다(외삽).")
    print(f"→ 윤작요건 충족 비용: 최적 배치는 대두 {int(soy_count(z_m))}곳으로 재배치 "
          f"{int(np.sum(z_m!=t.x0.values))}곳, 수익 {revenue_only(t.x0.values,t):,.0f}→{revenue_only(z_m,t):,.0f} "
          "(요건 충족 위한 최소 손실).")

    # 그림21: 수렴 곡선
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.axhline(f_m, color="#111", ls="--", lw=1.5, label="MILP optimum")
    ax.plot(np.linspace(0, 1, len(hg)), hg, color="#2563eb", label="GA (generations)")
    ax.plot(np.linspace(0, 1, len(hs)), hs, color="#dc2626", label="SA (iterations, scaled)")
    ax.set(xlabel="Search progress (normalized)", ylabel="Best objective",
           title="Exact vs metaheuristics: GA/SA converge near the MILP optimum")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(FIG, "21_meta_convergence.png")); plt.close(fig)
    print("→ 그림21 저장, 수치 → outputs/optimize_meta.csv")
    return res


if __name__ == "__main__":
    run()
