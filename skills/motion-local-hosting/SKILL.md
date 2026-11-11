---
name: motion-local-hosting
description: Start, stop, reload, diagnose, build, or deploy the Motion Analysis website while preserving saved jobs. Use for requests mentioning the Desktop launcher, localhost, port 8765, D-drive host, website reload, server status, FastAPI/Uvicorn, production build, Cloudflare, or cloud deployment.
---

# Motion Local Hosting

## Locations

- Editable source: `C:\Users\HAIER\Documents\Capyteine_Motion_analysis`
- Live local installation: `D:\Motion Analysis`
- URL: `http://127.0.0.1:8765`
- Desktop controls: `C:\Users\HAIER\Desktop\Motion Analysis Website`

## Local reload

Use the Desktop `Reload Motion Analysis Website.bat` control. It stops only the process listening on port 8765, launches `D:\Motion Analysis\.venv\Scripts\python.exe -m uvicorn dashboard.backend:app`, waits for `/api/health`, then opens the site.

## Deployment workflow

1. Edit only the C-drive source.
2. Run Python tests and the production frontend build.
3. Copy application code and `dashboard/dist` to D while preserving `dashboard/jobs`, `dashboard/sea_state_jobs`, `dashboard/response_jobs`, `.venv`, and existing outputs.
4. Reload the live server.
5. Verify `/api/health`, the root asset, and one affected API path.

Never delete saved jobs or overwrite the D-drive virtual environment during a routine reload.

## Current deferred work

Public hosting still needs authentication, durable object storage/database, a solver-worker queue, resource limits, monitoring, backups, TLS/domain setup, and a provider architecture suitable for long CPU-bound Capytaine jobs. Cloudflare Pages/Workers alone is not the solver host.
