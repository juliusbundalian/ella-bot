# ELLA Scripts & Auto-Pull Service

This directory contains utility scripts for ELLA Bot operation and service management.

## Key Scripts

* `auto_pull_on_connect.sh` - Automated Git pull script triggered upon internet connection.
* `install_auto_pull_service.sh` - Installs `ella-auto-pull.service` into `~/.config/systemd/user/`.

## Documentation & Troubleshooting

For detailed documentation, root cause analysis of git stash errors, and troubleshooting steps for auto-pull issues, see:
* [`docs/AUTO_PULL_README.md`](../docs/AUTO_PULL_README.md)
