@echo off
echo ========================================
echo Bloomberg Data Pipeline — %date%
echo ========================================

cd /d C:\Users\stephanie.leung\bloomberg-pipeline

echo.
echo [1/2] Extracting data from Bloomberg...
python bbg_extract.py

echo.
echo [2/2] Copying to Google Drive...
python bbg_upload.py

echo.
echo Done!
echo.
pause
