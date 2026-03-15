#!/bin/bash

set -e

echo ""
echo "======================================"
echo "   SHUFFLE PLAYER INSTALLER"
echo "======================================"
echo ""

INSTALL_DIR="$HOME/shuffle-player"
VENV_DIR="$INSTALL_DIR/.venv"

echo "Updating system..."
sudo apt update

echo "Installing dependencies..."
sudo apt install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    mpv \
    sqlite3

echo ""
echo "Downloading Shuffle Player..."

if [ -d "$INSTALL_DIR" ]; then
    echo "Existing install found — updating..."
    cd "$INSTALL_DIR"
    git pull
else
    git clone https://github.com/judasshuffle/shuffle-player.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo ""
echo "Installing Python requirements..."

if [ -f requirements.txt ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"

    echo "Activating virtual environment..."
    . "$VENV_DIR/bin/activate"

    echo "Upgrading pip..."
    pip install --upgrade pip

    echo "Installing requirements..."
    pip install -r requirements.txt
else
    echo "No requirements.txt found — skipping Python package install."
fi

echo ""
echo "Installing services..."

if [ -d systemd ]; then
    sudo cp systemd/*.service /etc/systemd/system/ 2>/dev/null || true
    sudo systemctl daemon-reload
else
    echo "No systemd directory found — skipping service install."
fi

echo ""
echo "Enabling services..."

sudo systemctl enable shuffle-radio-hd.service 2>/dev/null || true
sudo systemctl enable shuffle-control.service 2>/dev/null || true
sudo systemctl enable shuffle-web.service 2>/dev/null || true

echo ""
echo "Starting services..."

sudo systemctl start shuffle-radio-hd.service 2>/dev/null || true
sudo systemctl start shuffle-control.service 2>/dev/null || true
sudo systemctl start shuffle-web.service 2>/dev/null || true

echo ""
echo "======================================"
echo "Shuffle Player installed!"
echo ""
echo "Web UI:"
echo "http://$(hostname -I | awk '{print $1}'):8091"
echo "======================================"
echo ""