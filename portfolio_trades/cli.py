"""
Command-line interface for PortfolioAnalytics2 trade generation.

Workflow:
  1) Load holdings and portfolio-wide target mix
  2) Compute trades per account (no inter-account transfers)
  3) Write CSV, holdings-after, and PDF summaries
"""

import argparse
from pathlib import Path

from .io_utils import (
    load_holdings,
    load_targets,
    ensure_outdir,
    write_csv,
    write_holdings,
    today_str,
)
from .engine import build_trades_and_afterholdings
from .report_pdf import render_pdf
from .conventions import DEFAULT_CASH_TOL


def main():
    parser = argparse.ArgumentParser(
        description="Generate per-account trade lists to reach the portfolio-wide target mix"
    )
    parser.add_argument(
        "--vol",
        type=float,
        default=0.08,
        help="Target volatility (e.g. 0.08 = 8%%)",  # NOTE: '%%' escapes percent for argparse
    )
    parser.add_argument(
        "--cash-tol",
        type=float,
        default=DEFAULT_CASH_TOL,
        help="Per-account cash tolerance in $",
    )
    parser.add_argument(
        "--holdings",
        type=str,
        default="data/holdings.csv",   # default to data/ subdir; loader also searches other spots
        help="Path to holdings CSV (default: data/holdings.csv)",
    )
    args = parser.parse_args()

    vol_pct_tag = int(round(args.vol * 100))
    print(f"Target volatility: {vol_pct_tag}%")

    # === Load data ===
    h = load_holdings(args.holdings)
    W = load_targets(vol_pct_tag)

    # === Core computation ===
    tx, after, residuals = build_trades_and_afterholdings(
        h, W, cash_tolerance=args.cash_tol
    )

    # === Outputs ===
    outdir = ensure_outdir()
    date = today_str()
    base = Path.cwd().name  # project folder name as prefix

    csv_out = outdir / f"{base}_Trades_{date}.csv"
    write_csv(
        tx.rename(columns={"Delta_Dollars": "Delta_$", "CapGain_Dollars": "CapGain_$"}),
        csv_out,
    )
    print(f"CSV written: {csv_out}")

    hold_after_out = outdir / f"holdings_aftertrades_{date}.csv"
    write_holdings(after, hold_after_out)
    print(f"Holdings-after written: {hold_after_out}")

    # === Cash residuals ===
    for acct, amt in residuals.items():
        sign = "-" if amt < 0 else ""
        print(f"[WARN] Residual cash flow in '{acct}': {sign}${abs(amt):,.2f}")

    # === PDF ===
    if not tx.empty:
        tx = tx.copy()
        tx["Buy_$"] = tx["Delta_Dollars"].where(tx["Action"] == "BUY", 0.0)
        tx["Sell_$"] = (-tx["Delta_Dollars"]).where(tx["Action"] == "SELL", 0.0)

        # Per-account summary
        acc_sum = (
            tx.groupby(["Account", "TaxStatus"], as_index=False)
            .agg(
                Total_Buys=("Buy_$", "sum"),
                Total_Sells=("Sell_$", "sum"),
                Net_CapGain=("CapGain_Dollars", "sum"),
            )
        )

        # Estimated tax by account
        def _est_tax(row):
            if row["TaxStatus"] in ("HSA", "ROTH IRA"):
                return 0.0
            if row["TaxStatus"] == "Trust":
                return row["Net_CapGain"] * 0.20
            return row["Net_CapGain"] * 0.15

        acc_sum["Est_Tax"] = acc_sum.apply(_est_tax, axis=1)

        # Summary by tax status
        by_status = (
            tx.groupby("TaxStatus", as_index=False)
            .agg(
                Total_Buys=("Buy_$", "sum"),
                Total_Sells=("Sell_$", "sum"),
                Net_CapGain=("CapGain_Dollars", "sum"),
            )
        )
        by_status["Est_Tax"] = by_status.apply(_est_tax, axis=1)

        pdf_out = outdir / f"{base}_{vol_pct_tag}vol_{date}.pdf"
        render_pdf(tx, acc_sum, by_status, vol_pct_tag, str(pdf_out))
        print(f"PDF written: {pdf_out}")
    else:
        print("No trades; PDF skipped.")


if __name__ == "__main__":
    main()