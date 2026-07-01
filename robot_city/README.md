# Robot City: what does removing human constraints buy?

Two questions, in the order they must be answered:

1. **Technical (chapter 1).** Take a production chain and place it on a real
   city's tax-lot grid twice - once under the constraints a human city must
   obey, once under the constraints a robot-only city must obey. How much
   more output-per-resource does the robot version achieve? That single
   number is the *efficiency ratio* (rho).
2. **Economic (chapter 2).** Plug rho into a break-even model: if a
   robot city had to produce enough for every NYC resident to live without
   working, what would it cost to build and run, and how fast would the
   investment pay back?

## Why New York

NYC publishes lot-level zoning data (PLUTO: FAR caps, lot areas, zoning
districts for ~850k tax lots), and its Zoning Resolution is explicit about
*why* each constraint exists - the 1916 setback rules protect light and air
for people at street level, use-district separation keeps industry away from
homes, egress and daylighting codes size buildings around occupants. Those
are precisely the constraints that vanish when no one is inside.

## The two constraint sets

| constraint | human mode | robot mode |
|---|---|---|
| floor area per lot | zoning FAR cap (light/air) | structural cap (FAR 30) |
| use districts | industry on M lots, hubs on C lots only | anywhere |
| worker hubs | required, >= 2 cells from industry | none |
| amenity overhead | x1.45 gross/net floor | x1.0 |
| binding limit | zoning | cooling: <= 12 MW per 3x3 block |

Same production chain, same objective in both:
`efficiency = output / (process input + building services + transport)`.
Process input is identical per sqft in both modes (the machines do the same
work); building services scale with GROSS floor (human mode pays the x1.45
amenity overhead and the hubs) times an occupant factor of 1.5 (roughly a
third of commercial building energy serves occupants - lighting, comfort
HVAC - which a lights-out facility does not spend); transport is
flow-weighted distance.

## Files

- `fetch_pluto.py` - downloads real PLUTO lots (Socrata API; run where the
  network allows, the remote sandbox blocks NYC Open Data)
- `sample_data.py` - schema-matched stand-in lots (zoning FAR caps from the
  Zoning Resolution, lot sizes approximating Manhattan) so the pipeline runs
  end-to-end without the download; drop the real CSV into
  `data/pluto_manhattan.csv` and it is used automatically
- `city_env.py` - the placement environment, both modes
- `optimize.py` - random search / greedy local improvement / simulated
  annealing (numpy-only; the env exposes the interface an RL policy would
  use, so PPO can replace these later)
- `run_comparison.py` - the headline experiment
- `breakeven.py` - the chapter-2 economics

## Run

```bash
pip install numpy pandas matplotlib
python sample_data.py        # or: python fetch_pluto.py
python run_comparison.py     # writes outputs/, prints rho
python breakeven.py          # reads rho, prints payback table
```

## Current result (sample lots, 5 seeds)

| mode | best efficiency | process | services | transport |
|---|---|---|---|---|
| human constraints | 1.38 | 241 | 311 | 172 |
| robot constraints | 2.09 | 241 | 121 | 117 |
| **ratio rho** | **~1.51** | | | |

Where the gap comes from (see `outputs/input_breakdown.png`): process input
is identical by construction; the biggest single win is building services
(-61%: no amenity overhead, no worker hubs, no occupant lighting/HVAC),
then transport (-32%: denser placement once zoning and safety spacing are
gone). Note rho is a lower bound - channels deliberately not counted yet
include 24/7 utilisation (no shifts) and human idle/commute time.

The optimised layouts tell the story: the human city spreads (industry
scattered across M lots, worker hubs pushed to safety distance), the robot
city collapses into a tight stacked cluster until the cooling limit binds -
the bottleneck moves from zoning law to thermodynamics.

Break-even at rho = 1.51: NYC residents need ~$500bn/yr of net product;
capital of ~$0.6-1.6tn (at $75k-300k per job automated) pays back in ~1-3
years of liberated wages. The result is dominated by capital cost
assumptions, not by rho - an honest finding: *whether* to build is an
economics question, *how well* it can run is the optimisation question.

## Honest limitations / next steps

- Sample lots stand in for real PLUTO until the CSV is downloaded; the
  parameters (overhead factor, cooling cap, power density) are order-of-
  magnitude engineering values, not calibrated.
- Optimisers are classical; the planned contribution is an RL policy
  (PPO + GNN over the lot graph) benchmarked against these baselines.
- Single objective (transport efficiency); the multi-objective version
  (output vs waste-heat vs robustness Pareto front) is the thesis extension.
- Break-even is a parameterised back-of-envelope, meant to locate which
  variable dominates (capital cost), not to forecast.
