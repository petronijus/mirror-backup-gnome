# Mirror Backup for GNOME

> Scheduled rsync mirroring, watched live from your GNOME panel.

Rsync-based backup for Linux with systemd scheduling, a GNOME Shell panel indicator, and a GTK4/libadwaita desktop app — set up jobs once, watch them in the corner of your eye.

## Screenshots

<!-- Capture on a GNOME session: gnome-screenshot -w (window) into docs/screenshots/ -->
| Dashboard | Job editor | Panel indicator |
|---|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Job editor](docs/screenshots/job-editor.png) | ![Panel indicator](docs/screenshots/panel.png) |

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
- Live countdown to next scheduled run (e.g. "in 2h 15m"), relative last-run time
- Start/Pause/Resume/Stop controls
- Click card → detail page, edit pencil → job editor

### Job Management
- Create, edit, delete backup jobs from the UI
- Source/destination folder pickers
- Visual schedule editor:
  - **Weekly**: weekday pill buttons (multi-select), interval spinner ("every N weeks")
  - **Monthly**: day-of-month picker, interval spinner ("every N months")
  - **Time**: clean HH:MM display with ±30min step buttons
  - **Custom**: raw systemd calendar expression
  - **Manual**: no automatic scheduling
  - Human-readable summary (e.g. "Every week on Mon, Wed, Fri at 22:00")
  - Daily = weekly with all 7 days selected
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
- Live countdown to next run per job
- Pulsing icon when backups are active
- "Open Mirror Backup" button to launch the desktop app

## Backup Jobs

Jobs are created and managed in the desktop app and stored in
`~/.config/backup-sync/jobs.json` (the source of truth — systemd units are
generated from it). A typical setup looks like:

| Job | Source | Destination | Schedule | Archive |
|-----|--------|-------------|----------|---------|
| `backup-data` | `/mnt/DATA/` | `/mnt/BACKUP/DATA/` | Every 2 days | 60 days |
| `backup-music` | `/mnt/DATA/music/` | `/mnt/FAST/Music/` | Every 6 hours | None |
| `backup-photos` | `/mnt/FAST/Photos/` | `/mnt/DATA/Photos/` | Every 4 days | None |

## Install

**From a release** (recommended): download the extension zip from
[Releases](../../releases) and

```bash
gnome-extensions install --force backup-monitor@petronijus.zip
```

**From source**:

```bash
chmod +x install.sh
./install.sh
```

Then restart GNOME Shell (log out/in on Wayland, or Alt+F2 → `r` on X11) and
create your backup jobs in the desktop app (panel menu → Open Mirror Backup).

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

## Error Handling

- **Partial transfer tolerance**: rsync exit codes 23 (permission denied on some files) and 24 (files vanished during transfer) are treated as success with warnings, not failures. This prevents backup jobs from showing as "error" due to a single inaccessible file (e.g. Windows system files on NTFS mounts).
- **Default excludes**: new exclude files include `$RECYCLE.BIN`, `System Volume Information`, and `WpSystem` by default — common Windows system directories that are inaccessible or irrelevant on Linux.
- **Interrupted backups**: if a backup is killed (e.g. by system shutdown), the EXIT trap marks it as "error" with "Backup interrupted" message.
- **Atomic status writes**: status JSON is written to a temp file and renamed into place (`mv -f`), preventing UI flickering caused by readers seeing a partially written or truncated file.

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

## Releases

Everything ships as a single GNOME Shell extension with the desktop app
bundled inside. Tags `vX.Y.Z` build two artifacts in CI and attach them to the
GitHub release:

- `backup-monitor@petronijus.zip` — the extension, installable with
  `gnome-extensions install --force <zip>` (no root needed; log out/in to
  activate). Includes the panel indicator, the bundled GTK4 app and the
  `backup-sync` script.
- `mirror-backup-gnome-vX.Y.Z.tar.gz` — source tarball for `./install.sh` installs.

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

[MIT](LICENSE)
