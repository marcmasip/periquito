#!/bin/bash

# This script prepares the environment for 'aicli', makes the wrapper
# executable, and creates a symlink to it in /usr/local/bin.

set -e # Exit immediately if a command exits with a non-zero status.

# Get the directory where this install script is located.
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_SCRIPT_NAME="periquito"
WRAPPER_SCRIPT_PATH="$INSTALL_DIR/$WRAPPER_SCRIPT_NAME"
TARGET_DIR="/usr/bin"
SYMLINK_PATH="$TARGET_DIR/$WRAPPER_SCRIPT_NAME"
VENV_DIR="$INSTALL_DIR/venv"

# --- Verification ---
if [ ! -f "$WRAPPER_SCRIPT_PATH" ]; then
    echo "Error: The wrapper script '$WRAPPER_SCRIPT_NAME' was not found in '$INSTALL_DIR'."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but could not be found."
    exit 1
fi

# --- Environment Setup ---
echo "1. Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "Virtual environment created at $VENV_DIR"
fi

echo "2. Installing dependencies from requirements.txt..."
"$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# --- Installation ---
echo "3. Making wrapper script executable..."
chmod +x "$WRAPPER_SCRIPT_PATH"

echo "4. Creating symlink in $TARGET_DIR..."
# Use sudo because /usr/local/bin is typically owned by root.
if [ -L "$SYMLINK_PATH" ]; then
    echo "Symlink already exists at $SYMLINK_PATH. Recreating it."
    sudo rm "$SYMLINK_PATH"
elif [ -f "$SYMLINK_PATH" ]; then
    echo "Error: A file already exists at $SYMLINK_PATH and it's not a symlink."
    echo "Please remove it manually and run this script again."
    exit 1
fi

echo "You may be prompted for your password to create the symlink."
sudo ln -s "$WRAPPER_SCRIPT_PATH" "$SYMLINK_PATH"

echo ""
echo "✅ Installation successful!"
echo "You can now run the agent from any directory using the command:"
echo ""
echo "  aicli \"Your request here\""
echo ""
echo "To uninstall, run:"
echo "  sudo rm $SYMLINK_PATH"
echo "  (You can also remove the project directory: $INSTALL_DIR)"
