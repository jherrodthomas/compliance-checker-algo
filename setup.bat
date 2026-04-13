@echo off
REM ═══════════════════════════════════════════════════════════════
REM  ComplianceIQ — One-Time Setup
REM  Run this ONCE to install Python dependencies
REM ═══════════════════════════════════════════════════════════════

echo.
echo ============================================
echo   ComplianceIQ Setup
echo ============================================
echo.
echo Checking Python...

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: Python not found!
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

python --version
echo.
echo Installing required packages...
echo.

pip install python-docx openpyxl reportlab

echo.
echo ============================================
echo   Setup complete!
echo ============================================
echo.
echo You can now run compliance checks:
echo.
echo   run_compliance.bat ^<standard^> ^<artifact^>
echo.
echo Example:
echo   run_compliance.bat test_sample_iso_standard.md sample_user_doc_v2.json --format both
echo.
pause
