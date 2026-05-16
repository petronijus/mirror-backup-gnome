#!/usr/bin/env bash
# Install backup-monitor: script, configs, systemd units, GNOME extension + desktop app
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXT_UUID="backup-monitor@petronijus"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"

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

# 3. Data directories
mkdir -p "$HOME/.local/share/backup-sync/status"
mkdir -p "$HOME/.local/share/backup-sync/logs"
mkdir -p "$HOME/.local/share/backup-sync/history"

# 4. Systemd units
# If jobs.json already exists, it is authoritative — regenerate units from it
# AFTER the desktop app bundle is installed (step 6). Otherwise bootstrap from
# the bundled templates so the first-run migration in JobManager can pick them up.
mkdir -p "$HOME/.config/systemd/user"
JOBS_FILE="$HOME/.config/backup-sync/jobs.json"
if [ -f "$JOBS_FILE" ]; then
    echo "Existing jobs.json detected — will regenerate units after app install (step 9)."
    REGENERATE_FROM_JOBS=1
else
    echo "Bootstrapping systemd user units from templates (first install)..."
    for f in "$SCRIPT_DIR"/systemd/*; do
        install -Dm644 "$f" "$HOME/.config/systemd/user/$(basename "$f")"
    done
    systemctl --user daemon-reload
    REGENERATE_FROM_JOBS=0

    echo "Enabling backup timers..."
    for timer in backup-secondary.timer backup-fun.timer backup-music.timer backup-photos.timer; do
        systemctl --user enable --now "$timer"
        echo "  ✔ $timer enabled"
    done
fi

# 6. GNOME extension (includes bundled desktop app)
echo "Installing GNOME Shell extension + desktop app..."
mkdir -p "$EXT_DIR"

# Extension files
for f in "$SCRIPT_DIR"/gnome-extension/*; do
    install -Dm644 "$f" "$EXT_DIR/$(basename "$f")"
done

# Bundle the desktop app inside the extension at app/
rm -rf "$EXT_DIR/app"
cp -r "$SCRIPT_DIR/src" "$EXT_DIR/app"

# Bundle app data (CSS)
mkdir -p "$EXT_DIR/data"
cp "$SCRIPT_DIR"/data/style.css "$EXT_DIR/data/"

# 7. Desktop file (points to bundled app)
echo "Installing desktop launcher..."
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/com.github.petronijus.BackupMonitor.desktop" <<DEOF
[Desktop Entry]
Name=Backup Monitor
Comment=Monitor and manage rsync backups
Exec=bash -c 'PYTHONPATH="$EXT_DIR/app:\${PYTHONPATH:-}" exec python3 -m backup_monitor.main'
Icon=drive-harddisk-symbolic
Terminal=false
Type=Application
Categories=Utility;System;
Keywords=backup;rsync;sync;monitor;
StartupNotify=true
DEOF

# 8. Enable extension
if command -v gnome-extensions &>/dev/null; then
    gnome-extensions enable "$EXT_UUID" 2>/dev/null || true
    echo "  ✔ Extension enabled"
fi

# 9. Regenerate units from jobs.json (preserves user schedule edits across reinstall)
if [ "${REGENERATE_FROM_JOBS:-0}" = "1" ]; then
    echo "Regenerating systemd units from jobs.json..."
    PYTHONPATH="$EXT_DIR/app" python3 -m backup_monitor.main --regenerate-units
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "Everything is installed as a single GNOME extension."
echo "The desktop app is bundled inside the extension and launches from the panel menu."
echo ""
echo "Restart GNOME Shell to activate (log out/in on Wayland)."
echo ""
echo "Or launch the desktop app now:"
echo "  PYTHONPATH=\"$EXT_DIR/app\" python3 -m backup_monitor.main"
