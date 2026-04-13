#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
#  ComplianceIQ — One-Command Compliance Checker
# ═══════════════════════════════════════════════════════════════════════
#
#  Ingests a standard (markdown/JSON) and a work product (DOCX/XLSX/PDF/
#  MD/TXT/JSON), runs the 8-layer algorithm pipeline, and generates a
#  timestamped compliance report.
#
#  Usage:
#    ./run_compliance.sh <standard> <artifact> [options]
#
#  Examples:
#    ./run_compliance.sh iso26262_part4.md safety_plan.docx
#    ./run_compliance.sh ./standards/ ./work_products/ --format all
#    ./run_compliance.sh standard.pdf artifact.xlsx --convert --format both
#
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Color codes ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Script directory (where the engine lives) ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="${SCRIPT_DIR}/agnostic_engine.py"
REPORTS_DIR="${SCRIPT_DIR}/reports"

# ── Timestamp ──
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
DATE_HUMAN=$(date +"%B %d, %Y at %I:%M %p")

# ── Banner ──
echo ""
echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}${BOLD}  ComplianceIQ — Standard-Agnostic Compliance Checker${NC}"
echo -e "${BLUE}${BOLD}  ${DATE_HUMAN}${NC}"
echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# ── Argument parsing ──
if [ $# -lt 2 ]; then
    echo -e "${YELLOW}Usage:${NC}"
    echo "  ./run_compliance.sh <standard> <artifact> [options]"
    echo ""
    echo -e "${YELLOW}Arguments:${NC}"
    echo "  <standard>     Standard file or directory (.md, .json, .pdf with --convert)"
    echo "  <artifact>     Work product file or directory (.docx, .xlsx, .pdf, .md, .txt, .json)"
    echo ""
    echo -e "${YELLOW}Options:${NC}"
    echo "  --format FMT   Output format: json (default), docx, pdf, both, all"
    echo "  --convert      Auto-convert PDF standards to Markdown first"
    echo "  --meta FILE    Optional meta config JSON for schema hints"
    echo "  --output DIR   Custom output directory (default: ./reports/)"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  # Markdown standard + Word doc → timestamped DOCX report"
    echo "  ./run_compliance.sh iso26262_part4.md safety_plan.docx --format docx"
    echo ""
    echo "  # Directory of standards + spreadsheet artifact → all formats"
    echo "  ./run_compliance.sh ./standards/ requirements.xlsx --format all"
    echo ""
    echo "  # PDF standard (auto-convert) + mixed artifacts"
    echo "  ./run_compliance.sh iso26262.pdf ./work_products/ --convert --format both"
    echo ""
    echo -e "${YELLOW}Supported Standard Formats:${NC}  .json, .md, .pdf (with --convert)"
    echo -e "${YELLOW}Supported Artifact Formats:${NC}  .docx, .xlsx, .xls, .csv, .pdf, .md, .txt, .json"
    exit 1
fi

STANDARD="$1"
ARTIFACT="$2"
shift 2

# Parse optional arguments
FORMAT="both"
CONVERT=""
META=""
OUTPUT_DIR=""
EXTRA_ARGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --convert)
            CONVERT="--convert"
            shift
            ;;
        --meta)
            META="--meta $2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# ── Validate inputs ──
echo -e "${CYAN}Checking inputs...${NC}"

if [ ! -e "$STANDARD" ]; then
    echo -e "${RED}ERROR: Standard not found: ${STANDARD}${NC}"
    exit 1
fi

if [ ! -e "$ARTIFACT" ]; then
    echo -e "${RED}ERROR: Artifact not found: ${ARTIFACT}${NC}"
    exit 1
fi

# Resolve to absolute paths
STANDARD="$(cd "$(dirname "$STANDARD")" && pwd)/$(basename "$STANDARD")"
if [ -d "$ARTIFACT" ]; then
    ARTIFACT="$(cd "$ARTIFACT" && pwd)"
else
    ARTIFACT="$(cd "$(dirname "$ARTIFACT")" && pwd)/$(basename "$ARTIFACT")"
fi

# Show what we're working with
STD_NAME=$(basename "$STANDARD")
ART_NAME=$(basename "$ARTIFACT")
echo -e "  Standard: ${GREEN}${STD_NAME}${NC}"
echo -e "  Artifact: ${GREEN}${ART_NAME}${NC}"
echo -e "  Format:   ${GREEN}${FORMAT}${NC}"
[ -n "$CONVERT" ] && echo -e "  PDF→MD:   ${GREEN}enabled${NC}"
echo ""

# ── Check Python and dependencies ──
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}ERROR: python3 not found. Please install Python 3.8+${NC}"
    exit 1
fi

if [ ! -f "$ENGINE" ]; then
    echo -e "${RED}ERROR: Engine not found at ${ENGINE}${NC}"
    echo "       Make sure agnostic_engine.py is in the same directory as this script."
    exit 1
fi

# ── Create reports directory ──
if [ -n "$OUTPUT_DIR" ]; then
    REPORTS_DIR="$OUTPUT_DIR"
fi
mkdir -p "$REPORTS_DIR"

# ── Build report filename with timestamp ──
# Strip extensions for naming
STD_CLEAN=$(echo "$STD_NAME" | sed 's/\.[^.]*$//' | tr ' ' '_')
ART_CLEAN=$(echo "$ART_NAME" | sed 's/\.[^.]*$//' | tr ' ' '_')
REPORT_BASE="compliance_${STD_CLEAN}_vs_${ART_CLEAN}_${TIMESTAMP}"

# ── Run the engine ──
echo -e "${BLUE}${BOLD}Running 8-layer compliance analysis...${NC}"
echo -e "${BLUE}────────────────────────────────────────${NC}"
echo ""

# Build command
CMD="python3 \"${ENGINE}\" \"${STANDARD}\" \"${ARTIFACT}\" --format ${FORMAT}"
[ -n "$CONVERT" ] && CMD="${CMD} ${CONVERT}"
[ -n "$META" ] && CMD="${CMD} ${META}"

# Execute
eval $CMD
ENGINE_EXIT=$?

if [ $ENGINE_EXIT -ne 0 ]; then
    echo ""
    echo -e "${RED}${BOLD}Engine exited with error code ${ENGINE_EXIT}${NC}"
    exit $ENGINE_EXIT
fi

echo ""
echo -e "${BLUE}────────────────────────────────────────${NC}"

# ── Move and rename reports with timestamp ──
echo -e "${CYAN}Organizing reports...${NC}"

# Find the generated reports (engine saves them next to the artifact)
if [ -d "$ARTIFACT" ]; then
    SEARCH_DIR="$ARTIFACT"
else
    SEARCH_DIR="$(dirname "$ARTIFACT")"
fi

MOVED=0

for ext in json docx pdf; do
    SRC="${SEARCH_DIR}/compliance_report_agnostic.${ext}"
    if [ -f "$SRC" ]; then
        DEST="${REPORTS_DIR}/${REPORT_BASE}.${ext}"
        cp "$SRC" "$DEST"
        MOVED=$((MOVED + 1))
        echo -e "  ${GREEN}✓${NC} ${REPORT_BASE}.${ext}"
    fi
done

# ── Summary ──
echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  COMPLIANCE CHECK COMPLETE${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Reports (${MOVED} files):${NC}"
echo -e "    ${CYAN}${REPORTS_DIR}/${REPORT_BASE}.*${NC}"
echo ""
echo -e "  ${BOLD}Timestamp:${NC} ${DATE_HUMAN}"
echo -e "  ${BOLD}Standard:${NC}  ${STD_NAME}"
echo -e "  ${BOLD}Artifact:${NC}  ${ART_NAME}"
echo ""

# List the actual files
if [ $MOVED -gt 0 ]; then
    echo -e "  ${BOLD}Generated files:${NC}"
    for ext in json docx pdf; do
        DEST="${REPORTS_DIR}/${REPORT_BASE}.${ext}"
        if [ -f "$DEST" ]; then
            SIZE=$(du -h "$DEST" | cut -f1)
            echo -e "    ${GREEN}→${NC} ${REPORT_BASE}.${ext}  (${SIZE})"
        fi
    done
fi

echo ""
echo -e "${BLUE}Done.${NC}"
