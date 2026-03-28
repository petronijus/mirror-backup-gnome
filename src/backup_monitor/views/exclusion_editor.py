"""Exclusion editor — visual pattern editor for rsync exclude files."""

from __future__ import annotations

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

from backup_monitor.services.job_manager import read_exclusions, write_exclusions


class ExclusionEditorPage(Adw.NavigationPage):
    """Page for editing rsync exclusion patterns."""

    __gtype_name__ = 'ExclusionEditorPage'

    def __init__(self, exclude_file: str):
        super().__init__(title='Exclusion Patterns')
        self._exclude_file = exclude_file
        self._entries: list[dict] = read_exclusions(exclude_file)

        # Layout
        toolbar = Adw.ToolbarView()
        self.set_child(toolbar)

        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        save_btn = Gtk.Button(
            label='Save',
            css_classes=['suggested-action'],
        )
        save_btn.connect('clicked', self._on_save)
        header.pack_end(save_btn)

        scroll = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        toolbar.set_content(scroll)

        clamp = Adw.Clamp(
            maximum_size=600,
            margin_top=24, margin_bottom=24,
            margin_start=24, margin_end=24,
        )
        scroll.set_child(clamp)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(main_box)

        # Add pattern entry
        add_group = Adw.PreferencesGroup(title='Add Pattern')
        main_box.append(add_group)

        self._add_entry = Adw.EntryRow(title='Pattern (e.g. *.tmp, .cache/)')
        add_btn = Gtk.Button(
            icon_name='list-add-symbolic',
            css_classes=['flat'],
            valign=Gtk.Align.CENTER,
        )
        add_btn.connect('clicked', self._on_add)
        self._add_entry.add_suffix(add_btn)
        self._add_entry.connect('entry-activated', lambda r: self._on_add(None))
        add_group.add(self._add_entry)

        # Patterns list
        self._patterns_group = Adw.PreferencesGroup(
            title='Patterns',
            description=f'{len(self._entries)} pattern{"s" if len(self._entries) != 1 else ""}',
        )
        main_box.append(self._patterns_group)

        self._rebuild_list()

    def _rebuild_list(self):
        """Rebuild the patterns list from self._entries."""
        # Remove all existing rows
        while True:
            # AdwPreferencesGroup doesn't have get_first_child for rows easily,
            # so we track rows ourselves
            break

        # We need to recreate the group since there's no easy remove API
        parent = self._patterns_group.get_parent()
        if parent:
            parent.remove(self._patterns_group)

        self._patterns_group = Adw.PreferencesGroup(
            title='Patterns',
            description=f'{len(self._entries)} pattern{"s" if len(self._entries) != 1 else ""}',
        )
        if parent:
            parent.append(self._patterns_group)

        for i, entry in enumerate(self._entries):
            row = Adw.ActionRow(
                title=entry['pattern'],
            )

            # Enable/disable toggle
            switch = Gtk.Switch(
                active=entry.get('enabled', True),
                valign=Gtk.Align.CENTER,
            )
            switch.connect('notify::active', self._on_toggle, i)
            row.add_prefix(switch)

            # Delete button
            delete_btn = Gtk.Button(
                icon_name='edit-delete-symbolic',
                css_classes=['flat', 'error'],
                valign=Gtk.Align.CENTER,
                tooltip_text='Remove pattern',
            )
            delete_btn.connect('clicked', self._on_remove, i)
            row.add_suffix(delete_btn)

            self._patterns_group.add(row)

    def _on_add(self, btn):
        pattern = self._add_entry.get_text().strip()
        if not pattern:
            return

        # Check for duplicates
        existing = {e['pattern'] for e in self._entries}
        if pattern in existing:
            return

        self._entries.append({'pattern': pattern, 'enabled': True})
        self._add_entry.set_text('')
        self._rebuild_list()

    def _on_toggle(self, switch, pspec, index):
        if 0 <= index < len(self._entries):
            self._entries[index]['enabled'] = switch.get_active()

    def _on_remove(self, btn, index):
        if 0 <= index < len(self._entries):
            self._entries.pop(index)
            self._rebuild_list()

    def _on_save(self, btn):
        write_exclusions(self._exclude_file, self._entries)

        # Show toast and go back
        root = self.get_root()
        if hasattr(root, 'add_toast'):
            root.add_toast(Adw.Toast(title='Exclusions saved'))

        # Navigate back
        widget = self.get_parent()
        while widget:
            if isinstance(widget, Adw.NavigationView):
                widget.pop()
                return
            widget = widget.get_parent()
