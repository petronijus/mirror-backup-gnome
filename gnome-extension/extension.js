import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const JOBS = [
    {id: 'backup-secondary', label: 'SECONDARY', service: 'backup-secondary.service', timer: 'backup-secondary.timer'},
    {id: 'backup-fun',       label: 'FUN',       service: 'backup-fun.service',       timer: 'backup-fun.timer'},
    {id: 'backup-music',     label: 'Music',     service: 'backup-music.service',     timer: 'backup-music.timer'},
    {id: 'backup-photos',    label: 'Photos',    service: 'backup-photos.service',    timer: 'backup-photos.timer'},
];

const SCHEDULE_PRESETS = [
    {label: 'Every 6 hours',  calendar: '0/6:00:00'},
    {label: 'Every 12 hours', calendar: '0/12:00:00'},
    {label: 'Daily',          calendar: 'daily'},
    {label: 'Every 2 days',   calendar: '*-*-1/2 11:00:00'},
    {label: 'Every 4 days',   calendar: '*-*-1/4 22:00:00'},
    {label: 'Weekly',         calendar: 'weekly'},
];

const STATUS_DIR = GLib.build_filenamev([GLib.get_home_dir(), '.local', 'share', 'backup-sync', 'status']);

function _runSystemctl(args) {
    try {
        const proc = Gio.Subprocess.new(
            ['systemctl', '--user', ...args],
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
        );
        const [, stdout] = proc.communicate_utf8(null, null);
        return stdout?.trim() ?? '';
    } catch (e) {
        log(`[BackupMonitor] systemctl error: ${e.message}`);
        return '';
    }
}

function _runSystemctlAsync(args, callback) {
    try {
        const proc = Gio.Subprocess.new(
            ['systemctl', '--user', ...args],
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
        );
        proc.communicate_utf8_async(null, null, (_proc, res) => {
            try {
                const [, stdout] = _proc.communicate_utf8_finish(res);
                if (callback) callback(stdout?.trim() ?? '', null);
            } catch (e) {
                if (callback) callback('', e);
            }
        });
    } catch (e) {
        log(`[BackupMonitor] systemctl async error: ${e.message}`);
        if (callback) callback('', e);
    }
}

function _readStatusFile(jobId) {
    const path = GLib.build_filenamev([STATUS_DIR, `${jobId}.json`]);
    try {
        const [ok, contents] = GLib.file_get_contents(path);
        if (ok) {
            return JSON.parse(new TextDecoder().decode(contents));
        }
    } catch (_e) {
        // File doesn't exist or invalid JSON — normal for first run
    }
    return null;
}

class BackupJobSection {
    constructor(ext, job, menu) {
        this._ext = ext;
        this._job = job;
        this._paused = false;
        this._status = null;

        // --- Header item: icon + name + state ---
        this._headerItem = new PopupMenu.PopupBaseMenuItem({reactive: false});
        this._headerBox = new St.BoxLayout({vertical: false, x_expand: true, style_class: 'backup-job-header'});

        this._stateIcon = new St.Icon({
            icon_name: 'media-record-symbolic',
            icon_size: 12,
            style: 'color: #aaa; margin-right: 8px; margin-top: 2px;',
        });
        this._headerBox.add_child(this._stateIcon);

        this._nameLabel = new St.Label({text: job.label, x_expand: true});
        this._headerBox.add_child(this._nameLabel);

        this._stateLabel = new St.Label({text: 'idle', style_class: 'backup-state-idle'});
        this._headerBox.add_child(this._stateLabel);

        this._headerItem.add_child(this._headerBox);
        menu.addMenuItem(this._headerItem);

        // --- Progress bar ---
        this._progressItem = new PopupMenu.PopupBaseMenuItem({reactive: false});
        this._progressBox = new St.BoxLayout({vertical: true, x_expand: true});

        this._progressBarOuter = new St.BoxLayout({style_class: 'backup-progress-bar', x_expand: true});
        this._progressBarFill = new St.Widget({style_class: 'backup-progress-fill', x_expand: false});
        this._progressBarOuter.add_child(this._progressBarFill);
        this._progressBox.add_child(this._progressBarOuter);

        this._detailLabel = new St.Label({text: '', style_class: 'backup-job-detail'});
        this._progressBox.add_child(this._detailLabel);

        this._progressItem.add_child(this._progressBox);
        menu.addMenuItem(this._progressItem);
        this._progressItem.visible = false;

        // --- Schedule info ---
        this._scheduleItem = new PopupMenu.PopupBaseMenuItem({reactive: false});
        this._scheduleLabel = new St.Label({text: '', style_class: 'backup-job-detail'});
        this._scheduleItem.add_child(this._scheduleLabel);
        menu.addMenuItem(this._scheduleItem);

        // --- Buttons ---
        this._btnItem = new PopupMenu.PopupBaseMenuItem({reactive: false});
        this._btnBox = new St.BoxLayout({style: 'padding-left: 20px;'});

        this._startBtn = this._makeButton('▶ Start', 'backup-btn backup-btn-start', () => this._onStart());
        this._stopBtn = this._makeButton('⏹ Stop', 'backup-btn backup-btn-stop', () => this._onStop());
        this._pauseBtn = this._makeButton('⏸ Pause', 'backup-btn backup-btn-pause', () => this._onPause());

        this._btnBox.add_child(this._startBtn);
        this._btnBox.add_child(this._pauseBtn);
        this._btnBox.add_child(this._stopBtn);

        this._btnItem.add_child(this._btnBox);
        menu.addMenuItem(this._btnItem);

        // --- Schedule submenu ---
        this._schedSubMenu = new PopupMenu.PopupSubMenuMenuItem('Schedule');
        for (const preset of SCHEDULE_PRESETS) {
            const item = new PopupMenu.PopupMenuItem(preset.label, {style_class: 'backup-schedule-item'});
            item.connect('activate', () => this._onSetSchedule(preset.calendar));
            this._schedSubMenu.menu.addMenuItem(item);
        }
        menu.addMenuItem(this._schedSubMenu);

        // --- Separator ---
        menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
    }

    _makeButton(label, styleClass, callback) {
        const btn = new St.Button({
            label: label,
            style_class: styleClass,
            can_focus: true,
        });
        btn.connect('clicked', () => {
            callback();
            return Clutter.EVENT_STOP;
        });
        return btn;
    }

    update() {
        const status = _readStatusFile(this._job.id);
        this._status = status;
        const state = status?.state ?? 'idle';

        // Update state label and icon
        const stateColors = {idle: '#aaa', running: '#3584e4', paused: '#e5a50a', error: '#e01b24'};
        const stateNames = {idle: 'idle', running: 'syncing', paused: 'paused', error: 'error'};
        const color = stateColors[state] ?? '#aaa';

        this._stateIcon.style = `color: ${color}; margin-right: 8px; margin-top: 2px;`;
        this._stateLabel.text = stateNames[state] ?? state;
        this._stateLabel.style_class = `backup-state-${state}`;

        const isActive = state === 'running' || state === 'paused';

        // Progress bar
        this._progressItem.visible = isActive;
        if (isActive && status) {
            const pct = Math.min(100, Math.max(0, status.progress ?? 0));
            const totalWidth = this._progressBarOuter.get_width();
            if (totalWidth > 0) {
                this._progressBarFill.set_width(Math.round(totalWidth * pct / 100));
            }
            this._progressBarFill.style_class = state === 'paused'
                ? 'backup-progress-fill backup-progress-fill-paused'
                : 'backup-progress-fill';

            const parts = [];
            if (pct > 0) parts.push(`${pct}%`);
            if (status.speed) parts.push(status.speed);
            if (status.eta && status.eta !== '0:00:00') parts.push(`ETA ${status.eta}`);
            this._detailLabel.text = parts.join('  ·  ');
        }

        // Schedule info
        if (!isActive) {
            this._updateScheduleInfo();
        } else {
            this._scheduleLabel.text = '';
            this._scheduleItem.visible = false;
        }

        // Button visibility
        this._startBtn.visible = !isActive;
        this._pauseBtn.visible = isActive;
        this._stopBtn.visible = isActive;
        this._pauseBtn.label = state === 'paused' ? '▶ Resume' : '⏸ Pause';
        this._schedSubMenu.visible = !isActive;
    }

    _updateScheduleInfo() {
        this._scheduleItem.visible = true;
        _runSystemctlAsync(['show', this._job.timer, '--property=LastTriggerUSec,NextElapseUSecRealtime'], (out) => {
            if (!out) {
                this._scheduleLabel.text = 'Timer not active';
                return;
            }
            const props = {};
            for (const line of out.split('\n')) {
                const [k, ...rest] = line.split('=');
                props[k] = rest.join('=');
            }
            const parts = [];
            if (props.LastTriggerUSec && props.LastTriggerUSec !== 'n/a') {
                parts.push(`Last: ${this._relativeTime(props.LastTriggerUSec)}`);
            }
            if (props.NextElapseUSecRealtime && props.NextElapseUSecRealtime !== 'n/a') {
                parts.push(`Next: ${this._relativeTime(props.NextElapseUSecRealtime)}`);
            }
            this._scheduleLabel.text = parts.join('  ·  ') || 'Timer not scheduled';
        });
    }

    _relativeTime(timestampStr) {
        try {
            // systemd shows timestamps like "Thu 2026-03-14 11:00:00 CET"
            // Parse with Date — drop day-of-week prefix if present
            const cleaned = timestampStr.replace(/^[A-Za-z]+ /, '').replace(/ [A-Z]{3,4}$/, '');
            const ts = new Date(cleaned).getTime();
            if (isNaN(ts)) return timestampStr;

            const now = Date.now();
            const diffMs = ts - now;
            const absDiff = Math.abs(diffMs);
            const mins = Math.floor(absDiff / 60000);
            const hours = Math.floor(absDiff / 3600000);
            const days = Math.floor(absDiff / 86400000);

            let rel;
            if (mins < 1) rel = 'now';
            else if (mins < 60) rel = `${mins}m`;
            else if (hours < 24) rel = `${hours}h`;
            else rel = `${days}d`;

            return diffMs < 0 ? `${rel} ago` : `in ${rel}`;
        } catch (_e) {
            return timestampStr;
        }
    }

    _onStart() {
        _runSystemctlAsync(['start', this._job.service]);
        this._paused = false;
    }

    _onStop() {
        // Resume first if paused, so the process can receive SIGTERM
        if (this._paused) {
            _runSystemctlAsync(['kill', '--signal=USR2', this._job.service]);
        }
        _runSystemctlAsync(['stop', this._job.service]);
        this._paused = false;
    }

    _onPause() {
        if (this._paused || this._status?.state === 'paused') {
            _runSystemctlAsync(['kill', '--signal=USR2', this._job.service]);
            this._paused = false;
        } else {
            _runSystemctlAsync(['kill', '--signal=USR1', this._job.service]);
            this._paused = true;
        }
    }

    _onSetSchedule(calendar) {
        // Create timer override drop-in
        const overrideDir = GLib.build_filenamev([
            GLib.get_home_dir(), '.config', 'systemd', 'user',
            `${this._job.timer}.d`
        ]);
        const overrideFile = GLib.build_filenamev([overrideDir, 'override.conf']);

        try {
            GLib.mkdir_with_parents(overrideDir, 0o755);
            const content = `[Timer]\nOnCalendar=\nOnCalendar=${calendar}\n`;
            GLib.file_set_contents(overrideFile, content);
            _runSystemctlAsync(['daemon-reload'], () => {
                _runSystemctlAsync(['restart', this._job.timer]);
            });
        } catch (e) {
            log(`[BackupMonitor] Failed to set schedule: ${e.message}`);
        }
    }

    destroy() {
        // Nothing specific to destroy — menu items are owned by the menu
    }
}

export default class BackupMonitorExtension extends Extension {
    enable() {
        this._indicator = new PanelMenu.Button(0.0, 'Backup Monitor', false);

        // Panel icon
        const icon = new St.Icon({
            icon_name: 'drive-harddisk-symbolic',
            style_class: 'system-status-icon backup-monitor-icon',
        });
        this._indicator.add_child(icon);

        // Store reference to icon for color updates
        this._panelIcon = icon;

        // Build menu
        this._jobSections = [];
        for (const job of JOBS) {
            const section = new BackupJobSection(this, job, this._indicator.menu);
            this._jobSections.push(section);
        }

        Main.panel.addToStatusArea('backup-monitor', this._indicator);

        // Start polling status files
        this._pollId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 3, () => {
            this._updateAll();
            return GLib.SOURCE_CONTINUE;
        });

        // Initial update
        this._updateAll();
    }

    disable() {
        if (this._pollId) {
            GLib.source_remove(this._pollId);
            this._pollId = null;
        }
        for (const section of this._jobSections) {
            section.destroy();
        }
        this._jobSections = [];
        this._indicator?.destroy();
        this._indicator = null;
    }

    _updateAll() {
        let anyRunning = false;
        let anyError = false;

        for (const section of this._jobSections) {
            section.update();
            if (section._status?.state === 'running' || section._status?.state === 'paused') {
                anyRunning = true;
            }
            if (section._status?.state === 'error') {
                anyError = true;
            }
        }

        // Update panel icon color based on overall state
        if (anyError) {
            this._panelIcon.style = 'color: #e01b24;';
        } else if (anyRunning) {
            this._panelIcon.style = 'color: #3584e4;';
        } else {
            this._panelIcon.style = '';
        }
    }
}
