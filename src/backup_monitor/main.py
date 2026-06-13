"""Mirror Backup for GNOME — GTK4/libadwaita desktop app for managing rsync backups."""

from __future__ import annotations

import sys
import os
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, Gio, GLib

from backup_monitor import APP_ID
from backup_monitor.window import BackupMonitorWindow


class BackupMonitorApp(Adw.Application):
    """Main application class."""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_css()

    def do_activate(self):
        win = self.get_active_window()
        if win:
            win.present()
            return

        win = BackupMonitorWindow(self)
        win.present()

    def _load_css(self):
        """Load custom CSS from data/style.css."""
        # __file__ = .../backup_monitor/main.py
        # In dev:    repo/src/backup_monitor/main.py → repo/data/style.css
        # Bundled:   ext_dir/app/backup_monitor/main.py → ext_dir/data/style.css
        # Both resolve via: parent(main.py) / .. / .. / data / style.css
        css_paths = [
            Path(__file__).parent.parent.parent / 'data' / 'style.css',
        ]
        for css_path in css_paths:
            if css_path.is_file():
                provider = Gtk.CssProvider()
                provider.load_from_path(str(css_path))
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display, provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                    )
                break


def _regenerate_units() -> int:
    """Rewrite all .timer/.service units from jobs.json (authoritative)."""
    from backup_monitor.services.job_manager import JobManager

    mgr = JobManager()
    jobs = mgr.jobs
    if not jobs:
        print('[regenerate-units] No jobs in jobs.json — nothing to do.')
        return 0

    for job in jobs:
        mgr._generate_systemd_units(job)
        print(f"[regenerate-units] wrote {job['id']}.service + .timer "
              f"({job.get('schedule', {}).get('expression', '?')})")

    mgr._daemon_reload()

    for job in jobs:
        if job.get('enabled', True):
            mgr._enable_timer(job['id'])
        else:
            mgr._disable_timer(job['id'])

    print(f'[regenerate-units] done — {len(jobs)} job(s) regenerated.')
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--regenerate-units':
        return _regenerate_units()
    app = BackupMonitorApp()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
