"""Optimisers for the placement problem: random search, greedy, annealing.

Simulated annealing is the workhorse (numpy-only, no RL dependencies); the
environment exposes the same assignment/evaluate interface an RL agent
would use, so a PPO policy can replace these later without touching the
environment.
"""

import numpy as np

from city_env import CityEnv


def random_search(env: CityEnv, iters: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    best, best_eff = None, -np.inf
    for _ in range(iters):
        try:
            a = env.random_assignment(rng)
        except RuntimeError:
            continue
        eff = env.efficiency(a)
        if eff > best_eff:
            best, best_eff = a, eff
    return best


def greedy(env: CityEnv, seed: int = 0, passes: int = 3) -> np.ndarray:
    """Local improvement from a feasible start: repeatedly move each facility
    (in descending total-flow order) to the feasible cell that minimises
    total transport. Always returns a feasible assignment."""
    rng = np.random.default_rng(seed)
    n = len(env.facilities)
    totals = np.zeros(n)
    for i, j, w in env.flows:
        totals[i] += w
        totals[j] += w
    order = np.argsort(-totals)
    assign = env.random_assignment(rng)
    for _ in range(passes):
        for fi in order:
            best_cell, best_eff = assign[fi], env.efficiency(assign)
            allowed = np.flatnonzero(env.zone_ok[env.facilities[fi].kind])
            for cell in allowed:
                if cell == assign[fi]:
                    continue
                trial = assign.copy()
                trial[fi] = cell
                if not env.feasible(trial):
                    continue
                eff = env.efficiency(trial)
                if eff > best_eff:
                    best_cell, best_eff = cell, eff
            assign[fi] = best_cell
    return assign


def anneal(env: CityEnv, iters: int = 6000, seed: int = 0,
           t0: float = 30.0, t1: float = 0.1) -> np.ndarray:
    """Maximises efficiency; cost is scaled so temperatures stay meaningful
    (efficiency differences per move are ~1e-3)."""
    rng = np.random.default_rng(seed)

    def cost_of(a):
        return -1000.0 * env.efficiency(a)

    cur = env.random_assignment(rng)
    cur_cost = cost_of(cur)
    best, best_cost = cur.copy(), cur_cost
    for step in range(iters):
        temp = t0 * (t1 / t0) ** (step / iters)
        cand = cur.copy()
        fi = rng.integers(len(cand))
        allowed = np.flatnonzero(env.zone_ok[env.facilities[fi].kind])
        cand[fi] = rng.choice(allowed)
        if not env.feasible(cand):
            continue
        cost = cost_of(cand)
        if cost < cur_cost or rng.random() < np.exp((cur_cost - cost) / temp):
            cur, cur_cost = cand, cost
            if cost < best_cost:
                best, best_cost = cand.copy(), cost
    return best
