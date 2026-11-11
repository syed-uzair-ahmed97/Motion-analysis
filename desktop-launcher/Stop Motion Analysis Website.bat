@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$listeners = Get-NetTCPConnection -State Listen -LocalPort 8765 -ErrorAction SilentlyContinue; foreach ($listener in $listeners) { Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue }; Write-Host 'Motion Analysis website stopped.'"
pause
