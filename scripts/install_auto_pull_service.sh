#!/usr/bin/env bash
# ==============================================================================
# Installer for ELLA Auto-Pull Systemd User Service
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SERVICE_DIR}/ella-auto-pull.service"

mkdir -p "${SERVICE_DIR}"

cat <<EOF > "${SERVICE_FILE}"
[Unit]
Description=ELLA Auto-Pull on Internet Connection Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${SCRIPT_DIR}/scripts/auto_pull_on_connect.sh --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

echo "[+] Service file created at ${SERVICE_FILE}"

systemctl --user daemon-reload
systemctl --user enable ella-auto-pull.service
systemctl --user restart ella-auto-pull.service

echo "[+] ELLA Auto-Pull service installed and started successfully!"
echo "[+] Checking status:"
systemctl --user status ella-auto-pull.service --no-pager || true
