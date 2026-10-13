@echo off
rem Overnight data run for the Resonance interest model.
rem   run.bat test   - 2-video smoke test (about 5 minutes). Run this first, before leaving it.
rem   run.bat        - full run: collect for 7 hours, then Gemini signals, then zip.
rem   run.bat signals - only the Gemini signal pass + zip (if collection already finished).
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set REPO=%~dp0..\..\..

rem --- uv (Python tooling). Installs to %USERPROFILE%\.local\bin if missing.
where uv >nul 2>nul
if errorlevel 1 (
  echo Installing uv...
  powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not on PATH. Open a new terminal and run this again.
  exit /b 1
)

rem --- Gemini credentials (Application Default Credentials for project habeas-codus).
where gcloud >nul 2>nul
if errorlevel 1 (
  echo Install the Google Cloud CLI first: https://cloud.google.com/sdk/docs/install
  exit /b 1
)
call gcloud auth application-default print-access-token >nul 2>nul
if errorlevel 1 (
  echo Not signed in for Gemini. Run these two commands, then run this script again:
  echo   gcloud auth application-default login
  echo   gcloud auth application-default set-quota-project habeas-codus
  exit /b 1
)

if /i "%1"=="test" goto test
if /i "%1"=="signals" goto signals

echo === 1/3 Collecting videos and transcripts (up to 7 hours) ===
rem No GPU on the target laptop: Whisper "small" on CPU is about 3x faster than large-v3-turbo.
uv run collect.py --target 500 --hours 7 --model small
goto signals

:test
echo === Smoke test: 2 videos, then Gemini signals ===
uv run collect.py --target 2 --hours 0.5 --model small
pushd "%REPO%\backend"
uv run python scripts\interest_train.py signals --max-calls 10 --concurrency 2 --cbc-train 0 --cbc-test 0
popd
echo.
echo If you see "done": 2 (or 1) above with no errors, start the real run with: run.bat
exit /b 0

:signals
echo === 2/3 Gemini signals (bounded to 1500 calls, about $6 max) ===
pushd "%REPO%\backend"
uv run python scripts\interest_train.py signals --max-calls 1500 --concurrency 3 --cbc-train 0 --cbc-test 0
rem A second pass retries videos that hit Gemini rate limits the first time.
uv run python scripts\interest_train.py signals --max-calls 500 --concurrency 2 --cbc-train 0 --cbc-test 0
popd

echo === 3/3 Packing results ===
uv run collect.py --zip-only
echo.
echo Done. Send back the interest_data_*.zip file in:
echo   %~dp0
exit /b 0
