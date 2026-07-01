"""Headline experiment: optimise the same production chain under human vs
robot constraints and measure the efficiency gap.

Outputs:
- outputs/comparison.csv        per-mode/per-method efficiencies
- outputs/layouts.png           best human vs robot layout side by side
- outputs/efficiency_ratio.txt  the single number chapter 2 needs (rho)
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from city_env import CityEnv
from optimize import anneal, greedy, random_search
from sample_data import make_lots

N_SEEDS = 5
SA_ITERS = 6000


def load_lots() -> pd.DataFrame:
    real = "data/pluto_manhattan.csv"
    if os.path.exists(real):
        df = pd.read_csv(real)
        print(f"using real PLUTO data ({len(df)} lots)")
        return df
    print("real PLUTO file not found; using schema-matched sample lots")
    return make_lots()


def evaluate_mode(lots: pd.DataFrame, mode: str) -> dict:
    rows = []
    best_assign, best_env, best_eff = None, None, -np.inf
    for seed in range(N_SEEDS):
        env = CityEnv(lots=lots, mode=mode, seed=0)
        rnd = random_search(env, iters=50, seed=seed)
        grd = greedy(env, seed=seed)
        ann = anneal(env, iters=SA_ITERS, seed=seed)
        for method, a in (("random", rnd), ("greedy", grd), ("anneal", ann)):
            eff = env.efficiency(a)
            rows.append({"mode": mode, "method": method, "seed": seed,
                         "transport": env.transport(a), "efficiency": eff})
            if method != "random" and eff > best_eff:
                best_assign, best_env, best_eff = a, env, eff
    return {"rows": rows, "assign": best_assign, "env": best_env,
            "eff": best_eff}


def plot_layouts(human: dict, robot: dict, path: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, res, title in ((axes[0], human, "human constraints"),
                           (axes[1], robot, "robot constraints")):
        env, assign = res["env"], res["assign"]
        colors = {"extract": "tab:green", "process": "tab:blue",
                  "assemble": "tab:orange", "export": "tab:red",
                  "worker": "black"}
        for i, j, w in env.flows:
            p, q = env.rc[assign[i]], env.rc[assign[j]]
            ax.plot([p[1], q[1]], [p[0], q[0]], "-", color="gray",
                    alpha=0.3, lw=w)
        seen = set()
        for fi, f in enumerate(env.facilities):
            r, c = env.rc[assign[fi]]
            key = f.name.split("_")[0]
            label = key if key not in seen else None
            seen.add(key)
            ax.scatter(c, r, s=f.floor_sqft / 120, color=colors[key],
                       label=label, zorder=3, edgecolors="white")
        ax.set_title(f"{title}\nefficiency = {res['eff']:.3f}")
        ax.set_xlim(-1, env.side)
        ax.set_ylim(env.side, -1)
        ax.legend(loc="upper right", fontsize=8)
    fig.suptitle("Same production chain, optimised under each constraint set")
    fig.tight_layout()
    fig.savefig(path, dpi=130)


def main() -> None:
    os.makedirs("outputs", exist_ok=True)
    lots = load_lots()
    human = evaluate_mode(lots, "human")
    robot = evaluate_mode(lots, "robot")

    df = pd.DataFrame(human["rows"] + robot["rows"])
    df.to_csv("outputs/comparison.csv", index=False)
    summary = df.groupby(["mode", "method"])["efficiency"].agg(["mean", "std"])
    print("\n", summary.round(4))

    rho = robot["eff"] / human["eff"]
    with open("outputs/efficiency_ratio.txt", "w") as fh:
        fh.write(f"{rho:.4f}\n")
    print(f"\nbest human efficiency : {human['eff']:.4f}")
    print(f"best robot efficiency : {robot['eff']:.4f}")
    print(f"efficiency ratio rho  : {rho:.3f}")

    plot_layouts(human, robot, "outputs/layouts.png")
    print("wrote outputs/comparison.csv, outputs/layouts.png,"
          " outputs/efficiency_ratio.txt")


if __name__ == "__main__":
    main()
