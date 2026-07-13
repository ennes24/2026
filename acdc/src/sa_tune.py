"""
sa_tune.py — 강의 기반: Simulated Annealing 으로 수확량 모델 하이퍼파라미터 튜닝

참고한 강의:
- "Hyper-Parameter Tuning in Simulated Annealing": P(E)=exp(-ΔE/T), 지수 냉각 T_{k+1}=α·T_k,
  초기수용확률 p, 요인(factor)·수준(level)·반복(N=10~15) 실험설계.
- "Metaheuristics Performance Assessment": 단일 실행은 함정 → N회 반복 후 평균±표준편차.
  FEV(function evaluation)를 공정 비용단위로. Efficiency(수렴·FEV) vs Effectiveness(품질·신뢰도).
- "Decision Trees"/"Intro ML": 트리계열 모델, 교차검증으로 일반화 성능 측정.

설계:
- 결정변수 = HistGBM 하이퍼파라미터 (learning_rate, max_leaf_nodes, max_iter,
  l2_regularization, min_samples_leaf).
- 에너지 E = 학습셋(≤2010) 3-fold CV RMSE (낮을수록 좋음). 누수 방지 위해 튜닝은 train만.
- 이웃 = 파라미터 하나를 무작위 이동. 냉각 = 지수. 종료 = 고정 FEV 예산.
- 공정 비교: SA vs Random Search 를 '같은 FEV 예산'으로, 각각 여러 seed 반복 → 평균±std.
- 최종: 승자 설정으로 전체 재학습 → held-out 2011-2015 test R² 를 default 와 비교.
"""
from __future__ import annotations
import os, json, time
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import mean_squared_error, r2_score

from prepare import build_panel, feature_columns

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs")

# 탐색 공간 (요인·범위). 이웃 이동 시 이 범위 안에서 움직인다.
SPACE = {
    "learning_rate":     (0.02, 0.30, "float_log"),
    "max_leaf_nodes":    (15, 63, "int"),
    "max_iter":          (100, 350, "int"),
    "l2_regularization": (0.0, 5.0, "float"),
    "min_samples_leaf":  (10, 60, "int"),
}
DEFAULT = {"learning_rate": 0.05, "max_leaf_nodes": 31, "max_iter": 400,
           "l2_regularization": 0.0, "min_samples_leaf": 20}


def make_model(hp):
    return HistGradientBoostingRegressor(
        learning_rate=hp["learning_rate"], max_leaf_nodes=int(hp["max_leaf_nodes"]),
        max_iter=int(hp["max_iter"]), l2_regularization=hp["l2_regularization"],
        min_samples_leaf=int(hp["min_samples_leaf"]), random_state=0)


def cv_rmse(hp, X, y, folds=3):
    """에너지 함수 = 3-fold CV RMSE. 한 번 호출 = 1 FEV."""
    kf = KFold(folds, shuffle=True, random_state=0)
    errs = []
    for a, b in kf.split(X):
        m = make_model(hp).fit(X.iloc[a], y.iloc[a])
        errs.append(np.sqrt(mean_squared_error(y.iloc[b], m.predict(X.iloc[b]))))
    return float(np.mean(errs))


def clip(name, v):
    lo, hi, kind = SPACE[name]
    v = min(max(v, lo), hi)
    return int(round(v)) if kind == "int" else v


def neighbor(hp, rng):
    """이웃: 파라미터 하나를 현재값 근처로 이동(연속은 ±10~20%, 정수는 ±스텝)."""
    h = dict(hp); name = rng.choice(list(SPACE))
    lo, hi, kind = SPACE[name]
    if kind == "float_log":
        h[name] = clip(name, hp[name] * np.exp(rng.normal(0, 0.35)))
    elif kind == "float":
        h[name] = clip(name, hp[name] + rng.normal(0, (hi - lo) * 0.15))
    else:
        h[name] = clip(name, hp[name] + rng.choice([-1, 1]) * max(1, int((hi - lo) * 0.1)))
    return h


def random_hp(rng):
    h = {}
    for name, (lo, hi, kind) in SPACE.items():
        if kind == "float_log":
            h[name] = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
        elif kind == "float":
            h[name] = float(rng.uniform(lo, hi))
        else:
            h[name] = int(rng.integers(lo, hi + 1))
    return h


def sa_search(X, y, budget, seed, p0=0.8, alpha=0.9):
    """SA 튜닝. budget=FEV 예산. 강의식: P=exp(-ΔE/T), 지수냉각. best-so-far 곡선 반환."""
    rng = np.random.default_rng(seed)
    cur = dict(DEFAULT); cur_E = cv_rmse(cur, X, y); fev = 1
    best, best_E = dict(cur), cur_E
    # 초기 온도: 초기수용확률 p0 이 되도록 T0 = -Δ0/ln(p0) (Δ0=대표 악화폭 추정)
    d0 = max(cur_E * 0.03, 0.5)
    T = -d0 / np.log(p0)
    curve = [best_E]
    while fev < budget:
        cand = neighbor(cur, rng); cand_E = cv_rmse(cand, X, y); fev += 1
        dE = cand_E - cur_E
        if dE <= 0 or rng.random() < np.exp(-dE / max(T, 1e-9)):
            cur, cur_E = cand, cand_E
            if cur_E < best_E:
                best, best_E = dict(cur), cur_E
        T *= alpha
        curve.append(best_E)
    return best, best_E, curve


def random_search(X, y, budget, seed):
    rng = np.random.default_rng(seed)
    best, best_E, curve = None, np.inf, []
    for _ in range(budget):
        hp = random_hp(rng); E = cv_rmse(hp, X, y)
        if E < best_E: best, best_E = hp, E
        curve.append(best_E)
    return best, best_E, curve


def run(crop="corn", budget=30, seeds=(0, 1, 2)):
    df = build_panel(crop); feats = feature_columns(df)
    tr = df[df.year < 2011]; te = df[df.year >= 2011]
    Xtr, ytr, Xte, yte = tr[feats], tr[crop], te[feats], te[crop]
    # 튜닝 속도: CV 는 train 서브샘플(~12k)로 평가(상대비교엔 충분). 최종 test 는 전체로.
    if len(Xtr) > 12000:
        s = Xtr.sample(12000, random_state=0).index
        Xs, ys = Xtr.loc[s], ytr.loc[s]
    else:
        Xs, ys = Xtr, ytr

    def test_r2(hp):
        m = make_model(hp).fit(Xtr, ytr)
        return r2_score(yte, m.predict(Xte))

    print("=" * 70)
    print(f"SA 하이퍼파라미터 튜닝 — {crop}  (FEV예산 {budget}, seeds {list(seeds)})")
    print("=" * 70)
    E_def = cv_rmse(DEFAULT, Xs, ys)
    print(f"[기본값] CV RMSE {E_def:.3f} | test R2 {test_r2(DEFAULT):.3f}  (현재 손으로 정한 값)")

    sa_res, rs_res = [], []
    sa_curves = []
    for s in seeds:
        b, e, c = sa_search(Xs, ys, budget, s); sa_res.append((e, test_r2(b), b)); sa_curves.append(c)
        b2, e2, _ = random_search(Xs, ys, budget, s + 100); rs_res.append((e2, test_r2(b2)))

    sa_cv = np.array([r[0] for r in sa_res]); sa_t = np.array([r[1] for r in sa_res])
    rs_cv = np.array([r[0] for r in rs_res]); rs_t = np.array([r[1] for r in rs_res])
    print(f"\n{'방법':<16}{'CV RMSE (평균±std)':>24}{'test R2 (평균±std)':>22}")
    print(f"{'기본값':<16}{E_def:>18.3f}{'':6}{test_r2(DEFAULT):>16.3f}")
    print(f"{'Random Search':<16}{rs_cv.mean():>14.3f}±{rs_cv.std():.3f}{'':4}{rs_t.mean():>12.3f}±{rs_t.std():.3f}")
    print(f"{'SA (강의식)':<16}{sa_cv.mean():>14.3f}±{sa_cv.std():.3f}{'':4}{sa_t.mean():>12.3f}±{sa_t.std():.3f}")

    best_i = int(np.argmin(sa_cv)); best_hp = sa_res[best_i][2]
    print(f"\n→ SA 최적 설정: " + ", ".join(f"{k}={round(v,3) if isinstance(v,float) else v}" for k, v in best_hp.items()))
    print(f"→ 기본값 대비 test R2: {test_r2(DEFAULT):.3f} → {sa_res[best_i][1]:.3f} "
          f"({sa_res[best_i][1]-test_r2(DEFAULT):+.3f})")
    print("→ 강의 포인트: 단일 실행이 아니라 seed 여러 개의 평균±std 로 보고(노이즈 vs 신호 구분).")

    out = {"crop": crop, "budget": budget, "seeds": list(seeds),
           "default": {"cv_rmse": E_def, "test_r2": test_r2(DEFAULT)},
           "random_search": {"cv_rmse_mean": float(rs_cv.mean()), "cv_rmse_std": float(rs_cv.std()),
                             "test_r2_mean": float(rs_t.mean()), "test_r2_std": float(rs_t.std())},
           "sa": {"cv_rmse_mean": float(sa_cv.mean()), "cv_rmse_std": float(sa_cv.std()),
                  "test_r2_mean": float(sa_t.mean()), "test_r2_std": float(sa_t.std()),
                  "best_hp": {k: (round(v, 4) if isinstance(v, float) else int(v)) for k, v in best_hp.items()},
                  "best_test_r2": float(sa_res[best_i][1])},
           "curves_sa": [ [round(x, 3) for x in c] for c in sa_curves ]}
    with open(os.path.join(OUT, f"sa_tune_{crop}.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    t0 = time.time()
    run("corn")
    print(f"\n소요 {time.time()-t0:.0f}s")
