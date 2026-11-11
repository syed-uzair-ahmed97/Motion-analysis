@echo off
setlocal
set "ROOT=%~dp0"
set "CAPYTAINE_CACHE_DIR=%ROOT%.cache"
set "MPLCONFIGDIR=%ROOT%.matplotlib"
cd /d "%ROOT%"
"%ROOT%.venv\Scripts\python.exe" -m jupyterlab
