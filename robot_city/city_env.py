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

Efficiency = OUTPUT / (process + services + maintenance + transport).
OUTPUT is identical across modes (same production chain), so the ratio of
optimised efficiencies isolates what removing human constraints buys.
Input channels:
- process: proportional to EFFECTIVE process floor, identical in both modes
  (the machines do the same work either way)
- utilisation: humans run shifts with breaks and holidays (~75% capacity
  utilisation, cf. the Fed's G.17 series); lights-out operation sustains
  ~95%. The same effective floor therefore needs x1.33 physical floor in
  human mode and x1.05 in robot mode - which propagates into services,
  land take and feasibility
- services: proportional to GROSS physical floor (amenity overhead x1.45,
  worker housing) times an occupant factor of 1.5 in human mode - per
  CBECS roughly a third of commercial building energy serves occupants
  (lighting, comfort HVAC), which a lights-out facility does not spend
- support housing (human only): the workforce implied by the process floor
  must live somewhere; hubs are sized from workers x floor-per-resident
  instead of a token constant
- maintenance (robot only): robots are not free - upkeep, spares and
  compute add a fraction on top of process input
- transport: flow-weighted distance, as before (human mode adds commute)
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# --- production chain (identical in both modes) ---------------------------
OUTPUT_UNITS = 1000.0      # abstract units produced when the chain is placed
PROCESS_INTENSITY = 1.0    # input per 1,000 sqft of EFFECTIVE process floor
SERVICE_INTENSITY = 0.5    # building-services input per 1,000 sqft gross
OCCUPANT_FACTOR = 1.5      # occupied buildings spend ~1/3 more on people
BETA = 1.0                 # resources lost per unit flow-weighted distance

# --- human-mode parameters -------------------------------------------------
AMENITY_OVERHEAD = 1.45   # gross/net floor factor for occupied buildings
SAFETY_DIST = 2           # min Chebyshev distance hub <-> industrial (cells)
COMMUTE_W = 0.5           # commute flow weight hub -> each industrial node
HUMAN_UPTIME = 0.75       # shift schedules, breaks, holidays (Fed G.17)
WORKERS_PER_KSQFT = 1.25  # ~1 worker per 800 sqft of process floor
SUPPORT_SQFT = 600.0      # housing + daily services floor per worker
N_HUBS = 4

# --- robot-mode parameters -------------------------------------------------
STRUCT_FAR = 30.0         # structural (not zoning) FAR limit
ROBOT_UPTIME = 0.95       # lights-out continuous operation
MAINT_FRACTION = 0.10     # upkeep, spares, compute on top of process input
POWER_KW_PER_SQFT = 0.1   # equipment power density
COOL_CAP_KW = 12000.0     # cooling limit per 3x3 neighbourhood


@dataclass
class Facility:
    name: str
    kind: str          # "industrial" or "hub"
    floor_sqft: float  # industrial: EFFECTIVE (at 100% uptime); hub: physical


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
            process_ksqft = sum(f.floor_sqft for f in fac) / 1000
            workers = process_ksqft * WORKERS_PER_KSQFT / HUMAN_UPTIME
            hub_floor = workers * SUPPORT_SQFT / N_HUBS
            for h in range(N_HUBS):
                fac.append(Facility(f"worker_hub_{h}", "hub", hub_floor))
                for i in range(n_ind):
                    if i % N_HUBS == h:
                        flows.append((n_ind + h, i, COMMUTE_W))
        return fac, flows

    def uptime(self) -> float:
        return HUMAN_UPTIME if self.mode == "human" else ROBOT_UPTIME

    def physical_floor(self, f: Facility) -> float:
        """Floor that must actually be built: effective floor grossed up by
        utilisation for industrial nodes; hubs are already physical."""
        if f.kind == "industrial":
            return f.floor_sqft / self.uptime()
        return f.floor_sqft

    # --- feasibility --------------------------------------------------------
    def gross_floor(self, f: Facility) -> float:
        over = AMENITY_OVERHEAD if self.mode == "human" else 1.0
        return self.physical_floor(f) * over

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
                heat[r, c] += (self.physical_floor(self.facilities[fi])
                               * POWER_KW_PER_SQFT)
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

    def input_breakdown(self, assign: np.ndarray) -> dict:
        effective = sum(f.floor_sqft for f in self.facilities
                        if f.kind == "industrial")
        gross_total = sum(self.gross_floor(f) for f in self.facilities)
        occ = OCCUPANT_FACTOR if self.mode == "human" else 1.0
        process = PROCESS_INTENSITY * effective / 1000
        maint = MAINT_FRACTION * process if self.mode == "robot" else 0.0
        return {
            "process": process,
            "services": SERVICE_INTENSITY * gross_total / 1000 * occ,
            "maintenance": maint,
            "transport": BETA * self.transport(assign),
        }

    def efficiency(self, assign: np.ndarray) -> float:
        return OUTPUT_UNITS / sum(self.input_breakdown(assign).values())

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
