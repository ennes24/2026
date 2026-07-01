"""Chapter-2 question: would anyone actually build this?

Back-of-envelope, fully parameterised. Takes the efficiency ratio rho from
the placement experiment and asks: if a robot city must produce enough for
every NYC resident to live without working, what does it cost to build,
what does it cost to run, and how fast does the investment pay back?

Default figures (override via CLI):
- population 8.26M: US Census Bureau estimate for NYC, 2023
- per-capita consumption $60k/yr: BEA US personal consumption expenditure
  per capita (~$58k, 2023), rounded up for NYC prices
- jobs replaced 4.7M: BLS payroll employment in NYC
- capital per job $150k: IFR average industrial robot price (~$25k) plus
  integration/peripherals multiplier, service automation skew
- human-city conversion efficiency 2.0: gross output per dollar of
  intermediate input (BEA input-output tables, economy-wide input share
  roughly one half)
"""

import argparse
import os


def analyse(pop, consump, jobs, cap_per_job, infra_bn, eff_human, rho):
    needed_net = pop * consump                    # $/yr residents must receive
    eff_robot = eff_human * rho                   # output per $ of input
    # gross output G such that G - G/eff_robot = needed_net
    gross = needed_net / (1 - 1 / eff_robot)
    operating = gross / eff_robot
    capital = jobs * cap_per_job + infra_bn * 1e9
    payback = capital / needed_net                # years of liberated wages
    return {
        "needed_net_$bn": needed_net / 1e9,
        "gross_output_$bn": gross / 1e9,
        "operating_$bn_yr": operating / 1e9,
        "capital_$bn": capital / 1e9,
        "payback_years": payback,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pop", type=float, default=8.26e6)
    ap.add_argument("--consumption", type=float, default=60000.0)
    ap.add_argument("--jobs", type=float, default=4.7e6)
    ap.add_argument("--infra-bn", type=float, default=200.0,
                    help="fixed construction cost, $bn (Hudson Yards ~$25bn"
                         " for 28 acres; a city is orders more)")
    ap.add_argument("--eff-human", type=float, default=2.0)
    ap.add_argument("--rho", type=float, default=None,
                    help="efficiency ratio; default reads the experiment")
    args = ap.parse_args()

    rho = args.rho
    if rho is None:
        path = "outputs/efficiency_ratio.txt"
        rho = float(open(path).read()) if os.path.exists(path) else 1.3
        print(f"rho = {rho:.3f} ({'from experiment' if os.path.exists(path) else 'default'})")

    print(f"\n{'cap/job':>10} {'capital $bn':>12} {'operating $bn/yr':>17} "
          f"{'payback yrs':>12}")
    for cap in (75e3, 150e3, 300e3):
        r = analyse(args.pop, args.consumption, args.jobs, cap,
                    args.infra_bn, args.eff_human, rho)
        print(f"{cap / 1e3:>9.0f}k {r['capital_$bn']:>12.0f} "
              f"{r['operating_$bn_yr']:>17.0f} {r['payback_years']:>12.1f}")

    r = analyse(args.pop, args.consumption, args.jobs, 150e3,
                args.infra_bn, args.eff_human, rho)
    print(f"\nresidents' required net product : ${r['needed_net_$bn']:.0f}bn/yr")
    print(f"gross output the city must make : ${r['gross_output_$bn']:.0f}bn/yr")
    print(f"NYC gross city product today is roughly $1,200bn/yr for scale.")
    print("\nreading: payback under ~20 years at plausible capital costs is")
    print("the regime where question 1 ('would power invest?') turns yes;")
    print("rho enters through operating cost, capital dominates payback.")


if __name__ == "__main__":
    main()
