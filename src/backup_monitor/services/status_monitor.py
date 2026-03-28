"""Status monitor — polls JSON status files and emits signals on change."""

from __future__ import annotations

import gi
gi.require_version('Gio', '2.0')
from gi.repository import GLib, Gio, GObject

from backup_monitor.models.job import BackupJob, STATUS_DIR
from backup_monitor.services import systemd_service


class StatusMonitor(GObject.Object):
    """Periodically reads backup status files and timer info, emits 'updated' signal."""

    __gsignals__ = {
        'updated': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    POLL_INTERVAL_MS = 1000
    TIMER_POLL_INTERVAL_S = 30  # Timer info changes slowly, poll less often

    def __init__(self, jobs: list[BackupJob]):
        super().__init__()
        self._jobs = jobs
        self._poll_id = None
        self._timer_poll_id = None
        self._file_monitor = None

    @property
    def jobs(self) -> list[BackupJob]:
        return self._jobs

    def start(self):
        """Start polling and file monitoring."""
        self._refresh_statuses()
        self._refresh_timer_info()

        self._poll_id = GLib.timeout_add(
            self.POLL_INTERVAL_MS, self._on_poll)

        self._timer_poll_id = GLib.timeout_add_seconds(
            self.TIMER_POLL_INTERVAL_S, self._on_timer_poll)

        # Also watch the status directory with inotify for instant updates
        try:
            status_dir = Gio.File.new_for_path(str(STATUS_DIR))
            self._file_monitor = status_dir.monitor_directory(
                Gio.FileMonitorFlags.NONE, None)
            self._file_monitor.connect('changed', self._on_file_changed)
        except GLib.Error:
            pass  # Polling is the fallback

    def stop(self):
        """Stop all monitoring."""
        if self._poll_id:
            GLib.source_remove(self._poll_id)
            self._poll_id = None
        if self._timer_poll_id:
            GLib.source_remove(self._timer_poll_id)
            self._timer_poll_id = None
        if self._file_monitor:
            self._file_monitor.cancel()
            self._file_monitor = None

    def _on_poll(self) -> bool:
        self._refresh_statuses()
        return GLib.SOURCE_CONTINUE

    def _on_timer_poll(self) -> bool:
        self._refresh_timer_info()
        return GLib.SOURCE_CONTINUE

    def _on_file_changed(self, monitor, file, other_file, event_type):
        if event_type in (Gio.FileMonitorEvent.CHANGED, Gio.FileMonitorEvent.CREATED):
            self._refresh_statuses()

    def _refresh_statuses(self):
        for job in self._jobs:
            job.read_status()
        self.emit('updated')

    def _refresh_timer_info(self):
        timer_names = [f'{j.id}.timer' for j in self._jobs]
        systemd_service.get_all_timer_info(timer_names, self._on_timer_info)

    def _on_timer_info(self, results: dict):
        for job in self._jobs:
            timer_name = f'{job.id}.timer'
            if timer_name in results:
                next_run, last_run = results[timer_name]
                job.next_run = next_run
                job.last_run = last_run
        self.emit('updated')
