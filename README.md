# Vibe Launcher

Vibe Launcher is a floating, keyboard-driven launcher for KDE Plasma. It opens as a centered popup, lets you search apps, commands, and settings, and can also be launched as a standalone window.

## What It Looks Like

The launcher appears as a dark floating panel in the center of the screen with:

- a search bar at the top
- recent apps in a row
- recommended apps below
- keyboard hints in the footer

It is designed to feel like a lightweight custom launcher instead of the default KRunner popup.

## Files

- `metadata.json`: Plasma widget metadata
- `contents/ui/main.qml`: main plasmoid UI
- `contents/code/logic.js`: launcher history helpers
- `app/vibe_launcher.py`: standalone launcher window
- `app/com.vibe.launcher.desktop`: desktop entry for the standalone app

## Install As A Plasma Widget

Copy this folder to:

```bash
~/.local/share/plasma/plasmoids/com.vibe.launcher
```

Then restart Plasma:

```bash
kquitapp5 plasmashell && kstart5 plasmashell
```

If `kstart5` is not available:

```bash
kquitapp5 plasmashell
plasmashell &
```

After Plasma reloads:

1. Add the widget to your panel or desktop.
2. Click it to open the launcher popup.

## Run The Standalone App

You can also launch the Python version directly:

```bash
python3 app/vibe_launcher.py
```

Or make it executable and run:

```bash
./app/vibe_launcher.py
```

## Shortcut Setup

To use this instead of KRunner:

1. Open `System Settings -> Shortcuts`.
2. Remove or change KRunner's `Alt+Space` shortcut.
3. Create a custom shortcut that runs:

```bash
/home/your-user/.local/share/plasma/plasmoids/com.vibe.launcher/app/vibe_launcher.py
```

4. Bind that shortcut to `Alt+Space`.

Replace `your-user` with your actual username.

## Behavior

- `Esc` closes the launcher
- `Up` and `Down` move selection
- `Enter` opens the selected result
- searching updates results live
- recent usage is stored and reused for suggestions

## Notes

- The widget uses Plasma's runner infrastructure for app, settings, calculator, and unit conversion results.
- The standalone app uses local desktop-file scanning and its own history cache.
- The desktop entry currently uses a user-specific absolute path, so update it if you install the standalone app somewhere else.
