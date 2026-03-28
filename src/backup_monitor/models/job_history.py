"""Job history model — reads JSONL history files written by backup-sync."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

HISTORY_DIR = Path.home() / '.local' / 'share' / 'backup-sync' / 'history'


@dataclass
class HistoryEntry:
    started: str
    finished: str
    duration_sec: int
    exit_code: int
    files_transferred: int
    files_total: int
    error: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def duration_formatted(self) -> str:
        d = self.duration_sec
        if d < 60:
            return f'{d}s'
        if d < 3600:
            return f'{d // 60}m {d % 60}s'
        h = d // 3600
        m = (d % 3600) // 60
        return f'{h}h {m}m'

    @property
    def started_datetime(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.started)
        except (ValueError, TypeError):
            return None

    @property
    def started_relative(self) -> str:
        """Human-readable relative time like '2 hours ago', 'Yesterday 14:30'."""
        dt = self.started_datetime
        if not dt:
            return self.started
        now = datetime.now()
        diff = now - dt

        if diff < timedelta(minutes=1):
            return 'Just now'
        if diff < timedelta(hours=1):
            m = int(diff.total_seconds() // 60)
            return f'{m}m ago'
        if diff < timedelta(hours=24) and dt.date() == now.date():
            return f'Today {dt.strftime("%H:%M")}'
        if diff < timedelta(hours=48) and (now.date() - dt.date()).days == 1:
            return f'Yesterday {dt.strftime("%H:%M")}'
        if diff < timedelta(days=7):
            return dt.strftime('%a %H:%M')
        return dt.strftime('%b %d %H:%M')


@dataclass
class HistoryStats:
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    avg_duration_sec: float
    last_success: str
    last_failure: str

    @property
    def avg_duration_formatted(self) -> str:
        d = int(self.avg_duration_sec)
        if d < 60:
            return f'{d}s'
        if d < 3600:
            return f'{d // 60}m {d % 60}s'
        h = d // 3600
        m = (d % 3600) // 60
        return f'{h}h {m}m'


def read_history(job_id: str, limit: int = 50) -> list[HistoryEntry]:
    """Read history entries for a job, newest first."""
    path = HISTORY_DIR / f'{job_id}.jsonl'
    if not path.is_file():
        return []

    entries = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                entries.append(HistoryEntry(
                    started=data.get('started', ''),
                    finished=data.get('finished', ''),
                    duration_sec=data.get('duration_sec', 0),
                    exit_code=data.get('exit_code', -1),
                    files_transferred=data.get('files_transferred', 0),
                    files_total=data.get('files_total', 0),
                    error=data.get('error', ''),
                ))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []

    # Newest first
    entries.reverse()
    return entries[:limit]


def compute_stats(entries: list[HistoryEntry]) -> HistoryStats:
    """Compute aggregate statistics from history entries."""
    if not entries:
        return HistoryStats(0, 0, 0, 0.0, 0.0, '', '')

    total = len(entries)
    successful = [e for e in entries if e.success]
    failed = [e for e in entries if not e.success]

    avg_dur = sum(e.duration_sec for e in entries) / total if total else 0
    success_rate = len(successful) / total * 100 if total else 0

    last_success = successful[0].started_relative if successful else 'Never'
    last_failure = failed[0].started_relative if failed else 'Never'

    return HistoryStats(
        total_runs=total,
        successful_runs=len(successful),
        failed_runs=len(failed),
        success_rate=success_rate,
        avg_duration_sec=avg_dur,
        last_success=last_success,
        last_failure=last_failure,
    )
