@echo off
setlocal
set "ROOT=%~dp0"
set "CAPYTAINE_CACHE_DIR=%ROOT%.cache"
set "MPLCONFIGDIR=%ROOT%.matplotlib"
if "%~1"=="" (
  echo Usage: run_analysis.bat config.yaml
  exit /b 2
)
"%ROOT%.venv\Scripts\python.exe" "%ROOT%run_hydrodynamics.py" "%~1"
