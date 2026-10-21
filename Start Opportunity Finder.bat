@echo off
setlocal
title Opportunity Finder
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

echo.
echo   Opportunity Finder
echo   ------------------
echo   Starting the server. Your browser will open in a moment.
echo   Leave this window open while you use the app; close it to stop.
echo.

rem Find a working Python. The "python" shortcut Windows ships is only a Store
rem installer prompt, so the "py" launcher is tried first.
set "PYEXE="
py -3 --version >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE python --version >nul 2>nul && set "PYEXE=python"
if not defined PYEXE (
  echo   Python 3 was not found. Install it from https://www.python.org/downloads/
  echo   ^(tick "Add python.exe to PATH"^), then run this file again.
  echo.
  pause
  exit /b 1
)

rem Install anything missing, once. This is what stops "No module named ..." errors.
%PYEXE% -c "import flask, requests, feedparser, bs4, docx, reportlab, pypdf, cryptography" >nul 2>nul
if errorlevel 1 (
  echo   Installing the required packages ^(first run only^)...
  %PYEXE% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo   The packages could not be installed. Check your internet connection.
    pause
    exit /b 1
  )
)

%PYEXE% app.py
if errorlevel 1 (
  echo.
  echo   Something went wrong. The message above says what.
  echo.
  pause
)
