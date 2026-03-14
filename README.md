# Backup Monitor

Linux replacement for BvckUp2 — rsync-based backup with systemd scheduling and GNOME Shell panel integration.

## Architecture

```
backup-sync (bash)          — rsync wrapper with progress tracking & notifications
systemd user timers         — scheduling (replaces BvckUp2 scheduler)
GNOME Shell extension       — panel indicator with status, controls, schedule config
```

## Backup Jobs

| Job | Source | Destination | Schedule | Archive |
|-----|--------|-------------|----------|---------|
| `backup-secondary` | `/mnt/SECONDARY/` | `/mnt/DATA-SLOW/BACKUP/SECONDARY/` | Every 2 days | 60 days |
| `backup-fun` | `/mnt/FUN/` | `/mnt/DATA-SLOW/BACKUP/FUN/` | Daily | None |
| `backup-music` | `/mnt/SECONDARY/music/` | `/mnt/DATA-FAST/Music/` | Every 6 hours | None |
| `backup-photos` | `/mnt/DATA-FAST/Photos/` | `/mnt/SECONDARY/Photos/` | Every 4 days | None |

## Install

```bash
chmod +x install.sh
./install.sh
```

Then restart GNOME Shell (log out/in on Wayland, or Alt+F2 → `r` on X11).

## Uninstall

```bash
chmod +x uninstall.sh
./uninstall.sh
```

## Manual Commands

```bash
# Run a backup now
systemctl --user start backup-secondary

# Stop a running backup
systemctl --user stop backup-secondary

# Pause / resume
systemctl --user kill --signal=USR1 backup-secondary   # pause
systemctl --user kill --signal=USR2 backup-secondary   # resume

# Check timer schedule
systemctl --user list-timers 'backup-*'

# Watch live log
journalctl --user -u backup-secondary -f

# View backup logs
cat ~/.local/share/backup-sync/logs/backup-secondary.log
```

## GNOME Extension Features

- Panel icon with color-coded status (blue = running, yellow = paused, red = error)
- Per-job controls: Start, Stop, Pause/Resume
- Progress bar with speed and ETA
- Schedule info (last run, next run)
- Change timer frequency from the menu

## How It Works

1. **Scheduling**: systemd timers trigger `backup-sync` at configured intervals
2. **Sync**: `backup-sync` runs rsync with `--delete` (mirror mode) and tracks progress via `/proc/<pid>/io`
3. **Status**: Progress is written to JSON files in `~/.local/share/backup-sync/status/`
4. **Extension**: Polls status files every 3 seconds, updates the panel menu
5. **Signals**: SIGUSR1 pauses rsync (SIGSTOP), SIGUSR2 resumes (SIGCONT)
6. **Archive**: For `backup-secondary`, deleted/changed files are kept in `.archive/` with 60-day retention
7. **Notifications**: Desktop notifications on start, finish, pause, resume, and errors

## File Layout

```
~/.local/bin/backup-sync                              # sync script
~/.config/backup-sync/*.exclude                       # rsync exclude patterns
~/.config/systemd/user/backup-*.{service,timer}       # systemd units
~/.local/share/backup-sync/status/*.json              # runtime status
~/.local/share/backup-sync/logs/*.log                 # rsync logs
~/.local/share/gnome-shell/extensions/backup-monitor@petronijus/
```

## Ported from BvckUp2

Original Windows config was at `%LOCALAPPDATA%\Bvckup2\engine\backup-000{1,3,4,5}\settings.ini`.
Drive mapping: `E:` = SECONDARY, `F:` = FUN, `Z:` = DATA-SLOW, `Y:` = DATA-FAST.
