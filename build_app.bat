@echo off
SETLOCAL EnableDelayedExpansion

REM ═══════════════════════════════════════════════════════════════
REM  Lion of Functional Safety Engine  -  Full Desktop App Build
REM
REM  Double-click this file. It will request admin rights (needed
REM  for electron-builder symlink extraction), then build
REM  everything and place the app in a LionSafetyEngine folder.
REM
REM  Prerequisites: Python 3.8+, Node.js 18+
REM ═══════════════════════════════════════════════════════════════

REM ─── Self-elevate to Administrator ─────────────────────────────
net session >nul 2>&1
if !errorlevel! neq 0 (
    echo  Requesting administrator privileges...
    powershell -Command "Start-Process -Verb RunAs -FilePath '%~f0' -ArgumentList '%~dp0'"
    exit /b 0
)

REM Now running as admin - cd to the script's folder
cd /d "%~dp0"
if "%~1" neq "" cd /d "%~1"

echo.
echo  ==========================================================
echo   Lion of Functional Safety Engine - Desktop App Builder
echo   (Running as Administrator)
echo  ==========================================================
echo.

REM ─── Preflight: Python ─────────────────────────────────────────
echo  [CHECK] Python...
where python >nul 2>nul
if !errorlevel! neq 0 (
    echo.
    echo  [ERROR] Python not found on PATH!
    echo  Install Python 3.8+ from https://python.org
    echo  Make sure "Add Python to PATH" is checked during install.
    echo.
    goto :fail
)
python --version
echo  [OK] Python found.
echo.

REM ─── Preflight: Node.js ────────────────────────────────────────
echo  [CHECK] Node.js...
where node >nul 2>nul
if !errorlevel! neq 0 (
    echo.
    echo  [ERROR] Node.js not found on PATH!
    echo  Install Node.js 18+ from https://nodejs.org
    echo  Then restart this script.
    echo.
    goto :fail
)
node --version
echo  [OK] Node.js found.
echo.

REM ─── Preflight: npm ────────────────────────────────────────────
echo  [CHECK] npm...
where npm >nul 2>nul
if !errorlevel! neq 0 (
    echo.
    echo  [ERROR] npm not found on PATH!
    echo  npm comes bundled with Node.js. Reinstall Node.js.
    echo.
    goto :fail
)
call npm --version
echo  [OK] npm found.
echo.

echo  All prerequisites found. Starting build...
echo.

REM ═══════════════════════════════════════════════════════════════
REM  STEP 1 of 3: Build Python engine with PyInstaller
REM ═══════════════════════════════════════════════════════════════
echo  ==========================================================
echo   [1/3] Building Python engine with PyInstaller...
echo  ==========================================================
echo.

REM Install PyInstaller if needed
pip show pyinstaller >nul 2>nul
if !errorlevel! neq 0 (
    echo  Installing PyInstaller via pip...
    pip install pyinstaller
    if !errorlevel! neq 0 (
        echo.
        echo  [ERROR] Failed to install PyInstaller.
        echo  Try manually: pip install pyinstaller
        echo.
        goto :fail
    )
)
echo  [OK] PyInstaller available.

REM Install Python runtime dependencies
echo  Installing Python dependencies...
pip install python-docx openpyxl reportlab 2>nul
echo  [OK] Python dependencies installed.

REM Create engine output directory
if not exist "%~dp0engine" mkdir "%~dp0engine"

REM Build the executable
echo.
echo  Running PyInstaller (this may take 1-2 minutes)...
echo.
python -m PyInstaller --onefile --name iso26262_checker --distpath "%~dp0engine" --workpath "%~dp0build_temp" --specpath "%~dp0build_temp" --clean --noconfirm "%~dp0ISO26262_Checker.py"

if not exist "%~dp0engine\iso26262_checker.exe" (
    echo.
    echo  [ERROR] PyInstaller build failed.
    echo  The file engine\iso26262_checker.exe was not created.
    echo  Check the PyInstaller output above for errors.
    echo.
    goto :fail
)
echo.
echo  [OK] Engine built: engine\iso26262_checker.exe
echo.

REM Cleanup PyInstaller temp
if exist "%~dp0build_temp" rmdir /s /q "%~dp0build_temp"

REM ═══════════════════════════════════════════════════════════════
REM  STEP 2 of 3: Install Electron dependencies
REM ═══════════════════════════════════════════════════════════════
echo  ==========================================================
echo   [2/3] Installing Electron dependencies (npm install)...
echo  ==========================================================
echo.
call npm install
if !errorlevel! neq 0 (
    echo.
    echo  [ERROR] npm install failed.
    echo  Check your internet connection and try again.
    echo.
    goto :fail
)
echo.
echo  [OK] Electron dependencies installed.
echo.

REM ═══════════════════════════════════════════════════════════════
REM  STEP 3 of 3: Package desktop app
REM ═══════════════════════════════════════════════════════════════
echo  ==========================================================
echo   [3/3] Packaging desktop app with electron-builder...
echo         (this may take a few minutes)
echo  ==========================================================
echo.

REM Disable code signing
set CSC_IDENTITY_AUTO_DISCOVERY=false
set CSC_LINK=
set WIN_CSC_LINK=

REM Clear any stale winCodeSign cache
if exist "%LOCALAPPDATA%\electron-builder\Cache\winCodeSign" (
    echo  Clearing stale winCodeSign cache...
    rmdir /s /q "%LOCALAPPDATA%\electron-builder\Cache\winCodeSign" 2>nul
)

call npx electron-builder --win --dir
if !errorlevel! neq 0 (
    echo.
    echo  [ERROR] electron-builder packaging failed.
    echo  Check the output above for errors.
    echo.
    goto :fail
)
echo.
echo  [OK] Desktop app packaged.
echo.

REM ─── Move portable app folder here ────────────────────────────
echo  Moving app to this folder...
if exist "%~dp0dist\win-unpacked" (
    if exist "%~dp0LionSafetyEngine" rmdir /s /q "%~dp0LionSafetyEngine" 2>nul
    move "%~dp0dist\win-unpacked" "%~dp0LionSafetyEngine" >nul
    echo  [OK] App folder: LionSafetyEngine\
    echo  [OK] Run: LionSafetyEngine\Lion of Functional Safety.exe
) else (
    echo  [WARNING] Could not find dist\win-unpacked folder.
    echo  Check the dist\ folder manually.
    goto :fail
)

REM ─── Cleanup build artifacts ───────────────────────────────────
echo  Cleaning up build folders...
if exist "%~dp0dist" rmdir /s /q "%~dp0dist" 2>nul
if exist "%~dp0node_modules" rmdir /s /q "%~dp0node_modules" 2>nul
if exist "%~dp0engine" rmdir /s /q "%~dp0engine" 2>nul
if exist "%~dp0build_temp" rmdir /s /q "%~dp0build_temp" 2>nul

echo.
echo  ==========================================================
echo.
echo   BUILD COMPLETE!
echo.
echo   Your app is in the LionSafetyEngine folder.
echo   Double-click: LionSafetyEngine\Lion of Functional Safety.exe
echo   Share the whole folder - no Python or Node needed to run it.
echo.
echo  ==========================================================
echo.
echo  Press any key to close...
pause >nul
exit /b 0

:fail
echo.
echo  ==========================================================
echo   BUILD FAILED - Read the error message above.
echo  ==========================================================
echo.
echo  Press any key to close...
pause >nul
exit /b 1
