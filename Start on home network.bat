@echo off
setlocal
title Opportunity Finder - home network
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

echo.
echo   Opportunity Finder - home network mode
echo   -------------------------------------
echo   The full dashboard, reachable from your phone while it is on the
echo   same Wi-Fi as this PC. The address to open on your phone is printed
echo   below. Leave this window open; close it to stop.
echo.
echo   If your phone cannot reach it, the usual causes are:
echo     - Windows Firewall has not been told to allow it (see README)
echo     - a VPN is on, which hides this PC from the Wi-Fi
echo     - the phone is on mobile data, not the house Wi-Fi
echo.

set "PYEXE="
py -3 --version >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE python --version >nul 2>nul && set "PYEXE=python"
if not defined PYEXE (
  echo   Python 3 was not found. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)

%PYEXE% -c "import flask, requests, feedparser, bs4, docx, reportlab, pypdf, cryptography" >nul 2>nul
if errorlevel 1 (
  echo   Installing the required packages ^(first run only^)...
  %PYEXE% -m pip install -r requirements.txt
)

%PYEXE% app.py --lan
if errorlevel 1 (
  echo.
  echo   Something went wrong. The message above says what.
  echo.
  pause
)
