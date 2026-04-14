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

### One-time setup

1. **Clone this repo** somewhere stable:
   ```
   cd C:\Users\stephanie.leung
   git clone https://github.com/schlafen318/openclaw-bloomberg-pipeline.git bloomberg-pipeline-src
   ```
   If this is a private repo, git-for-windows will prompt for a
   personal access token the first time. Git Credential Manager caches
   it so future pulls are silent.

2. **Copy the wrapper out of the git clone**:
   ```
   copy bloomberg-pipeline-src\bloomberg-sync.bat  bloomberg-sync.bat
   ```
   The wrapper lives at `C:\Users\stephanie.leung\bloomberg-sync.bat`,
   **outside** the git clone. This is deliberate — it's the thing that
   git-pulls the rest, so it can't be in the thing it pulls (risk of
   the file getting overwritten mid-execution).

3. **First-run bootstrap**: copy the runtime files into place for the
   first time. The wrapper will keep them in sync from now on:
   ```
   cd bloomberg-pipeline-src
   copy /Y bbg_extract.py   ..\bloomberg-pipeline\bbg_extract.py
   copy /Y bbg_upload.py    ..\bloomberg-pipeline\bbg_upload.py
   copy /Y run_pipeline.bat ..\bloomberg-pipeline\run_pipeline.bat
   ```
   **Never copy `bbg_tickers.json`** — it stays local and stateful, and
   it's already in `.gitignore` so git can't touch it anyway.

4. **Re-point Windows Task Scheduler**: your existing trigger probably
   runs `bloomberg-pipeline\run_pipeline.bat` at 06:00 HKT. Edit the
   trigger so it runs `C:\Users\stephanie.leung\bloomberg-sync.bat`
   instead. Leave the schedule (06:00 HKT daily) unchanged.

### How updates work after setup

Any push to this repo's `main` branch automatically rolls out to Windows
on the next scheduled 06:00 HKT run:

```
[Mac]   git push origin main
[06:00] Windows scheduler fires bloomberg-sync.bat
        → git pull (fast-forwards to new HEAD)
        → copies .py and .bat files into bloomberg-pipeline\
        → calls run_pipeline.bat
        → bbg_extract.py runs with new code, pulls data, uploads
```

No manual action on the Windows machine unless:
- The git clone breaks (auth expiry, disk issue)
- You want to roll out a fix *before* the next 06:00 run (manually
  double-click `bloomberg-sync.bat`)
- You edit `bbg_tickers.json` by hand for the hand-curated `macro`
  section

### Sync logs

`bloomberg-sync.bat` appends to `C:\Users\stephanie.leung\bloomberg-pipeline\sync.log`
with timestamps, git pull output, copy results, and the pipeline exit
code. Check this file if a run looks weird. Rotate it manually if it
ever gets large (probably years from now — each run is ~10 lines).

## Deployment on Windows (manual updates)

**Only needed if you want to roll out a fix before the next 06:00 run.**

From any shell on Windows:
```
bloomberg-sync.bat
```

That's it. Same logic runs interactively.

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
