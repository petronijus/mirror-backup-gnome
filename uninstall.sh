#!/usr/bin/env bash
# Uninstall Mirror Backup for GNOME
set -euo pipefail

EXT_UUID="backup-monitor@petronijus"

echo "=== Mirror Backup for GNOME Uninstaller ==="

# 1. Stop and disable timers
echo "Stopping backup timers..."
for timer in backup-secondary.timer backup-fun.timer backup-music.timer backup-photos.timer; do
    systemctl --user disable --now "$timer" 2>/dev/null || true
done

# 2. Stop any running services
for svc in backup-secondary.service backup-fun.service backup-music.service backup-photos.service; do
    systemctl --user stop "$svc" 2>/dev/null || true
done

# 3. Remove systemd units
echo "Removing systemd units..."
rm -f "$HOME/.config/systemd/user"/backup-{secondary,fun,music,photos}.{service,timer}
rm -rf "$HOME/.config/systemd/user"/backup-{secondary,fun,music,photos}.timer.d
systemctl --user daemon-reload

# 4. Remove GNOME extension
echo "Removing GNOME extension..."
gnome-extensions disable "$EXT_UUID" 2>/dev/null || true
rm -rf "$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"

# 5. Remove script (keep configs and logs)
rm -f "$HOME/.local/bin/backup-sync"

echo ""
echo "=== Uninstalled ==="
echo "Kept: ~/.config/backup-sync/ (configs) and ~/.local/share/backup-sync/ (logs/status)"
echo "Remove manually if not needed."
