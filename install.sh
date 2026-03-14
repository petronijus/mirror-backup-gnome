#!/usr/bin/env bash
# Install backup-monitor: script, configs, systemd units, GNOME extension
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXT_UUID="backup-monitor@petronijus"

echo "=== Backup Monitor Installer ==="

# 1. Main sync script
echo "Installing backup-sync script..."
install -Dm755 "$SCRIPT_DIR/scripts/backup-sync" "$HOME/.local/bin/backup-sync"

# 2. Config / exclude files
echo "Installing config files..."
mkdir -p "$HOME/.config/backup-sync"
for f in "$SCRIPT_DIR"/config/*; do
    install -Dm644 "$f" "$HOME/.config/backup-sync/$(basename "$f")"
done

# 3. Status directory
mkdir -p "$HOME/.local/share/backup-sync/status"
mkdir -p "$HOME/.local/share/backup-sync/logs"

# 4. Systemd units
echo "Installing systemd user units..."
mkdir -p "$HOME/.config/systemd/user"
for f in "$SCRIPT_DIR"/systemd/*; do
    install -Dm644 "$f" "$HOME/.config/systemd/user/$(basename "$f")"
done

systemctl --user daemon-reload

# 5. Enable timers
echo "Enabling backup timers..."
for timer in backup-secondary.timer backup-fun.timer backup-music.timer backup-photos.timer; do
    systemctl --user enable --now "$timer"
    echo "  ✔ $timer enabled"
done

# 6. GNOME extension
echo "Installing GNOME Shell extension..."
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
mkdir -p "$EXT_DIR"
for f in "$SCRIPT_DIR"/gnome-extension/*; do
    install -Dm644 "$f" "$EXT_DIR/$(basename "$f")"
done

# 7. Enable extension
if command -v gnome-extensions &>/dev/null; then
    gnome-extensions enable "$EXT_UUID" 2>/dev/null || true
    echo "  ✔ Extension enabled (restart GNOME Shell to load: Alt+F2 → r → Enter, or log out/in)"
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "Backup jobs installed:"
echo "  backup-secondary  /mnt/SECONDARY/ → /mnt/DATA-SLOW/BACKUP/SECONDARY/  (every 2 days, archive 60d)"
echo "  backup-fun        /mnt/FUN/       → /mnt/DATA-SLOW/BACKUP/FUN/        (daily)"
echo "  backup-music      /mnt/SECONDARY/music/ → /mnt/DATA-FAST/Music/       (every 6h)"
echo "  backup-photos     /mnt/DATA-FAST/Photos/ → /mnt/SECONDARY/Photos/     (every 4 days)"
echo ""
echo "Commands:"
echo "  systemctl --user start backup-secondary   # run now"
echo "  systemctl --user stop backup-secondary     # stop"
echo "  systemctl --user list-timers 'backup-*'    # check schedules"
echo "  journalctl --user -u backup-secondary -f   # watch logs"
echo ""
echo "GNOME extension: restart shell to see the panel indicator."
