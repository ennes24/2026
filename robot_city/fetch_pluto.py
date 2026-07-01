"""Fetch real NYC PLUTO tax-lot data from the Socrata Open Data API.

Run this on a machine with open network access (the remote sandbox blocks
data.cityofnewyork.us). Output: data/pluto_manhattan.csv with the fields the
environment needs. No API token is required for moderate volumes; pass one
via --token to raise rate limits.

Source: NYC Open Data, "Primary Land Use Tax Lot Output (PLUTO)", dataset id
64uk-42ks, maintained by the NYC Department of City Planning.
"""

import argparse
import csv
import io
import sys
import time
import urllib.parse
import urllib.request

API = "https://data.cityofnewyork.us/resource/64uk-42ks.csv"

FIELDS = [
    "bbl", "borough", "block", "lot", "address",
    "zonedist1", "lotarea", "bldgarea", "builtfar",
    "residfar", "commfar", "facilfar",
    "numfloors", "latitude", "longitude",
]


def fetch(borough: str, limit: int, token: str | None) -> str:
    params = {
        "$select": ",".join(FIELDS),
        "$where": f"borough='{borough}' AND lotarea > 0",
        "$limit": str(limit),
        "$order": "bbl",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    if token:
        req.add_header("X-App-Token", token)
    for attempt, delay in enumerate((0, 2, 4, 8, 16)):
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - retry then surface
            print(f"attempt {attempt + 1} failed: {exc}", file=sys.stderr)
    raise SystemExit("all fetch attempts failed; check network access")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--borough", default="MN", help="MN/BX/BK/QN/SI")
    ap.add_argument("--limit", type=int, default=50000)
    ap.add_argument("--token", default=None, help="Socrata app token")
    ap.add_argument("--out", default="data/pluto_manhattan.csv")
    args = ap.parse_args()

    text = fetch(args.borough, args.limit, args.token)
    rows = list(csv.reader(io.StringIO(text)))
    with open(args.out, "w", newline="") as fh:
        csv.writer(fh).writerows(rows)
    print(f"wrote {len(rows) - 1} lots to {args.out}")


if __name__ == "__main__":
    main()
