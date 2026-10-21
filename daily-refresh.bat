@echo off
REM Collect fresh opportunities and rebuild the phone snapshot, without
REM opening the app. Windows Task Scheduler runs this every morning.
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

set "PYEXE="
py -3 --version >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE python --version >nul 2>nul && set "PYEXE=python"

if not exist "data" mkdir "data"
echo. >> "data\refresh.log"
echo ================ %DATE% %TIME% ================ >> "data\refresh.log"

if not defined PYEXE (
  echo Python was not found. Install Python 3 from python.org. >> "data\refresh.log"
  exit /b 1
)

REM A missing package used to make every scheduled run crash silently; install it instead.
%PYEXE% -c "import flask, requests, feedparser, bs4, docx, reportlab, pypdf, cryptography" >nul 2>nul
if errorlevel 1 %PYEXE% -m pip install -r requirements.txt >> "data\refresh.log" 2>&1

%PYEXE% app.py --refresh >> "data\refresh.log" 2>&1
%PYEXE% app.py --export  >> "data\refresh.log" 2>&1
