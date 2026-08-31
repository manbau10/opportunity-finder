@echo off
title Opportunity Finder
cd /d "%~dp0"

echo.
echo   Opportunity Finder
echo   ------------------
echo   Starting the server. Your browser will open in a moment.
echo   Leave this window open while you use the app; close it to stop.
echo.

python app.py
if errorlevel 1 (
  echo.
  echo   Something went wrong. If Python is missing, install it from python.org,
  echo   then run:  pip install -r requirements.txt
  echo.
  pause
)
