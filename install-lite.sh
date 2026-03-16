#!/bin/bash

set -e

MODE="full"
if [ "$1" = "--lite" ]; then
    MODE="lite"
fi

echo ""
echo "======================================"
echo "   SHUFFLE PLAYER INSTALLER"
echo "======================================"
echo "Mode: $MODE"
echo ""

INSTALL_DIR="$HOME/shuffle-player"
VENV_DIR="$INSTALL_DIR/.venv"

echo "Updating system..."
sudo apt update

echo "Installing system dependencies..."
sudo apt install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    mpv \
    sqlite3 \
    ffmpeg \
    cifs-utils

echo ""
echo "Downloading Shuffle Player..."

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Existing install found — updating..."
    cd "$INSTALL_DIR"
    git pull
elif [ -d "$INSTALL_DIR" ]; then
    echo "Directory exists but is not a git repo: $INSTALL_DIR"
    echo "Please move or remove it, then re-run installer."
    exit 1
else
    git clone https://github.com/judasshuffle/shuffle-player.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo ""
echo "Installing Python requirements..."

python3 -m venv "$VENV_DIR"
. "$VENV_DIR/bin/activate"
pip install --upgrade pip

if [ "$MODE" = "lite" ] && [ -f requirements-lite.txt ]; then
    echo "Installing lite Python requirements..."
    pip install -r requirements-lite.txt
elif [ -f requirements.txt ]; then
    echo "Installing full Python requirements..."
    pip install -r requirements.txt
else
    echo "No requirements file found — skipping Python package install."
fi

echo ""
echo "Installing services..."

if [ -d systemd ]; then
    sudo cp systemd/*.service /etc/systemd/system/ 2>/dev/null || true
fi

if [ -d systemd/user ]; then
    sudo cp systemd/user/*.service /etc/systemd/system/ 2>/dev/null || true
fi

sudo systemctl daemon-reload

echo ""
echo "Enabling services..."

if [ -f /etc/systemd/system/shuffle-radio.service ]; then
    sudo systemctl enable shuffle-radio.service 2>/dev/null || true
fi

if [ -f /etc/systemd/system/shuffle-web.service ]; then
    sudo systemctl enable shuffle-web.service 2>/dev/null || true
fi

if [ "$MODE" = "full" ]; then
    if [ -f /etc/systemd/system/shuffle-radio-hd.service ]; then
        sudo systemctl enable shuffle-radio-hd.service 2>/dev/null || true
    fi

    if [ -f /etc/systemd/system/shuffle-control.service ]; then
        sudo systemctl enable shuffle-control.service 2>/dev/null || true
    fi
fi

echo ""
echo "Starting services..."

if [ -f /etc/systemd/system/shuffle-web.service ]; then
    sudo systemctl start shuffle-web.service 2>/dev/null || true
fi

if [ "$MODE" = "full" ]; then
    if [ -f /etc/systemd/system/shuffle-radio-hd.service ]; then
        sudo systemctl start shuffle-radio-hd.service 2>/dev/null || true
    fi

    if [ -f /etc/systemd/system/shuffle-control.service ]; then
        sudo systemctl start shuffle-control.service 2>/dev/null || true
    fi
fi

echo ""
echo "Optional database build..."

if [ -d /mnt/lossless ]; then
    echo "Music root found at /mnt/lossless"
    echo "Building/updating jukebox database..."
    "$VENV_DIR/bin/python" "$INSTALL_DIR/scripts/update_index_sqlite.py" || true
else
    echo "No /mnt/lossless mount found — skipping database build."
fi

echo ""
echo "======================================"
echo "Shuffle Player installed!"
echo ""
echo "Web UI:"
echo "http://$(hostname -I | awk '{print $1}'):8091"
echo "======================================"
echo ""