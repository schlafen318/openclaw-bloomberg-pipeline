#!/usr/bin/env python3
"""
bbg_extract.py — Extract all Bloomberg data in one run.
Pulls fundamentals, estimates, valuation, and market data.
Saves CSVs to staging/ folder.

Usage:
    python bbg_extract.py           # Full extraction
    python bbg_extract.py --quick   # Market data + estimates only (faster)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "bbg_tickers.json"
STAGING_DIR = SCRIPT_DIR / "staging"
TODAY = datetime.now().strftime("%Y-%m-%d")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def get_all_tickers(config):
    tickers = []
    for group in ["portfolio", "watchlist", "macro"]:
        tickers += [t["bbg_ticker"] for t in config.get(group, [])]
    return tickers

def get_equity_tickers(config):
    """Portfolio + watchlist only (skip macro for fundamentals)."""
    tickers = []
    for group in ["portfolio", "watchlist"]:
        tickers += [t["bbg_ticker"] for t in config.get(group, [])]
    return tickers

def save_csv(df, name):
    out_dir = STAGING_DIR / TODAY
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.csv"
    df.to_csv(path)
    print(f"  Saved {path}")

def batch_bdp(tickers, fields, batch_size=20, **kwargs):
    """Fetch reference data in batches to avoid timeouts."""
    from xbbg import blp
    results = []
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        try:
            df = blp.bdp(batch, fields, **kwargs)
            results.append(df)
            print(f"  Batch {i//batch_size+1}: {len(batch)} tickers OK")
        except Exception as e:
            print(f"  Batch {i//batch_size+1} ERROR: {e}")
    return pd.concat(results) if results else pd.DataFrame()


# --- EXTRACTION FUNCTIONS ---

def extract_market_data(config):
    """Current prices, returns, volatility, short interest."""
    print("\n📊 Extracting market data...")
    tickers = get_all_tickers(config)
    
    fields = [
        "PX_LAST", "CHG_PCT_1D", "CHG_PCT_5D", "CHG_PCT_1M",
        "CHG_PCT_3M", "CHG_PCT_6M", "CHG_PCT_YTD", "CHG_PCT_1YR",
        "HIGH_52WEEK", "LOW_52WEEK",
        "VOLUME_AVG_30D", "PX_VOLUME",
        "VOLATILITY_30D", "VOLATILITY_90D",
        "SHORT_INT_RATIO", "SI_PERCENT_OF_FLOAT",
    ]
    
    df = batch_bdp(tickers, fields)
    if not df.empty:
        save_csv(df, "market_data")
    return df


def extract_fundamentals(config):
    """Revenue, earnings, margins, returns, cash flow."""
    print("\n📈 Extracting fundamentals...")
    tickers = get_equity_tickers(config)
    
    fields = [
        "NAME", "GICS_SECTOR_NAME", "CNTRY_OF_DOMICILE",
        "CUR_MKT_CAP", "TRAIL_12M_SALES", "TRAIL_12M_EPS",
        "GROSS_MARGIN", "OPER_MARGIN", "PROF_MARGIN", "EBITDA_MARGIN",
        "RETURN_ON_INV_CAPITAL", "RETURN_COM_EQY",
        "TOT_DEBT_TO_TOT_EQY", "NET_DEBT_TO_EBITDA", "CUR_RATIO",
        "CF_FREE_CASH_FLOW", "FREE_CASH_FLOW_YIELD",
        "EQY_DVD_YLD_IND",
    ]
    
    df = batch_bdp(tickers, fields)
    if not df.empty:
        save_csv(df, "fundamentals")
    return df


def extract_estimates(config):
    """Consensus estimates: EPS, revenue, target prices."""
    print("\n🎯 Extracting estimates...")
    tickers = get_equity_tickers(config)
    
    all_estimates = []
    for label, period in [("FY1", "1BF"), ("FY2", "2BF")]:
        fields = [
            "BEST_EPS", "BEST_EPS_HIGH", "BEST_EPS_LOW", "BEST_EPS_NUM_EST",
            "BEST_SALES", "BEST_SALES_NUM_EST",
            "BEST_EBITDA",
        ]
        df = batch_bdp(tickers, fields, BEST_FPERIOD_OVERRIDE=period)
        if not df.empty:
            df["period"] = label
            all_estimates.append(df)
            save_csv(df, f"estimates_{label}")
    
    # Revisions + target prices (NTM 12M forward for EPS/Sales revisions)
    rev_ntm_fields = [
        "BEST_EPS_1MO_CHG", "BEST_EPS_3MO_CHG",
        "BEST_SALES_1MO_CHG", "BEST_SALES_3MO_CHG",
    ]
    rev_static_fields = [
        "BEST_TARGET_PRICE", "BEST_TARGET_PRICE_HIGH", "BEST_TARGET_PRICE_LOW",
        "TOT_BUY_REC", "TOT_HOLD_REC", "TOT_SELL_REC",
        "BEST_ANALYST_RATING",
    ]
    print("  Fetching NTM estimate revisions...")
    df_rev_ntm = batch_bdp(tickers, rev_ntm_fields, BEST_FPERIOD_OVERRIDE="12M")
    df_rev_static = batch_bdp(tickers, rev_static_fields)
    
    if not df_rev_ntm.empty and not df_rev_static.empty:
        df_rev = df_rev_static.join(df_rev_ntm, how="outer")
    elif not df_rev_static.empty:
        df_rev = df_rev_static
    elif not df_rev_ntm.empty:
        df_rev = df_rev_ntm
    else:
        df_rev = pd.DataFrame()
    
    if not df_rev.empty:
        save_csv(df_rev, "estimates_revisions")
    
    return all_estimates


def extract_valuation(config):
    """Current and historical valuation multiples."""
    print("\n💰 Extracting valuation...")
    tickers = get_equity_tickers(config)
    
    # Static valuation fields (no period override needed)
    static_fields = [
        "PE_RATIO",
        "PX_TO_BOOK_RATIO", "PX_TO_SALES_RATIO", "PX_TO_FREE_CASH_FLOW",
        "EV_TO_T12M_EBITDA", "EV_TO_T12M_SALES", "ENTERPRISE_VALUE",
        "EARN_YLD", "WACC",
    ]
    
    df_static = batch_bdp(tickers, static_fields)
    
    # NTM (next twelve months) forward fields — requires BEST_FPERIOD_OVERRIDE=12M
    ntm_fields = [
        "BEST_PE_RATIO", "BEST_PEG_RATIO",
        "BEST_EV_TO_BEST_EBITDA",
    ]
    
    print("  Fetching NTM (12M forward) estimates...")
    df_ntm = batch_bdp(tickers, ntm_fields, BEST_FPERIOD_OVERRIDE="12M")
    
    # Merge static + NTM
    if not df_static.empty and not df_ntm.empty:
        df = df_static.join(df_ntm, how="outer")
    elif not df_static.empty:
        df = df_static
    elif not df_ntm.empty:
        df = df_ntm
    else:
        df = pd.DataFrame()
    
    if not df.empty:
        save_csv(df, "valuation")
    return df


def extract_credit(config):
    """Credit market data for risk monitoring."""
    print("\n🏦 Extracting credit data...")
    credit_tickers = [t["bbg_ticker"] for t in config.get("macro", [])
                      if t["ticker"] in ("BKLN", "HYG", "TLT", "VIX", "DXY", "GC1", "HG1")]
    
    fields = ["PX_LAST", "CHG_PCT_1D", "CHG_PCT_1M", "CHG_PCT_3M",
              "MOV_AVG_50D", "MOV_AVG_200D"]
    
    df = batch_bdp(credit_tickers, fields)
    if not df.empty:
        save_csv(df, "credit_macro")
    return df


# --- MAIN ---

def merge_data_requests(config):
    """Check for pending data requests and merge add/remove into config.

    Handles two request kinds:
      - ``pending_tickers``: append to ``watchlist`` if not already in
        ``portfolio`` / ``watchlist`` / ``macro``
      - ``pending_removals``: remove from ``portfolio`` or ``watchlist``
        if present. ``macro`` is NEVER auto-pruned — macro tickers are
        hand-curated and the Mac-side sync script protects them via
        ``PRUNE_PROTECTED_TICKERS``, so any removal against a macro row
        would be a bug.

    Both kinds move to ``fulfilled`` on success, with an ``action``
    field so the history log is auditable (``added`` vs ``removed``).
    """
    requests_path = SCRIPT_DIR / "data_requests.json"
    # Also check Drive-synced location
    drive_requests = Path(r"H:\My Drive\Steph-PA\notes\personal-portfolio\bloomberg\data_requests.json")

    req_file = None
    for p in [requests_path, drive_requests]:
        if p.exists():
            req_file = p
            break

    if not req_file:
        return config

    try:
        with open(req_file, encoding="utf-8") as f:
            requests = json.load(f)
    except Exception:
        return config

    pending = requests.get("pending_tickers", []) or []
    pending_removals = requests.get("pending_removals", []) or []
    fulfilled = requests.get("fulfilled", []) or []

    if not pending and not pending_removals:
        return config

    # Build the existing ticker set once for add decisions
    existing = set()
    for group in ["portfolio", "watchlist", "macro"]:
        for t in config.get(group, []):
            existing.add(t.get("bbg_ticker"))

    # --- Process ADDS ------------------------------------------------
    added = []
    for req in pending:
        bbg_t = req.get("ticker")
        if bbg_t and bbg_t not in existing:
            yf_ticker = (
                bbg_t.replace(" US Equity", "")
                .replace(" HK Equity", ".HK")
                .replace(" KS Equity", ".KS")
                .replace(" TT Equity", ".TW")
                .replace(" FP Equity", ".PA")
                .replace(" JT Equity", ".T")
                .replace(" IM Equity", ".MI")
                .replace(" LN Equity", ".L")
                .replace(" GY Equity", ".DE")
            )
            config.setdefault("watchlist", []).append({
                "ticker": yf_ticker,
                "bbg_ticker": bbg_t,
            })
            existing.add(bbg_t)
            added.append(bbg_t)
            fulfilled.append({**req, "fulfilled_at": TODAY, "action": "added"})

    # --- Process REMOVALS --------------------------------------------
    # Only touch portfolio + watchlist. Macro is hand-curated.
    removed = []
    if pending_removals:
        removal_set = {r.get("ticker") for r in pending_removals if r.get("ticker")}
        for group in ["portfolio", "watchlist"]:
            before = config.get(group, []) or []
            after = [t for t in before if t.get("bbg_ticker") not in removal_set]
            # Record which ones actually got removed (present → absent)
            dropped = [t.get("bbg_ticker") for t in before if t.get("bbg_ticker") in removal_set]
            removed.extend(dropped)
            config[group] = after
        # Move every removal request to fulfilled. Even requests whose
        # ticker wasn't found in the config get logged (they were either
        # already removed or were never there) so the queue drains.
        for req in pending_removals:
            fulfilled.append({**req, "fulfilled_at": TODAY, "action": "removed"})

    # --- Write back --------------------------------------------------
    touched = bool(added or removed or pending_removals)
    if added:
        print(f"  📥 Added {len(added)} tickers from data requests: {added}")
    if removed:
        print(f"  🗑  Removed {len(removed)} tickers from extraction: {removed}")

    if touched:
        # Drain both pending lists — leave only the requests whose
        # ticker wasn't in the add set AND wasn't in the removal set.
        added_set = set(added)
        requests["pending_tickers"] = [r for r in pending if r.get("ticker") not in added_set]
        requests["pending_removals"] = []  # everything processed
        requests["fulfilled"] = fulfilled
        with open(req_file, "w", encoding="utf-8") as f:
            json.dump(requests, f, indent=2)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Market data + estimates only")
    args = parser.parse_args()

    config = load_config()
    config = merge_data_requests(config)
    print(f"Bloomberg Data Extraction — {TODAY}")
    print(f"Portfolio: {len(config['portfolio'])} tickers")
    print(f"Watchlist: {len(config.get('watchlist', []))} tickers")
    print(f"Macro: {len(config.get('macro', []))} tickers")
    print(f"Output: {STAGING_DIR / TODAY}")

    extract_market_data(config)
    extract_estimates(config)
    extract_credit(config)

    if not args.quick:
        extract_fundamentals(config)
        extract_valuation(config)
    
    print(f"\n✅ Done! Files saved to {STAGING_DIR / TODAY}")
    print(f"Next step: python bbg_upload.py")


if __name__ == "__main__":
    main()
