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

REM --- 0. Reconnect WiFi and wait for network (handles wake-from-sleep) ---
echo [%date% %time%] reconnecting WiFi >> "%LOG_FILE%"
netsh wlan connect name="WeWork" >> "%LOG_FILE%" 2>&1
set NET_RETRIES=0
:wait_net
ping -n 1 8.8.8.8 >nul 2>&1
if %errorlevel%==0 goto :net_ok
set /a NET_RETRIES+=1
if %NET_RETRIES% geq 24 (
    echo ERROR: no network after 2 minutes >> "%LOG_FILE%"
    echo ERROR: no network after 2 minutes
    endlocal & exit /b 1
)
timeout /t 5 /nobreak >nul
goto :wait_net
:net_ok
echo [%date% %time%] network ready ^(after %NET_RETRIES% retries^) >> "%LOG_FILE%"

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
set GIT_EXIT=%errorlevel%
if %GIT_EXIT% neq 0 (
    echo WARNING: git pull failed ^(network^|auth^|conflict^); continuing with existing files >> "%LOG_FILE%"
    echo WARNING: git pull failed; continuing with existing files
)

REM Record the current HEAD sha and last-sync timestamp to a status
REM file that gets uploaded to Drive alongside the BBG extraction.
REM The Mac-side bbg_daily_check.py reads this file and alerts loudly
REM if the sync has been broken for >2 days.
for /f "delims=" %%s in ('git -C "%SRC_DIR%" rev-parse --short HEAD 2^>nul') do set GIT_HEAD=%%s
if "%GIT_HEAD%"=="" set GIT_HEAD=unknown
set STATUS_FILE=%RUN_DIR%\sync_status.json
> "%STATUS_FILE%" echo {
>> "%STATUS_FILE%" echo   "last_sync_utc": "%date:~10,4%-%date:~4,2%-%date:~7,2%T%time:~0,2%:%time:~3,2%:%time:~6,2%Z",
>> "%STATUS_FILE%" echo   "git_head": "%GIT_HEAD%",
>> "%STATUS_FILE%" echo   "git_pull_exit": %GIT_EXIT%,
>> "%STATUS_FILE%" echo   "run_dir": "%RUN_DIR:\=/%",
>> "%STATUS_FILE%" echo   "wrapper_version": "2"
>> "%STATUS_FILE%" echo }

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
