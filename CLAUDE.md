# Mirror Backup for GNOME

Linux rsync backup system: `scripts/backup-sync` (bash) + systemd user timers +
GNOME Shell extension (`gnome-extension/`) + GTK4/libadwaita app
(`src/backup_monitor/`). `~/.config/backup-sync/jobs.json` is the source of
truth; the app generates systemd units from it. See README for architecture.

## Repo conventions (public repo)

- Conventional commits: `feat:` / `fix:` / `chore:` / `docs:` / `refactor:`.
- Releases are cut with the `repo-release` skill; config in `.release.yml`.
  Never tag or edit CHANGELOG.md manually. App version lives in
  `src/backup_monitor/__init__.py` (`APP_VERSION`); `metadata.json` `version`
  is the separate e.g.o integer — bump when extension content changes.
- Private overlay: `private/` (gitignored) = clone of
  `petronijus/mirror-backup-gnome-private` — Petr's real job units + excludes.
  `install.sh` bootstraps jobs from `private/configs/systemd/` when present.
  Bootstrap: `git clone git@github.com:petronijus/mirror-backup-gnome-private.git private`
