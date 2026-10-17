#!/usr/bin/env bash
# Download in Background - Installation Script for SteamOS / Decky Loader
set -e

PLUGIN_NAME="DownloadInBackground"
DECKY_PLUGIN_DIR="${HOME}/homebrew/plugins/${PLUGIN_NAME}"

echo "=================================================="
echo " Installing ${PLUGIN_NAME} for Decky Loader"
echo "=================================================="

# Check if dist/index.js exists, build if missing
if [ ! -f "dist/index.js" ]; then
    echo "Frontend build missing, running build..."
    if command -v pnpm &> /dev/null; then
        pnpm run build
    elif [ -f "${HOME}/.local/bin/pnpm" ]; then
        "${HOME}/.local/bin/pnpm" run build
    elif command -v npm &> /dev/null; then
        npm run build
    else
        echo "Error: Neither pnpm nor npm found. Please build frontend first."
        exit 1
    fi
fi

echo "Target directory: ${DECKY_PLUGIN_DIR}"
mkdir -p "${DECKY_PLUGIN_DIR}"

echo "Copying plugin files..."
cp -rf dist "${DECKY_PLUGIN_DIR}/"
cp -f plugin.json "${DECKY_PLUGIN_DIR}/"
cp -f main.py "${DECKY_PLUGIN_DIR}/"
cp -f package.json "${DECKY_PLUGIN_DIR}/"

if [ -d "assets" ]; then
    cp -rf assets "${DECKY_PLUGIN_DIR}/"
fi

# Ensure permissions
chmod -R u+rwX "${DECKY_PLUGIN_DIR}"

echo ""
echo "Installation completed successfully!"
echo "If Decky Loader is running, restart Decky service or reboot Game Mode:"
echo "  sudo systemctl restart plugin_loader"
echo "=================================================="
