@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo The project virtual environment was not found: %PYTHON%
  pause
  exit /b 1
)
if not exist "%ROOT%dashboard\dist\index.html" (
  echo The dashboard frontend has not been built.
  pause
  exit /b 1
)
start "Motion Analysis Server" /min cmd /c ""%PYTHON%" "%ROOT%dashboard\backend.py" --host 127.0.0.1 --port 8765"
for /L %%I in (1,1,45) do (
  powershell -NoProfile -Command "try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8765/' -TimeoutSec 2; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>nul
  if not errorlevel 1 goto ready
  timeout /t 1 /nobreak >nul
)
echo The dashboard server did not become ready. Check that port 8765 is available.
pause
exit /b 1
:ready
start "" "http://127.0.0.1:8765"
echo Motion Analysis dashboard started at http://127.0.0.1:8765
