# openclaw-bloomberg-pipeline

Windows-side scripts for the OpenClaw Bloomberg extraction pipeline.

These files live on **Steph's Bloomberg laptop** (Windows) and pull daily
fundamentals / estimates / valuation / market data from Bloomberg via
`xbbg` + `blpapi`, then upload to Google Drive for the Mac side to consume.

The Mac-side companion lives in the `openclaw` monorepo under
`inv-team/scripts/ops/bbg_ticker_sync.py` and
`inv-team/scripts/ops/bbg_daily_check.py`.

## Why this repo exists

Previously, the Windows scripts were embedded as string templates inside
`bbg_setup.py` and generated into `C:\Users\stephanie.leung\bloomberg-pipeline\`
once at install time. That created a **drift problem**: edits to the
templates on Mac never made it to Windows unless the destructive
"re-run setup" step was invoked (which clobbers `bbg_tickers.json`).

This repo makes the Windows scripts **version-controlled, git-synced,
and single-source-of-truth**.

## Files

| File | Purpose |
|---|---|
| `bbg_extract.py` | Pulls market_data, fundamentals, estimates, valuation, credit_macro from Bloomberg via xbbg. Calls `merge_data_requests()` to drain pending adds/removes from `data_requests.json` on each run. |
| `bbg_upload.py` | Moves staging CSVs from `C:\Users\stephanie.leung\bloomberg-pipeline\staging\YYYY-MM-DD\` to the Drive-synced folder `H:\My Drive\Steph-PA\notes\personal-portfolio\bloomberg\YYYY-MM-DD\`. |
| `run_pipeline.bat` | One-shot batch file that runs extract → upload. Wired to Windows Task Scheduler for 06:00 HKT daily execution. |
| `bbg_tickers.json` | Ticker config the extract script reads. NOT in this repo — stays on the Windows laptop, managed by `merge_data_requests` via `data_requests.json` on Drive. |

## Data flow

```
[Mac] ticker_registry.json + securities.json
   ↓ bbg_ticker_sync.py (04:30 HKT daily, LaunchAgent)
[Drive] data_requests.json  ← pending_tickers, pending_removals
   ↓ bbg_extract.py reads this
[Windows] bbg_tickers.json ← drained & updated
   ↓ xbbg pulls from Bloomberg Terminal
[Windows] staging/YYYY-MM-DD/*.csv
   ↓ bbg_upload.py
[Drive] bloomberg/YYYY-MM-DD/*.csv
   ↓ bbg_reader.sync_latest_from_drive()
[Mac] data/bloomberg/YYYY-MM-DD/*.csv
   ↓ read by portfolio_view, research, risk scripts
```

## Deployment on Windows (first time)

1. Clone this repo somewhere stable, e.g. `C:\Users\stephanie.leung\bloomberg-pipeline-src\`
2. Copy `bbg_extract.py`, `bbg_upload.py`, `run_pipeline.bat` into
   `C:\Users\stephanie.leung\bloomberg-pipeline\` (next to your existing
   `bbg_tickers.json` — **do NOT overwrite that file**)
3. Schedule `run_pipeline.bat` in Windows Task Scheduler to run at 06:00
   HKT daily (or 22:00 UTC, depending on your timezone setting)

## Deployment on Windows (updates)

When new versions of any file land in this repo:

```
cd C:\Users\stephanie.leung\bloomberg-pipeline-src
git pull
copy bbg_extract.py ..\bloomberg-pipeline\bbg_extract.py
copy bbg_upload.py ..\bloomberg-pipeline\bbg_upload.py
copy run_pipeline.bat ..\bloomberg-pipeline\run_pipeline.bat
```

**Never overwrite `bbg_tickers.json`** — that file is stateful and gets
mutated by `merge_data_requests()` on every run.

## Prerequisites on the Windows laptop

- Python 3.11+
- `blpapi` + `xbbg` (Bloomberg Python SDK + wrapper)
- `pandas`
- A logged-in Bloomberg Terminal session (xbbg connects via the local `bbcomm.exe`)
- Google Drive for Desktop mounted at `H:\` with Steph-PA visible
- `bbg_tickers.json` already present in `C:\Users\stephanie.leung\bloomberg-pipeline\`

## Sync model

- **Tickers to extract** — driven by `bbg_ticker_sync.py` on Mac, communicated
  via `data_requests.json` on Drive. You do NOT edit `bbg_tickers.json`
  directly on Windows except for the hand-curated `macro` section.
- **Macro/FX/credit tickers** — hand-curated inside `bbg_tickers.json` on
  Windows (the `macro` array). Not managed by the Mac sync.
- **Field definitions** — baked into `bbg_extract.py`. Any changes go
  through this git repo.

## Known gotchas

- **`data_requests.json` on Drive is delete-then-upload** from Mac, so the
  Drive file ID changes on every push. That's fine — the Windows code
  reads by path (`H:\My Drive\…\data_requests.json`), not by ID.
- **Windows DST vs HKT**: Windows Task Scheduler triggers are local-time.
  Make sure the trigger is set to the right local time for 06:00 HKT
  equivalent on whatever timezone the laptop is in.
- **Bloomberg Terminal must be unlocked** for `blpapi` to connect.
  xbbg silently returns empty DataFrames if the terminal is locked.
