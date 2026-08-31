@echo off
title Opportunity Finder - home network
cd /d "%~dp0"

echo.
echo   Opportunity Finder - home network mode
echo   -------------------------------------
echo   The full dashboard, reachable from your phone while it is on the
echo   same Wi-Fi as this PC. The address to open on your phone is printed
echo   below. Leave this window open; close it to stop.
echo.
echo   If your phone cannot reach it, the usual causes are:
echo     - Windows Firewall has not been told to allow it (see README)
echo     - the HotspotShield VPN is on, which hides this PC from the Wi-Fi
echo     - the phone is on mobile data, not the house Wi-Fi
echo.

python app.py --lan
if errorlevel 1 (
  echo.
  echo   Something went wrong. If packages are missing, run:
  echo     pip install -r requirements.txt
  echo.
  pause
)
