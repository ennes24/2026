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
| worker housing | sized from workforce x 600 sqft/person, >= 2 cells from industry | none |
| amenity overhead | x1.45 gross/net floor | x1.0 |
| capacity utilisation | 75% (shifts, breaks, holidays) | 95% (lights-out 24/7) |
| upkeep | - | +10% of process input (spares, compute) |
| interaction | face-to-face, decays over ~3 cells | network-speed, distance-free |
| binding limit | zoning | cooling: <= 12 MW per 3x3 block |

Same production chain, same objective in both:
`efficiency = output / (process + services + maintenance + transport)`.
Process input is identical in both modes (the machines do the same work).
Utilisation grosses up the floor that must physically exist (x1.33 human,
x1.05 robot), which propagates into services, land take and feasibility.
Services scale with gross physical floor times an occupant factor of 1.5 in
human mode (roughly a third of commercial building energy serves occupants -
lighting, comfort HVAC - which a lights-out facility does not spend).
Worker housing is derived from the implied workforce, not a token constant.
Maintenance is a robot-only penalty so the comparison cuts both ways.
Transport is flow-weighted distance; human mode adds commute flows.

Output is not fixed: it carries an agglomeration bonus of up to +80%,
because interaction - not floor space - is what makes cities productive
(Bettencourt/West superlinear scaling). Human interaction is face-to-face
and decays over a few blocks (gravity form, exp(-d/3)), so the human city
*wants* the density its own zoning and safety rules deny it. Robot
interaction runs at network speed with fleet learning, so robots collect
the full bonus at any layout. This is the model's answer to the question
"can robots interacting like humans out-produce the human city, not just
run cheaper?"

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

| mode | output | interaction | efficiency | process | services | maint. | transport |
|---|---|---|---|---|---|---|---|
| human constraints | 1320 | 0.40 | 1.22 | 241 | 612 | 0 | 232 |
| robot constraints | 1800 | 1.00 | 3.54 | 241 | 127 | 24 | 117 |
| **output ratio** | **1.36** | | **rho ~2.9** | | | | |

Two headline numbers now, answering two different questions:

- **Output ratio 1.36** - can robots *out-produce* the human city, not
  just run cheaper? Yes: even optimised, the human city only realises
  interaction 0.40 of 1.00, because zoning, safety spacing and its
  housing ring keep production nodes apart; robots collect the full
  agglomeration bonus regardless of layout.
- **Efficiency ratio ~2.9** - per unit of resource, the robot city
  produces ~3x. Services dominate the input gap (-79%): the human city
  builds 33% more floor for the same effective output (shift
  utilisation), grosses it up 45% for amenities, houses its workforce on
  top, and lights/heats it all for occupants. The human city is carrying
  an entire support city on its back; that burden, not the factory
  itself, is what a robot city deletes.

The optimised layouts tell the story: the human city pushes large worker-
housing hubs to the safety perimeter (a dormitory-suburb ring, emerging
from the optimiser rather than assumed), while the robot city collapses
into a few stacked clusters until the cooling limit binds - the bottleneck
moves from zoning law to thermodynamics.

Break-even at rho ~2.9: NYC residents need ~$500bn/yr of net product;
capital of ~$0.6-1.6tn (at $75k-300k per job automated) pays back in ~1-3
years of liberated wages. The result is dominated by capital cost
assumptions, not by rho - an honest finding: *whether* to build is an
economics question, *how well* it can run is the optimisation question.

## Honest limitations / next steps

- Sample lots stand in for real PLUTO until the CSV is downloaded; the
  parameters (overhead factor, utilisation rates, floor-per-worker, cooling
  cap, power density, maintenance fraction) are order-of-magnitude
  engineering values with cited anchors, not calibrated fits - read the
  ratios as "roughly 1.4x output, roughly 3x per resource", not as
  precise values. The distance-free robot interaction (=1.0) is the most
  optimistic assumption in the model; coordination overhead between robot
  fleets would pull it below 1 and is worth a sensitivity sweep.
- Optimisers are classical; the planned contribution is an RL policy
  (PPO + GNN over the lot graph) benchmarked against these baselines.
- Single objective (transport efficiency); the multi-objective version
  (output vs waste-heat vs robustness Pareto front) is the thesis extension.
- Break-even is a parameterised back-of-envelope, meant to locate which
  variable dominates (capital cost), not to forecast.
