# Backup Monitor

Linux replacement for BvckUp2 — rsync-based backup with systemd scheduling, GNOME Shell panel integration, and a GTK4/libadwaita desktop app.

## Components

```
backup-sync (bash)          — rsync wrapper with progress tracking, job queue & notifications
systemd user timers         — scheduling (persistent, survives reboots)
GNOME Shell extension       — panel indicator with live status, controls
Desktop app (GTK4)          — job management, configuration, history, logs
```

## Desktop App

The GTK4/libadwaita desktop app provides full backup management:

### Dashboard
- Real-time status cards for all backup jobs
- Progress bars with speed, ETA, file counts
- Next scheduled run and last trigger times
- Start/Pause/Resume/Stop controls
- Click card → detail page, edit pencil → job editor

### Job Management
- Create, edit, delete backup jobs from the UI
- Source/destination folder pickers
- Schedule presets (daily, every N hours, weekly, custom calendar expression, manual)
- Visual exclusion pattern editor (add/remove/toggle patterns)
- Jobs stored in `~/.config/backup-sync/jobs.json`
- Generates systemd service+timer units on save

### Advanced Rsync Options (per job)
- **Delete mode**: before/during/after transfer, or disabled (additive backup)
- **Compression**: compress data during transfer (useful for slow links)
- **Checksum verification**: compare by content instead of time+size
- **Hard links**: detect and preserve hard links
- **Extended attributes**: preserve xattrs
- **ACLs**: preserve filesystem access control lists
- **Partial transfers**: resume interrupted file transfers
- **Skip newer**: don't overwrite newer files on destination
- **File size filters**: max-size and min-size limits
- **Bandwidth limiting**: throttle transfer speed (KB/s)
- **Archive retention**: keep deleted/changed files for N days

### History & Logs
- Per-job run history with duration, file counts, exit codes
- Statistics: success rate, average duration, last success/failure
- Full log viewer with search highlighting and auto-tail
- History stored as JSONL in `~/.local/share/backup-sync/history/`

### Preferences
- Notification settings (on start, complete, error)
- Default values for new jobs (archive, bandwidth, nice, I/O priority)
- Default rsync options for new jobs
- Log retention settings

### Other
- Dry-run preview (see what would change without transferring)
- Keyboard shortcuts (Ctrl+N, Ctrl+R, Ctrl+,)
- About dialog
- Job queue: backups run one at a time (flock-based), "Queued" state visible in UI

### Launch

```bash
./run.sh
```

## GNOME Shell Extension

- Panel icon with color-coded status (blue = running, yellow = paused, red = error, gray = queued)
- Per-job controls: Start, Stop, Pause/Resume
- Progress bar with speed and ETA
- Pulsing icon when backups are active

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

# View backup logs
cat ~/.local/share/backup-sync/logs/backup-secondary.log
```

## How It Works

1. **Scheduling**: systemd timers trigger `backup-sync` at configured intervals
2. **Queue**: `flock` ensures only one backup runs at a time; others wait in "queued" state
3. **Sync**: `backup-sync` runs rsync with configurable options and tracks progress
4. **Status**: Progress written to JSON files in `~/.local/share/backup-sync/status/`
5. **History**: Each completed run appends to `~/.local/share/backup-sync/history/*.jsonl`
6. **Extension**: Polls status files every 3 seconds, updates the panel menu
7. **Desktop app**: Polls at 1 second + inotify for instant updates
8. **Signals**: SIGUSR1 pauses rsync (SIGSTOP), SIGUSR2 resumes (SIGCONT)
9. **Archive**: Deleted/changed files kept in `.archive/` with configurable retention
10. **Notifications**: Desktop notifications on start, finish, pause, resume, and errors

## File Layout

```
~/.local/bin/backup-sync                              # sync script
~/.config/backup-sync/jobs.json                       # job configuration (source of truth)
~/.config/backup-sync/settings.json                   # app preferences
~/.config/backup-sync/*.exclude                       # rsync exclude patterns
~/.config/systemd/user/backup-*.{service,timer}       # systemd units (generated by app)
~/.local/share/backup-sync/status/*.json              # runtime status
~/.local/share/backup-sync/status/backup-sync.lock    # job queue lock file
~/.local/share/backup-sync/history/*.jsonl             # run history
~/.local/share/backup-sync/logs/*.log                 # rsync logs
~/.local/share/gnome-shell/extensions/backup-monitor@petronijus/
```

## Ported from BvckUp2

Original Windows config was at `%LOCALAPPDATA%\Bvckup2\engine\backup-000{1,3,4,5}\settings.ini`.
Drive mapping: `E:` = SECONDARY, `F:` = FUN, `Z:` = DATA-SLOW, `Y:` = DATA-FAST.
