#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  Build the ISO 26262 Checker engine binary with PyInstaller
#  Output: ./engine/iso26262_checker
# ═══════════════════════════════════════════════════════════════

echo ""
echo "  Building ISO 26262 Checker engine..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  [ERROR] Python3 not found! Install Python 3.8+"
    exit 1
fi

# Install PyInstaller if needed
if ! python3 -m PyInstaller --version &> /dev/null; then
    echo "  Installing PyInstaller..."
    pip3 install pyinstaller --break-system-packages
fi

# Install runtime dependencies
echo "  Installing dependencies..."
pip3 install python-docx openpyxl reportlab --break-system-packages 2>/dev/null

# Build the executable
echo "  Running PyInstaller..."
python3 -m PyInstaller --onefile \
    --name iso26262_checker \
    --distpath "./engine" \
    --workpath "./build_temp" \
    --specpath "./build_temp" \
    --clean \
    --noconfirm \
    "./ISO26262_Checker.py"

if [ -f "engine/iso26262_checker" ]; then
    echo ""
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║  Engine built successfully!                   ║"
    echo "  ║  Output: engine/iso26262_checker              ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo ""
else
    echo ""
    echo "  [ERROR] Build failed. Check output above."
    echo ""
fi

# Cleanup
rm -rf build_temp
