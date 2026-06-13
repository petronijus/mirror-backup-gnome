# Changelog

All notable changes to Mirror Backup for GNOME. Format follows
[Keep a Changelog](https://keepachangelog.com/), versioning follows
[SemVer](https://semver.org/) (0.x = no stability promises).

## [Unreleased]

## [0.5.1] - 2026-06-13
### Changed
- Renamed to **Mirror Backup for GNOME** (was "Backup Monitor") with the tagline
  "Scheduled rsync mirroring, watched live from your GNOME panel". Display names,
  README and repo renamed; technical identifiers (extension UUID, `backup-sync`
  config paths, desktop file id) are unchanged, so existing installs keep working.

## [0.5.0] - 2026-06-12

First public release.

### Changed
- `install.sh` no longer ships or auto-enables any backup jobs — a fresh
  install starts clean and you create jobs in the desktop app. (Previously the
  installer bundled the author's personal job units and enabled their timers.)
- Extension zip no longer bundles systemd unit templates; units are generated
  from `jobs.json` by the app.

### Added
- MIT LICENSE, changelog, CI release pipeline (tag → extension zip + source
  tarball on GitHub Releases)
- `config/example.exclude` — generic rsync exclude template

## [0.4.1] - 2026-05-16
### Fixed
- User schedule edits survive reinstall (existing `jobs.json` is authoritative;
  units regenerate from it after the app bundle is installed)

## [0.4.0] - 2026-05-09
### Added
- Persistent failure escalation, run-history rotation, suggested excludes

## [0.3.2] - 2026-05-09
### Fixed
- Daily job failing on a Windows-ACL'd file

## [0.3.1] - 2026-04-12
### Fixed
- UI flickering — status JSON now written atomically (temp file + rename)

## [0.3.0] - 2026-04-12
### Added
- Job queue (`flock` — one backup at a time, others wait as "queued")
- Default excludes for Windows system dirs on NTFS mounts
### Changed
- rsync exit codes 23/24 (partial transfer) treated as success with warnings

## [0.2.0] - 2026-03-31
### Added
- Build system (`build.sh`: extension zip + source tarball), self-setup

## [0.1.0] - 2026-03

Initial version: rsync wrapper with progress tracking, systemd user timers,
GNOME Shell panel indicator, GTK4/libadwaita desktop app.
