@echo off
REM Collect fresh opportunities and rebuild the phone snapshot, without
REM opening the app. Windows Task Scheduler runs this every morning.
cd /d "%~dp0"

echo. >> "data\refresh.log"
echo ================ %DATE% %TIME% ================ >> "data\refresh.log"

python app.py --refresh >> "data\refresh.log" 2>&1
python app.py --export  >> "data\refresh.log" 2>&1
