# Kegerator

A touchscreen kegerator tracker for a Raspberry Pi 3B+ with a 7" HDMI display (Elecrow), built with Python + Tkinter.

## Features

- **4 tap cards**, each showing a keg icon (drawn from `keg.svg`) with a color-coded volume fill:
  - 🟢 Green: > 25%
  - 🟡 Yellow: 10–25%
  - 🔴 Red: < 10%
- **Tap-to-select** a keg, then pour **Small**, **Large**, or **Growler** (64 oz)
- **Live updates** — fill level and color recompute after every pour
- **Config-driven** — tap names and keg resets are set in `config.ini`
- **Auto-reload** — the app watches `config.ini` and reloads ~30s after you save
- **Persistent** — keg volumes stored in SQLite (`kegs.db`)
- **Dark mode** UI, designed for a 1024×600 touchscreen

## Files

| File | Purpose |
|------|---------|
| `kegerator.py` | The app |
| `config.example.ini` | Template config (copy to `config.ini`) |
| `config.ini` | Your real config (**gitignored**) |
| `keg.svg` | The keg artwork (drawn in Inkscape) |
| `kegs.db` | Live keg volumes (**gitignored**, auto-created) |

## Setup

```bash
# copy the example config to your real one
cp config.example.ini config.ini

# run it (windowed, for desktop testing)
python3 kegerator.py

# run it full-screen (for the Pi touchscreen)
python3 kegerator.py --fullscreen
```

Requires Python 3 with Tkinter (built into Raspberry Pi OS Desktop).

## Configuration

Edit `config.ini`:

```ini
[kegerator]
small_pour_oz = 8
large_pour_oz = 16
growler_pour_oz = 64
num_taps = 4

[tap1]
name = Example Beer 1
reset = false
```

- **`name`** — what's in the keg. Use `(empty)` for an empty tap (always shows 0%).
- **`reset`** — set to `true` when you put in a fresh keg. The app fills it to capacity (640 oz) and auto-clears it back to `false`.

The app watches `config.ini` and reloads automatically ~30 seconds after you save — no restart needed.

## Autostart on the Pi (systemd)

Create `/etc/systemd/system/kegerator.service`:

```ini
[Unit]
Description=Kegerator Touchscreen App
After=graphical.target

[Service]
Type=simple
User=pi
Environment=DISPLAY=:0
WorkingDirectory=/home/pi/kegerator
ExecStart=/usr/bin/python3 /home/pi/kegerator/kegerator.py --fullscreen
Restart=always
RestartSec=5

[Install]
WantedBy=graphical.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable kegerator.service
sudo systemctl start kegerator.service
```

Adjust `User`, `WorkingDirectory`, and the `ExecStart` path to match your Pi setup.
