"""Async systemctl --user wrapper using Gio.Subprocess."""

from __future__ import annotations

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib


def _run_systemctl(args: list[str], callback=None):
    """Run systemctl --user with given args asynchronously."""
    try:
        proc = Gio.Subprocess.new(
            ['systemctl', '--user', *args],
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE,
        )
        proc.communicate_utf8_async(None, None, _on_done, callback)
    except GLib.Error as e:
        print(f'[BackupMonitor] systemctl error: {e.message}')
        if callback:
            callback('', str(e))


def _on_done(proc, result, callback):
    try:
        _, stdout, stderr = proc.communicate_utf8_finish(result)
        if callback:
            callback(stdout.strip() if stdout else '', None)
    except GLib.Error as e:
        if callback:
            callback('', str(e))


def start_job(service_name: str):
    """Start a backup service."""
    _run_systemctl(['start', service_name])


def stop_job(service_name: str, is_paused: bool = False):
    """Stop a backup service. If paused, resume first so rsync can clean up."""
    if is_paused:
        _run_systemctl(['kill', '--signal=USR2', service_name])
    _run_systemctl(['stop', service_name])


def pause_job(service_name: str):
    """Send SIGUSR1 to pause rsync."""
    _run_systemctl(['kill', '--signal=USR1', service_name])


def resume_job(service_name: str):
    """Send SIGUSR2 to resume rsync."""
    _run_systemctl(['kill', '--signal=USR2', service_name])


def get_timer_info(timer_name: str, callback):
    """Get next trigger time and last trigger time for a timer.

    callback(next_run: str, last_run: str, error: str | None)
    """
    _run_systemctl(
        ['show', timer_name,
         '--property=NextElapseUSecRealtime',
         '--property=LastTriggerUSec'],
        lambda stdout, err: _parse_timer_info(stdout, err, callback),
    )


def _parse_timer_info(stdout: str, error, callback):
    if error:
        callback('', '', error)
        return

    next_run = ''
    last_run = ''
    for line in stdout.splitlines():
        if line.startswith('NextElapseUSecRealtime='):
            val = line.split('=', 1)[1].strip()
            if val and val != 'n/a':
                next_run = _format_timestamp(val)
        elif line.startswith('LastTriggerUSec='):
            val = line.split('=', 1)[1].strip()
            if val and val != 'n/a':
                last_run = _format_timestamp(val)
    callback(next_run, last_run, None)


def get_all_timer_info(timer_names: list[str], callback):
    """Get timer info for multiple timers. callback(dict[timer_name, (next, last)])"""
    results = {}
    remaining = [len(timer_names)]

    if not timer_names:
        callback({})
        return

    def on_one(timer_name, next_run, last_run, err):
        results[timer_name] = (next_run, last_run)
        remaining[0] -= 1
        if remaining[0] <= 0:
            callback(results)

    for name in timer_names:
        get_timer_info(
            name,
            lambda nr, lr, e, n=name: on_one(n, nr, lr, e),
        )


def _format_timestamp(systemd_ts: str) -> str:
    """Convert systemd timestamp like 'Thu 2026-03-27 18:00:00 CET' to a readable form."""
    # systemd outputs like: "Thu 2026-03-27 18:00:00 CET"
    # We want to show a relative-friendly format
    parts = systemd_ts.split()
    if len(parts) >= 3:
        # Return "Thu 18:00" or "Thu Mar 27 18:00" depending on context
        day_name = parts[0]
        date_part = parts[1]  # 2026-03-27
        time_part = parts[2]  # 18:00:00

        # Parse to check if it's today/tomorrow
        try:
            from datetime import datetime
            dt = datetime.strptime(f'{date_part} {time_part}', '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            diff = (dt.date() - now.date()).days

            time_short = dt.strftime('%H:%M')
            if diff == 0:
                return f'Today {time_short}'
            elif diff == 1:
                return f'Tomorrow {time_short}'
            elif diff < 7:
                return f'{day_name} {time_short}'
            else:
                return f'{dt.strftime("%b %d")} {time_short}'
        except (ValueError, ImportError):
            return systemd_ts
    return systemd_ts
