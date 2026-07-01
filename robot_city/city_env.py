"""Facility-placement environment on a PLUTO-derived lot grid.

One environment, two constraint modes:

- mode="human": the city keeps people inside it. Zoning FAR caps (light/air
  regulation) limit floor area per lot, use-district separation applies
  (industrial uses are only permitted on M-district lots, worker hubs only
  on C-district lots, per the NYC Zoning Resolution's use groups), hubs must
  stay a safety distance from industrial nodes, and every facility carries a
  human-amenity overhead (egress, daylighting, HVAC sized for occupants).
- mode="robot": no people on site. FAR caps are replaced by a structural
  cap, hubs and amenity overhead disappear, and the binding constraint
  becomes heat: total equipment power in any 3x3 neighbourhood must stay
  under a district-cooling limit.

Efficiency = OUTPUT / (BASE_INPUT + BETA * weighted transport distance).
OUTPUT is identical across modes (same production chain), so the ratio of
optimised efficiencies isolates what removing human constraints buys.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# --- production chain (identical in both modes) ---------------------------
OUTPUT_UNITS = 1000.0   # abstract units produced when the chain is placed
BASE_INPUT = 300.0      # resources consumed by production itself
BETA = 1.0              # resources lost per unit of flow-weighted distance

# --- human-mode parameters -------------------------------------------------
AMENITY_OVERHEAD = 1.45  # gross/net floor factor for occupied buildings
SAFETY_DIST = 2          # min Chebyshev distance hub <-> industrial (cells)
COMMUTE_W = 0.5          # commute flow weight hub -> each industrial node

# --- robot-mode parameters -------------------------------------------------
STRUCT_FAR = 30.0        # structural (not zoning) FAR limit
POWER_KW_PER_SQFT = 0.1  # equipment power density
COOL_CAP_KW = 12000.0    # cooling limit per 3x3 neighbourhood


@dataclass
class Facility:
    name: str
    kind: str        # "industrial" or "hub"
    floor_sqft: float


@dataclass
class CityEnv:
    lots: pd.DataFrame
    mode: str = "human"
    seed: int = 0
    facilities: list = field(init=False)
    flows: list = field(init=False)          # (i, j, weight)

    def __post_init__(self) -> None:
        rng = np.random.default_rng(self.seed)
        self.side = int(self.lots["block"].max())
        self.rc = self.lots[["block", "lot"]].to_numpy() - 1
        area = self.lots["lotarea"].to_numpy(float)
        zone = self.lots["zonedist1"].astype(str).to_numpy(dtype="U16")
        if self.mode == "human":
            self.capacity = self.lots["commfar"].to_numpy(float) * area
            self.zone_ok = {
                "industrial": np.char.startswith(zone, "M"),
                "hub": np.char.startswith(zone, "C"),
            }
        else:
            self.capacity = STRUCT_FAR * area
            everywhere = np.ones(len(self.lots), dtype=bool)
            self.zone_ok = {"industrial": everywhere, "hub": everywhere}
        self.facilities, self.flows = self._build_chain(rng)

    def _build_chain(self, rng) -> tuple[list, list]:
        fac = []
        for i in range(3):
            fac.append(Facility(f"extract_{i}", "industrial",
                                rng.uniform(8000, 15000)))
        for i in range(6):
            fac.append(Facility(f"process_{i}", "industrial",
                                rng.uniform(12000, 25000)))
        for i in range(3):
            fac.append(Facility(f"assemble_{i}", "industrial",
                                rng.uniform(15000, 30000)))
        fac.append(Facility("export_hub", "industrial", 20000))
        flows = []
        for i in range(3):            # extractors feed every processor
            for j in range(3, 9):
                flows.append((i, j, 2.0))
        for j in range(3, 9):         # processors feed assemblers
            for k in range(9, 12):
                flows.append((j, k, 1.5))
        for k in range(9, 12):        # assemblers feed the export node
            flows.append((k, 12, 3.0))
        if self.mode == "human":      # workers must be housed on site
            n_ind = len(fac)
            for h in range(3):
                fac.append(Facility(f"worker_hub_{h}", "hub", 15000))
                for i in range(n_ind):
                    if i % 3 == h:
                        flows.append((n_ind + h, i, COMMUTE_W))
        return fac, flows

    # --- feasibility --------------------------------------------------------
    def gross_floor(self, f: Facility) -> float:
        over = AMENITY_OVERHEAD if self.mode == "human" else 1.0
        return f.floor_sqft * over

    def feasible(self, assign: np.ndarray) -> bool:
        used = np.zeros(len(self.lots))
        for fi, cell in enumerate(assign):
            if not self.zone_ok[self.facilities[fi].kind][cell]:
                return False
            used[cell] += self.gross_floor(self.facilities[fi])
        if np.any(used > self.capacity + 1e-6):
            return False
        if self.mode == "human":
            for hi, fh in enumerate(self.facilities):
                if fh.kind != "hub":
                    continue
                hr, hc = self.rc[assign[hi]]
                for fi, f in enumerate(self.facilities):
                    if f.kind != "industrial":
                        continue
                    r, c = self.rc[assign[fi]]
                    if max(abs(hr - r), abs(hc - c)) < SAFETY_DIST:
                        return False
        else:
            heat = np.zeros((self.side, self.side))
            for fi, cell in enumerate(assign):
                r, c = self.rc[cell]
                heat[r, c] += self.facilities[fi].floor_sqft * POWER_KW_PER_SQFT
            block = np.zeros_like(heat)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    block += np.roll(np.roll(heat, dr, 0), dc, 1)
            if block.max() > COOL_CAP_KW + 1e-6:
                return False
        return True

    # --- objective ----------------------------------------------------------
    def transport(self, assign: np.ndarray) -> float:
        pos = self.rc[assign]
        return float(sum(
            w * (abs(pos[i][0] - pos[j][0]) + abs(pos[i][1] - pos[j][1]))
            for i, j, w in self.flows
        ))

    def efficiency(self, assign: np.ndarray) -> float:
        return OUTPUT_UNITS / (BASE_INPUT + BETA * self.transport(assign))

    def random_assignment(self, rng, max_tries: int = 200) -> np.ndarray:
        """Constructive sampling: place facilities one by one on cells with
        enough remaining capacity, then verify joint feasibility (spacing or
        cooling), retrying the whole placement if it fails."""
        n = len(self.facilities)
        for _ in range(max_tries):
            assign = np.full(n, -1)
            remaining = self.capacity.copy()
            ok = True
            for fi in rng.permutation(n):
                need = self.gross_floor(self.facilities[fi])
                allowed = self.zone_ok[self.facilities[fi].kind]
                cells = np.flatnonzero(allowed & (remaining >= need))
                if len(cells) == 0:
                    ok = False
                    break
                cell = int(rng.choice(cells))
                assign[fi] = cell
                remaining[cell] -= need
            if ok and self.feasible(assign):
                return assign
        raise RuntimeError("could not find a feasible random assignment")
