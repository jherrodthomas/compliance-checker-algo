@echo off
REM ═══════════════════════════════════════════════════════════════════
REM  ComplianceIQ — One-Command Compliance Checker (Windows)
REM ═══════════════════════════════════════════════════════════════════
REM
REM  Usage:
REM    run_compliance.bat <standard> <artifact> [options]
REM
REM  Examples:
REM    run_compliance.bat iso26262_part4.md safety_plan.docx
REM    run_compliance.bat .\standards\ requirements.xlsx --format all
REM    run_compliance.bat standard.pdf artifact.xlsx --convert --format both
REM
REM ═══════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

REM ── Timestamp ──
for /f "tokens=2 delims==" %%i in ('wmic os get localdatetime /value 2^>nul') do set dt=%%i
set TIMESTAMP=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%_%dt:~8,2%-%dt:~10,2%-%dt:~12,2%
set DATE_HUMAN=%dt:~0,4%-%dt:~4,2%-%dt:~6,2% %dt:~8,2%:%dt:~10,2%:%dt:~12,2%

REM ── Script directory ──
set SCRIPT_DIR=%~dp0
set ENGINE=%SCRIPT_DIR%agnostic_engine.py
set REPORTS_DIR=%SCRIPT_DIR%reports

echo.
echo ================================================================
echo   ComplianceIQ — Standard-Agnostic Compliance Checker
echo   %DATE_HUMAN%
echo ================================================================
echo.

REM ── Check arguments ──
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set STANDARD=%~1
set ARTIFACT=%~2
shift
shift

REM ── Parse optional arguments ──
set FORMAT=both
set CONVERT=
set META=
set OUTPUT_DIR=

:parse_args
if "%~1"=="" goto :done_parsing
if /i "%~1"=="--format" (
    set FORMAT=%~2
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--convert" (
    set CONVERT=--convert
    shift
    goto :parse_args
)
if /i "%~1"=="--meta" (
    set META=--meta %~2
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--output" (
    set OUTPUT_DIR=%~2
    shift
    shift
    goto :parse_args
)
shift
goto :parse_args
:done_parsing

REM ── Validate inputs ──
echo Checking inputs...
if not exist "%STANDARD%" (
    echo ERROR: Standard not found: %STANDARD%
    exit /b 1
)
if not exist "%ARTIFACT%" (
    echo ERROR: Artifact not found: %ARTIFACT%
    exit /b 1
)

echo   Standard: %STANDARD%
echo   Artifact: %ARTIFACT%
echo   Format:   %FORMAT%
if not "%CONVERT%"=="" echo   PDF-MD:   enabled
echo.

REM ── Check Python ──
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python not found. Please install Python 3.8+
    exit /b 1
)

REM ── Create reports directory ──
if not "%OUTPUT_DIR%"=="" set REPORTS_DIR=%OUTPUT_DIR%
if not exist "%REPORTS_DIR%" mkdir "%REPORTS_DIR%"

REM ── Build report filename ──
for %%f in ("%STANDARD%") do set STD_NAME=%%~nf
for %%f in ("%ARTIFACT%") do set ART_NAME=%%~nf
set REPORT_BASE=compliance_%STD_NAME%_vs_%ART_NAME%_%TIMESTAMP%

REM ── Run the engine ──
echo Running 8-layer compliance analysis...
echo ----------------------------------------
echo.

set CMD=python "%ENGINE%" "%STANDARD%" "%ARTIFACT%" --format %FORMAT%
if not "%CONVERT%"=="" set CMD=%CMD% %CONVERT%
if not "%META%"=="" set CMD=%CMD% %META%

%CMD%
if errorlevel 1 (
    echo.
    echo ERROR: Engine failed
    exit /b 1
)

echo.
echo ----------------------------------------

REM ── Move and rename reports with timestamp ──
echo Organizing reports...

REM Determine where the engine saved files
for %%f in ("%ARTIFACT%") do set SEARCH_DIR=%%~dpf
if exist "%ARTIFACT%\*" set SEARCH_DIR=%ARTIFACT%

set MOVED=0

for %%e in (json docx pdf) do (
    if exist "%SEARCH_DIR%compliance_report_agnostic.%%e" (
        copy /y "%SEARCH_DIR%compliance_report_agnostic.%%e" "%REPORTS_DIR%\%REPORT_BASE%.%%e" >nul
        echo   [OK] %REPORT_BASE%.%%e
        set /a MOVED+=1
    )
)

REM ── Summary ──
echo.
echo ================================================================
echo   COMPLIANCE CHECK COMPLETE
echo ================================================================
echo.
echo   Reports folder: %REPORTS_DIR%
echo   Base filename:  %REPORT_BASE%
echo   Timestamp:      %DATE_HUMAN%
echo   Standard:       %STANDARD%
echo   Artifact:       %ARTIFACT%
echo.

dir /b "%REPORTS_DIR%\%REPORT_BASE%*" 2>nul
echo.
echo Done.
goto :eof

:usage
echo Usage:
echo   run_compliance.bat ^<standard^> ^<artifact^> [options]
echo.
echo Arguments:
echo   ^<standard^>     Standard file or directory (.md, .json, .pdf with --convert)
echo   ^<artifact^>     Work product file or directory (.docx, .xlsx, .pdf, .md, .txt, .json)
echo.
echo Options:
echo   --format FMT   Output format: json (default), docx, pdf, both, all
echo   --convert      Auto-convert PDF standards to Markdown first
echo   --meta FILE    Optional meta config JSON for schema hints
echo   --output DIR   Custom output directory (default: .\reports\)
echo.
echo Examples:
echo   run_compliance.bat iso26262_part4.md safety_plan.docx --format docx
echo   run_compliance.bat .\standards\ requirements.xlsx --format all
echo   run_compliance.bat iso26262.pdf .\work_products\ --convert --format both
exit /b 1
