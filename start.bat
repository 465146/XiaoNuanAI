@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================
echo         XiaoNuan CBT Launcher
echo ========================================
echo.

REM Kill any process on port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    echo [clean] Killing PID %%a on port 8000...
    taskkill //F //PID %%a >nul 2>&1
)

REM Kill any process on port 18789
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":18789.*LISTENING"') do (
    echo [clean] Killing PID %%a on port 18789...
    taskkill //F //PID %%a >nul 2>&1
)

REM Clean lock file
if exist "%APPDATA%\..\.openclaw\gateway.lock" del /f "%APPDATA%\..\.openclaw\gateway.lock" 2>nul

timeout /t 2 >nul
echo [clean] Ports cleaned
echo.

REM OpenClaw Gateway
set "DEEPSEEK_API_KEY=sk-e6297d37490043eabf06faf2b39b6ff6"
set "OPENCLAW_JS=%APPDATA%\npm\node_modules\openclaw\dist\index.js"
if exist "%OPENCLAW_JS%" (
    echo [openclaw] Starting Gateway...
    start /B "" node "%OPENCLAW_JS%" gateway --port 18789
    timeout /t 4 >nul
    echo [openclaw] Gateway started
) else (
    echo [openclaw] Not found
)

echo.
echo [web] Starting FastAPI...
echo     http://localhost:8000
echo.
uv run uvicorn main:app --host 127.0.0.1 --port 8000
