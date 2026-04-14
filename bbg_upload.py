#!/usr/bin/env python3
"""
bbg_upload.py — Upload Bloomberg staging data to Google Drive.
Uses rclone or simple HTTP upload via Google Drive API.

Copies CSVs directly to Google Drive via Drive for Desktop sync.

Usage:
    python bbg_upload.py
"""

import os
import shutil
from datetime import datetime
from pathlib import Path

STAGING_DIR = Path(__file__).parent / "staging"
DRIVE_DIR = Path(r"H:\My Drive\Steph-PA\notes\personal-portfolio\bloomberg")
TODAY = datetime.now().strftime("%Y-%m-%d")

def main():
    today_dir = STAGING_DIR / TODAY
    if not today_dir.exists():
        print(f"No data for {TODAY}. Run bbg_extract.py first.")
        return

    # Create target dir on Drive
    drive_today = DRIVE_DIR / TODAY
    drive_today.mkdir(parents=True, exist_ok=True)

    # Copy all CSVs to Drive
    files = list(today_dir.glob("*.csv"))
    for f in files:
        dest = drive_today / f.name
        shutil.copy2(f, dest)
        print(f"  -> {dest}")

    total_size = sum(f.stat().st_size for f in files)
    print(f"\n{len(files)} CSV files ({total_size/1024:.0f} KB) saved to {drive_today}")
    print("Google Drive will sync automatically.")


if __name__ == "__main__":
    main()
