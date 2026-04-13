@echo off
REM ═══════════════════════════════════════════════════════════════
REM  Build the ISO 26262 Checker engine binary with PyInstaller
REM  Output: .\engine\iso26262_checker.exe
REM ═══════════════════════════════════════════════════════════════

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║  Building ISO 26262 Engine Binary            ║
echo  ╚══════════════════════════════════════════════╝
echo.

REM Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo  [ERROR] Python not found!
    echo  Install Python 3.8+ from https://python.org
    echo  Make sure "Add Python to PATH" is checked.
    pause
    exit /b 1
)
python --version

REM Install PyInstaller if needed
pip show pyinstaller >nul 2>nul
if errorlevel 1 (
    echo  Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo  [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

REM Install runtime dependencies
echo  Installing Python dependencies...
pip install python-docx openpyxl reportlab >nul 2>nul

REM Create engine output directory
if not exist "%~dp0engine" mkdir "%~dp0engine"

REM Build the executable
echo  Running PyInstaller (this may take 1-2 minutes)...
pyinstaller --onefile ^
    --name iso26262_checker ^
    --distpath "%~dp0engine" ^
    --workpath "%~dp0build_temp" ^
    --specpath "%~dp0build_temp" ^
    --clean ^
    --noconfirm ^
    "%~dp0ISO26262_Checker.py"

if exist "%~dp0engine\iso26262_checker.exe" (
    echo.
    echo  ╔══════════════════════════════════════════════╗
    echo  ║  Engine built successfully!                   ║
    echo  ║  Output: engine\iso26262_checker.exe          ║
    echo  ╚══════════════════════════════════════════════╝
    echo.
) else (
    echo.
    echo  [ERROR] Build failed. Check output above.
    echo.
    pause
    exit /b 1
)

REM Cleanup build artifacts
if exist "%~dp0build_temp" rmdir /s /q "%~dp0build_temp"

exit /b 0
