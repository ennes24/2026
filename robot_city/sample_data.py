"""Generate a PLUTO-schema sample of Manhattan-like tax lots.

The remote sandbox cannot reach NYC Open Data, so this produces a stand-in
file with the same columns fetch_pluto.py would return. Zoning districts and
their floor-area-ratio (FAR) caps come from the NYC Zoning Resolution;
lot-size and built-FAR distributions approximate published PLUTO summary
statistics for Manhattan commercial/manufacturing districts. Swap in the
real CSV (same columns) once downloaded - the rest of the pipeline does not
change.
"""

import numpy as np
import pandas as pd

# District -> max commercial/manufacturing FAR per the NYC Zoning Resolution
# (Articles III-IV base FARs, ignoring bonuses). These caps exist for light,
# air and street-level human comfort - i.e. they are human constraints.
ZONING_FAR = {
    "M1-2": 2.0,
    "M1-5": 5.0,
    "M1-6": 10.0,
    "M2-3": 2.0,
    "M3-1": 2.0,
    "C6-2": 6.0,
    "C6-4": 10.0,
    "C5-3": 15.0,
}
DISTRICT_WEIGHTS = [0.10, 0.20, 0.10, 0.08, 0.05, 0.20, 0.17, 0.10]


def make_lots(n_lots: int = 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    districts = rng.choice(list(ZONING_FAR), size=n_lots, p=DISTRICT_WEIGHTS)
    # Manhattan lots: median ~2,500 sqft, long right tail (assemblages).
    lotarea = np.round(rng.lognormal(mean=np.log(4000), sigma=0.7, size=n_lots))
    far_cap = np.array([ZONING_FAR[d] for d in districts])
    builtfar = np.round(far_cap * rng.uniform(0.3, 0.95, size=n_lots), 2)
    side = int(np.ceil(np.sqrt(n_lots)))
    rows, cols = np.divmod(np.arange(n_lots), side)
    return pd.DataFrame(
        {
            "bbl": 1000000000 + np.arange(n_lots),
            "borough": "MN",
            "block": rows + 1,
            "lot": cols + 1,
            "address": [f"SAMPLE LOT {i}" for i in range(n_lots)],
            "zonedist1": districts,
            "lotarea": lotarea,
            "bldgarea": np.round(lotarea * builtfar),
            "builtfar": builtfar,
            "residfar": 0.0,
            "commfar": far_cap,
            "facilfar": far_cap,
            "numfloors": np.maximum(1, np.round(builtfar * 1.2)),
            "latitude": 40.75 + rows * 0.0008,
            "longitude": -73.99 + cols * 0.0008,
        }
    )


if __name__ == "__main__":
    df = make_lots()
    out = "data/pluto_sample.csv"
    df.to_csv(out, index=False)
    print(f"wrote {len(df)} sample lots to {out}")
    print(df.groupby("zonedist1")["commfar"].agg(["count", "first"]))
