# Screenshots

Drop PNGs here to populate the README gallery:

- `dashboard.png` — main window, status cards for a few jobs
- `job-editor.png` — the visual schedule + rsync-options editor
- `panel.png` — the GNOME Shell panel indicator menu open

Capture on a GNOME session:
```bash
gnome-screenshot -w -f docs/screenshots/dashboard.png   # active window
# Wayland alternative:
grim -g "$(slurp)" docs/screenshots/panel.png           # region select
```
Keep them reasonably sized (≤ ~1600px wide).
