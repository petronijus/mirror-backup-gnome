#!/bin/bash
# Launch Mirror Backup for GNOME desktop app in development mode
cd "$(dirname "$0")"
PYTHONPATH="src:$PYTHONPATH" exec python3 -m backup_monitor.main "$@"
