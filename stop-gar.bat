@echo off
rem Stop API/UI children and GAR's isolated desktop containers; preserve user files.
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo GAR's Python environment is missing. Cannot safely identify its services.
  popd
  if /I not "%~1"=="--no-pause" pause
  exit /b 1
)
".venv\Scripts\python.exe" -m gar.lifecycle
set "GAR_STOP_EXIT=%ERRORLEVEL%"
popd
if /I not "%~1"=="--no-pause" pause
exit /b %GAR_STOP_EXIT%
