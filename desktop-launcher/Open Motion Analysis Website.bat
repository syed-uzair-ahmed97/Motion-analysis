@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 3 | Out-Null; Start-Process 'http://127.0.0.1:8765' } catch { & '%~dp0Reload-MotionAnalysis.ps1' }"
if errorlevel 1 pause
