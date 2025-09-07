#!/bin/bash

set -e

echo "🔄 Updating system..."
sudo apt update && sudo apt upgrade -y

echo "📦 Installing required packages..."
sudo apt install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils virt-manager virtinst
sudo apt install -y python3 python3-pip git

echo "🐍 Cloning vm manager repo..."
if [ -d vm ]; then
  echo "Directory vm already exists. Pulling latest changes..."
  cd vm
  git pull
  cd ..
else
  git clone https://github.com/AnkitBoss790/vm.git
fi

cd vm

echo "📥 Installing Python dependencies..."
pip3 install flask flask-login flask_sqlalchemy libvirt-python

echo "📂 Ensuring ISO images exist..."
# create images directory
sudo mkdir -p /var/lib/libvirt/images
cd /var/lib/libvirt/images

# Ubuntu ISO
if [ ! -f ubuntu-22.04.iso ]; then
  echo "Downloading Ubuntu-22.04 ISO..."
  sudo wget https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso -O ubuntu-22.04.iso
fi

# Debian ISO
if [ ! -f debian-12.iso ]; then
  echo "Downloading Debian-12 ISO..."
  sudo wget https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.5.0-amd64-netinst.iso -O debian-12.iso
fi

cd ../..

echo "⚙ Setting up service to run panel on startup..."

SERVICE_FILE=/etc/systemd/system/vm-manager.service

sudo bash -c "cat > $SERVICE_FILE <<EOL
[Unit]
Description=VM Manager Panel Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 $(pwd)/vm/app.py
WorkingDirectory=$(pwd)/vm
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOL"

sudo systemctl daemon-reload
sudo systemctl enable vm-manager.service
sudo systemctl start vm-manager.service

echo "✅ Installation complete!"
echo "👉 Panel should be running at: http://$(hostname -I | awk '{print $1}'):5000"
