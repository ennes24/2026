# Project Plan: Robot City Optimisation (12 months)

## Research questions

- **RQ1 (capability).** Given infrastructure built for them, can robot
  agents interacting like humans out-produce a human city - absolutely,
  not just per resource? *Current toy answer: yes, output ratio ~1.4,
  efficiency ratio ~2.9; the thesis must show this survives calibration
  and sensitivity.*
- **RQ2 (method).** Does reinforcement learning (PPO, later +GNN) find
  better layouts with fewer evaluations than classical baselines
  (greedy local search, simulated annealing, NSGA-II)?
- **RQ3 (economics).** Under what capital-cost and efficiency assumptions
  does building a robot city pay back fast enough that an investor would
  prefer it over the status quo?

RQ2 is the CS-thesis core; RQ1 gives it stakes; RQ3 is the applied
discussion chapter.

## What already exists (phase 0, done)

Working pipeline in this directory: PLUTO-schema lot grid, human/robot
constraint modes (zoning FAR, use districts, worker housing, utilisation,
amenity overhead, occupant energy, robot maintenance, cooling limit),
agglomeration-dependent output, three classical optimisers, break-even
model. Headline numbers: output ratio 1.36, rho ~2.9 on sample lots.

## Phase 1 - Ground and stress the toy (months 1-2)

1. Download real PLUTO (`fetch_pluto.py` on an open network), run the
   pipeline on a real Manhattan M-district window; keep the sample-lot
   results as a robustness check.
2. Calibrate parameters to citable anchors and record each source:
   utilisation (Fed G.17), occupant energy share (CBECS), amenity
   gross/net factors (architectural standards), power density and cooling
   (data-centre engineering), maintenance fraction (IFR service data),
   worker density and support floor (Census/BLS, NYC housing stats).
3. Sensitivity sweeps - the most important experiments in the project:
   - robot interaction efficiency in [0.2, 1.0]: find the threshold below
     which the robot city stops out-producing (current back-of-envelope:
     it wins on resources even at human-level 0.4);
   - agglomeration gain, cooling cap, lambda (spillover decay);
   - report rho as a band, not a point.

**Deliverable:** calibrated results section + sensitivity figures. This
alone is a defensible mini-paper if everything later slips.

## What to reuse instead of building (start here, month 3)

Nobody has published the human-vs-robot constraint comparison or the
agglomeration asymmetry - that gap is this thesis's novelty. But every
piece of machinery exists and is open source; adapt, don't rewrite:

- **DRL-urban-planning** (tsinghua-fib-lab, Nature Computational Science
  2023): the closest existing system - sequential spatial planning of
  land use on a city graph with a GNN policy and PPO, code and scenarios
  released. It optimises human livability (service accessibility,
  greenness); we flip the objective to robot efficiency and add the
  constraint-mode comparison. Reuse: environment structure, GNN encoder,
  training loop. Primary base for phases 2-3.
- **circuit_training / AlphaChip** (google-research, Apache 2.0, with
  pre-trained checkpoints): the sequential-placement RL reference; heavier
  infrastructure, use as methodological citation and fallback.
- **gym-flp** (Operations Research Forum 2024): Gym environments for
  facility layout problems - near drop-in for our placement MDP.
- **QAPLIB**: our placement problem is a quadratic-assignment variant;
  instances with known optima give RQ2 an external benchmark.
- **pymoo** (NSGA-II) and **sb3-contrib** (MaskablePPO): baselines and
  learner, both off the shelf.

## Phase 2 - RL enters (months 3-5)

0. Clone DRL-urban-planning and gym-flp; reproduce one of their published
   runs first, then port our two-constraint objective into whichever
   fits better, rather than wiring PPO from scratch.
1. Wrap `CityEnv` as a Gymnasium environment: sequential placement MDP
   (state = partial layout + remaining facilities; action = choose a lot;
   action masking = zoning/capacity/cooling feasibility; terminal reward
   = efficiency). The env already exposes exactly this interface.
2. PPO + MLP with action masking (sb3-contrib MaskablePPO). Success bar:
   match or beat annealing's best efficiency.
3. Randomise instances per episode (facility sizes, flows, lot windows)
   so the policy learns generalisation, not one layout - this is what
   separates an RL contribution from a solver run.
4. Metrics vs baselines: best efficiency, evaluations-to-quality (sample
   efficiency), wall-clock, transfer to unseen instances.

**Deliverable:** RQ2 experiment table. Honest framing: if PPO does not
beat SA, the negative result plus analysis is still a chapter.

## Phase 3 - GNN + multi-objective (months 6-8)

1. Replace the MLP with a GNN encoder over the lot/flow graph (the chip-
   placement precedent, Mirhoseini et al. 2021); test transfer across
   grid sizes.
2. Vector reward (output, waste heat exported, robustness) with a
   preference-conditioned policy (envelope MORL, Yang et al. 2019);
   compare the learned Pareto front against NSGA-II (pymoo) on
   hypervolume.
3. Robustness axis: random node-failure tests on optimised layouts -
   does the efficient robot city degrade more steeply? (The
   efficiency-fragility trade-off from the original conversation.)

**Deliverable:** Pareto front + fragility analysis; this is the thesis's
methodological novelty (chip-placement RL x MORL x physical constraints).

## Phase 4 - Economics (months 9-10)

1. Re-run `breakeven.py` with the calibrated rho band; add discounting
   and construction-time lag; sensitivity on capital per job.
2. Threshold statement for RQ3: "investment is rational if capital per
   automated job < $X and robot interaction efficiency > Y".

**Deliverable:** the applied chapter answering "would power invest?".

## Phase 5 - Writing + portfolio (months 11-12)

1. Thesis text; figures already accumulate from each phase.
2. Portfolio artifacts: layout-evolution animation (SA/RL improving a
   city), interactive Pareto slider (weights -> city shape morphs),
   before/after human-vs-robot maps.

## Standing rules

- Every phase ends with something runnable and a committed figure -
  never more than two weeks without a checkpoint.
- Baselines before learning: no RL result is reported without the
  classical comparison on the same instances.
- Parameters carry citations or they carry a "toy" label; rho is always
  reported with its sensitivity band.
- Scope guard: 3D stacking, real geography beyond Manhattan windows, and
  closed-loop material cycles are explicitly out of scope for the thesis
  (listed as future work).

## Risk table

| risk | fallback |
|---|---|
| PPO never beats SA | negative-result chapter + analysis of why (reward sparsity, action-space size) |
| real PLUTO unreachable | sample lots are schema-identical; results labelled accordingly |
| MORL too heavy for the timeline | fixed-weight scalarisation grid instead of conditioned policy |
| time squeeze in months 9+ | phases 1-2 alone already answer RQ1+RQ2 minimally |
