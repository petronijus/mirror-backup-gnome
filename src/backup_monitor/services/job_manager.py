"""Job manager — CRUD for jobs.json, generates systemd units, handles migration."""

from __future__ import annotations

import json
import os
import re
import subprocess
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from backup_monitor.models.job import BackupJob, SYSTEMD_USER_DIR

JOBS_CONFIG_DIR = Path.home() / '.config' / 'backup-sync'
JOBS_FILE = JOBS_CONFIG_DIR / 'jobs.json'
EXCLUDE_DIR = JOBS_CONFIG_DIR
BACKUP_SYNC_BIN = Path.home() / '.local' / 'bin' / 'backup-sync'

DEFAULT_RSYNC_OPTIONS = {
    'delete_mode': 'before',   # before, during, after, disabled
    'compress': False,          # --compress (useful for remote/slow links)
    'checksum': False,          # --checksum (verify by content, not time+size)
    'hard_links': False,        # --hard-links (preserve hard links)
    'xattrs': False,            # --xattrs (preserve extended attributes)
    'acls': False,              # --acls (preserve ACLs)
    'partial': False,           # --partial (keep partially transferred files)
    'update': False,            # --update (skip files newer on destination)
    'max_size': '',             # --max-size (e.g. "500M", "2G")
    'min_size': '',             # --min-size (e.g. "1K")
}


class JobManager:
    """Manages backup job configuration, systemd unit generation, and persistence."""

    def __init__(self):
        self._jobs: list[dict] = []
        self._load_or_migrate()

    def _load_or_migrate(self):
        """Load jobs.json or migrate from existing systemd units on first run."""
        if JOBS_FILE.is_file():
            self._load()
        else:
            self._migrate_from_systemd()

    def _load(self):
        try:
            data = json.loads(JOBS_FILE.read_text())
            self._jobs = data.get('jobs', [])
        except (json.JSONDecodeError, OSError) as e:
            print(f'[BackupMonitor] Error loading jobs.json: {e}')
            self._jobs = []

    def _save(self):
        """Write jobs.json to disk."""
        JOBS_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            'version': 1,
            'jobs': self._jobs,
        }
        JOBS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')

    def _migrate_from_systemd(self):
        """First-run migration: read existing systemd units and create jobs.json."""
        discovered = BackupJob.discover_from_systemd()
        self._jobs = []
        for job in discovered:
            self._jobs.append({
                'id': job.id,
                'name': job.label,
                'source': job.source,
                'destination': job.destination,
                'exclude_file': job.exclude_file,
                'archive_days': job.archive_days,
                'description': job.description,
                'schedule': {
                    'type': 'calendar',
                    'expression': job.timer_schedule or 'daily',
                    'randomized_delay_sec': 0,
                },
                'bandwidth_limit_kbps': 0,
                'nice': 10,
                'io_priority': 7,
                'rsync_options': DEFAULT_RSYNC_OPTIONS.copy(),
                'notifications': {
                    'on_start': True,
                    'on_complete': True,
                    'on_error': True,
                },
                'enabled': True,
                'created': datetime.now().isoformat(),
            })
        self._save()

    @property
    def jobs(self) -> list[dict]:
        return self._jobs

    def get_job(self, job_id: str) -> Optional[dict]:
        for j in self._jobs:
            if j['id'] == job_id:
                return j
        return None

    def create_job(self, job_data: dict) -> str:
        """Create a new backup job. Returns the job ID."""
        # Generate ID from name
        job_id = 'backup-' + re.sub(r'[^a-z0-9]+', '-', job_data['name'].lower()).strip('-')

        # Ensure unique
        existing_ids = {j['id'] for j in self._jobs}
        base_id = job_id
        counter = 2
        while job_id in existing_ids:
            job_id = f'{base_id}-{counter}'
            counter += 1

        job = {
            'id': job_id,
            'name': job_data['name'],
            'source': job_data['source'].rstrip('/') + '/',
            'destination': job_data['destination'].rstrip('/') + '/',
            'exclude_file': job_data.get('exclude_file', ''),
            'archive_days': job_data.get('archive_days', 0),
            'description': job_data.get('description', f'Backup {job_data["name"]}'),
            'schedule': job_data.get('schedule', {
                'type': 'calendar',
                'expression': 'daily',
                'randomized_delay_sec': 0,
            }),
            'bandwidth_limit_kbps': job_data.get('bandwidth_limit_kbps', 0),
            'nice': job_data.get('nice', 10),
            'io_priority': job_data.get('io_priority', 7),
            'rsync_options': job_data.get('rsync_options', DEFAULT_RSYNC_OPTIONS.copy()),
            'notifications': job_data.get('notifications', {
                'on_start': True,
                'on_complete': True,
                'on_error': True,
            }),
            'enabled': True,
            'created': datetime.now().isoformat(),
        }

        self._jobs.append(job)
        self._save()
        self._generate_systemd_units(job)
        self._daemon_reload()

        if job['enabled'] and job['schedule']['type'] != 'manual':
            self._enable_timer(job['id'])

        return job_id

    def update_job(self, job_id: str, job_data: dict):
        """Update an existing backup job."""
        for i, j in enumerate(self._jobs):
            if j['id'] == job_id:
                # Preserve id, created
                job_data['id'] = job_id
                job_data['created'] = j.get('created', datetime.now().isoformat())
                if 'source' in job_data:
                    job_data['source'] = job_data['source'].rstrip('/') + '/'
                if 'destination' in job_data:
                    job_data['destination'] = job_data['destination'].rstrip('/') + '/'
                self._jobs[i] = job_data
                self._save()
                self._generate_systemd_units(job_data)
                self._daemon_reload()

                if job_data.get('enabled', True) and job_data.get('schedule', {}).get('type') != 'manual':
                    self._enable_timer(job_id)
                else:
                    self._disable_timer(job_id)
                return
        raise ValueError(f'Job not found: {job_id}')

    def delete_job(self, job_id: str):
        """Delete a backup job and its systemd units."""
        self._disable_timer(job_id)
        self._stop_service(job_id)
        self._remove_systemd_units(job_id)
        self._daemon_reload()

        self._jobs = [j for j in self._jobs if j['id'] != job_id]
        self._save()

    def toggle_job(self, job_id: str, enabled: bool):
        """Enable or disable a job's timer."""
        for j in self._jobs:
            if j['id'] == job_id:
                j['enabled'] = enabled
                self._save()
                if enabled and j.get('schedule', {}).get('type') != 'manual':
                    self._enable_timer(job_id)
                else:
                    self._disable_timer(job_id)
                return

    def to_backup_jobs(self) -> list[BackupJob]:
        """Convert stored job dicts to BackupJob model objects."""
        result = []
        for j in self._jobs:
            schedule = j.get('schedule', {})
            result.append(BackupJob(
                id=j['id'],
                label=j['name'],
                service_name=f'{j["id"]}.service',
                source=j.get('source', ''),
                destination=j.get('destination', ''),
                exclude_file=j.get('exclude_file', ''),
                archive_days=j.get('archive_days', 0),
                description=j.get('description', ''),
                timer_schedule=schedule.get('expression', ''),
            ))
        return result

    # ── systemd unit generation ──

    def _generate_systemd_units(self, job: dict):
        """Write .service and .timer files for a job."""
        SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
        job_id = job['id']

        # Service file
        exclude = job.get('exclude_file', '')
        archive = job.get('archive_days', 0)
        exclude_arg = exclude if exclude else '""'
        bwlimit = job.get('bandwidth_limit_kbps', 0)

        # Build environment lines for rsync options
        env_vars = []
        if bwlimit and bwlimit > 0:
            env_vars.append(f'Environment=BACKUP_SYNC_BWLIMIT={bwlimit}')

        rsync_opts = job.get('rsync_options', {})
        bool_flags = [
            ('compress', 'BACKUP_SYNC_COMPRESS'),
            ('checksum', 'BACKUP_SYNC_CHECKSUM'),
            ('hard_links', 'BACKUP_SYNC_HARD_LINKS'),
            ('xattrs', 'BACKUP_SYNC_XATTRS'),
            ('acls', 'BACKUP_SYNC_ACLS'),
            ('partial', 'BACKUP_SYNC_PARTIAL'),
            ('update', 'BACKUP_SYNC_UPDATE'),
        ]
        for key, env_name in bool_flags:
            if rsync_opts.get(key, False):
                env_vars.append(f'Environment={env_name}=1')

        delete_mode = rsync_opts.get('delete_mode', 'before')
        if delete_mode != 'before':
            env_vars.append(f'Environment=BACKUP_SYNC_DELETE_MODE={delete_mode}')

        if rsync_opts.get('max_size'):
            env_vars.append(f'Environment=BACKUP_SYNC_MAX_SIZE={rsync_opts["max_size"]}')
        if rsync_opts.get('min_size'):
            env_vars.append(f'Environment=BACKUP_SYNC_MIN_SIZE={rsync_opts["min_size"]}')

        env_lines = '\n'.join(env_vars) + '\n' if env_vars else ''

        nice = job.get('nice', 10)
        io_prio = job.get('io_priority', 7)
        desc = job.get('description', f'Backup {job["name"]}')

        # Check if job needs network (source or dest starts with remote-like path)
        needs_network = False  # For now, all local

        service_content = f"""[Unit]
Description={desc}
{"Wants=network-online.target" if needs_network else ""}
{"After=network-online.target" if needs_network else ""}

[Service]
Type=simple
{env_lines}ExecStart=%h/.local/bin/backup-sync {job_id} {job['source']} {job['destination']} {exclude_arg} {archive}
KillSignal=SIGTERM
KillMode=mixed
TimeoutStopSec=30
Nice={nice}
IOSchedulingClass=best-effort
IOSchedulingPriority={io_prio}

[Install]
WantedBy=default.target
"""
        # Clean up empty lines from conditional sections
        service_content = re.sub(r'\n{3,}', '\n\n', service_content)
        service_path = SYSTEMD_USER_DIR / f'{job_id}.service'
        service_path.write_text(service_content)

        # Timer file
        schedule = job.get('schedule', {})
        sched_type = schedule.get('type', 'calendar')

        if sched_type != 'manual':
            expression = schedule.get('expression', 'daily')

            timer_content = f"""[Unit]
Description={desc} (timer)

[Timer]
OnCalendar={expression}
Persistent=true

[Install]
WantedBy=timers.target
"""
            timer_path = SYSTEMD_USER_DIR / f'{job_id}.timer'
            timer_path.write_text(timer_content)

    def _remove_systemd_units(self, job_id: str):
        """Remove .service and .timer files."""
        for suffix in ('.service', '.timer'):
            path = SYSTEMD_USER_DIR / f'{job_id}{suffix}'
            path.unlink(missing_ok=True)

    def _daemon_reload(self):
        subprocess.run(
            ['systemctl', '--user', 'daemon-reload'],
            capture_output=True, timeout=10,
        )

    def _enable_timer(self, job_id: str):
        subprocess.run(
            ['systemctl', '--user', 'enable', '--now', f'{job_id}.timer'],
            capture_output=True, timeout=10,
        )

    def _disable_timer(self, job_id: str):
        subprocess.run(
            ['systemctl', '--user', 'disable', '--now', f'{job_id}.timer'],
            capture_output=True, timeout=10,
        )

    def _stop_service(self, job_id: str):
        subprocess.run(
            ['systemctl', '--user', 'stop', f'{job_id}.service'],
            capture_output=True, timeout=10,
        )


# ── Exclusion file helpers ──

def read_exclusions(exclude_file: str) -> list[dict]:
    """Read an exclude file and return list of {pattern, enabled, comment}."""
    if not exclude_file or not Path(exclude_file).is_file():
        return []

    entries = []
    for line in Path(exclude_file).read_text().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#'):
            # Check if it's a commented-out pattern (disabled)
            pattern = stripped.lstrip('#').strip()
            if pattern and not pattern.startswith(' '):
                entries.append({'pattern': pattern, 'enabled': False})
            # Skip pure comments
        else:
            entries.append({'pattern': stripped, 'enabled': True})
    return entries


def write_exclusions(exclude_file: str, entries: list[dict]):
    """Write exclusion entries back to the exclude file."""
    path = Path(exclude_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for entry in entries:
        if entry.get('enabled', True):
            lines.append(entry['pattern'])
        else:
            lines.append(f'# {entry["pattern"]}')
    path.write_text('\n'.join(lines) + '\n')


DEFAULT_EXCLUDES = """\
# Exclude patterns for rsync (one per line)

# Windows system directories (typically inaccessible from Linux)
$RECYCLE.BIN
System Volume Information
WpSystem
"""


def create_exclude_file(job_id: str) -> str:
    """Create a new exclude file with sensible defaults and return its path."""
    path = EXCLUDE_DIR / f'{job_id}.exclude'
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_EXCLUDES)
    return str(path)
