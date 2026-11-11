@echo off
setlocal
set "ROOT=%~dp0"
set "CAPYTAINE_CACHE_DIR=%ROOT%.cache"
set "MPLCONFIGDIR=%ROOT%.matplotlib"
"%ROOT%.venv\Scripts\python.exe" "%ROOT%create_demo_mesh.py"
if errorlevel 1 exit /b %errorlevel%
"%ROOT%.venv\Scripts\python.exe" "%ROOT%run_hydrodynamics.py" "%ROOT%config.demo.yaml"
