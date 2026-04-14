@echo off
REM ============================================================================
REM bloomberg-sync.bat — wrapper that keeps the Bloomberg pipeline in sync
REM with github.com/schlafen318/openclaw-bloomberg-pipeline before each run.
REM
REM Flow:
REM   1. cd into the git clone
REM   2. git pull (if it fails — network, auth — log and continue)
REM   3. copy .py + .bat files into the live runtime folder, preserving
REM      bbg_tickers.json which is stateful and never in git
REM   4. call the refreshed run_pipeline.bat from the runtime folder
REM
REM Windows Task Scheduler should be pointed at THIS file, not at
REM run_pipeline.bat directly, so every scheduled run gets the latest
REM scripts automatically.
REM
REM Deploy once (manual):
REM   - copy this file to C:\Users\stephanie.leung\bloomberg-sync.bat
REM     (OUTSIDE the git clone — it's the wrapper, not the wrapped thing)
REM   - point Task Scheduler at C:\Users\stephanie.leung\bloomberg-sync.bat
REM   - leave your existing run_pipeline.bat schedule disabled
REM ============================================================================

setlocal

REM --- paths (edit if yours differ) ---
set SRC_DIR=C:\Users\stephanie.leung\bloomberg-pipeline-src
set RUN_DIR=C:\Users\stephanie.leung\bloomberg-pipeline
set LOG_FILE=%RUN_DIR%\sync.log

echo. >> "%LOG_FILE%"
echo ==================================================== >> "%LOG_FILE%"
echo [%date% %time%] bloomberg-sync starting >> "%LOG_FILE%"
echo [bloomberg-sync] Starting...

REM --- 1. Pull latest from git ---
if not exist "%SRC_DIR%\.git" (
    echo ERROR: git clone not found at %SRC_DIR% >> "%LOG_FILE%"
    echo ERROR: git clone not found at %SRC_DIR%
    echo Skipping sync; running pipeline with existing local files. >> "%LOG_FILE%"
    goto :run_pipeline
)

cd /d "%SRC_DIR%"
echo [%date% %time%] git pull in %SRC_DIR% >> "%LOG_FILE%"
echo [bloomberg-sync] Pulling latest from git...
git pull --quiet >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo WARNING: git pull failed ^(network^|auth^|conflict^); continuing with existing files >> "%LOG_FILE%"
    echo WARNING: git pull failed; continuing with existing files
)

REM --- 2. Copy refreshed files into runtime folder ---
echo [%date% %time%] syncing files to %RUN_DIR% >> "%LOG_FILE%"
echo [bloomberg-sync] Syncing files...
copy /Y "%SRC_DIR%\bbg_extract.py"   "%RUN_DIR%\bbg_extract.py"   >> "%LOG_FILE%" 2>&1
copy /Y "%SRC_DIR%\bbg_upload.py"    "%RUN_DIR%\bbg_upload.py"    >> "%LOG_FILE%" 2>&1
copy /Y "%SRC_DIR%\run_pipeline.bat" "%RUN_DIR%\run_pipeline.bat" >> "%LOG_FILE%" 2>&1

REM DELIBERATELY NOT COPIED: bbg_tickers.json (stateful, mutated by
REM merge_data_requests on every run). Never sync from git.

:run_pipeline
REM --- 3. Run the refreshed pipeline ---
echo [%date% %time%] calling run_pipeline.bat >> "%LOG_FILE%"
echo [bloomberg-sync] Running pipeline...
cd /d "%RUN_DIR%"

REM Run pipeline, capture output to temp file, show on screen AND log
set TEMP_OUT=%TEMP%\pipeline_out_%RANDOM%.txt
call run_pipeline.bat > "%TEMP_OUT%" 2>&1
set EXIT_CODE=%errorlevel%

REM Show output on screen
type "%TEMP_OUT%"
REM Append to log
type "%TEMP_OUT%" >> "%LOG_FILE%"
del "%TEMP_OUT%" 2>nul

echo [%date% %time%] pipeline exited with code %EXIT_CODE% >> "%LOG_FILE%"

if %EXIT_CODE% neq 0 (
    echo.
    echo ERROR: Pipeline failed with exit code %EXIT_CODE%
    echo See %LOG_FILE% for details.
) else (
    echo [bloomberg-sync] Done.
)

endlocal & exit /b %EXIT_CODE%
