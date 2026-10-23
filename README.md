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

## Display session: use X11 (not Wayland)

**This app runs best on an X11 session, not Wayland.**

Tkinter is a native X11 toolkit. On Raspberry Pi OS Bookworm (which defaults to
Wayland with the labwc compositor), a Tkinter app runs through Xwayland and a
compositor, which adds noticeable input/render latency — especially on a
Pi 3B+.

If the touch interface feels laggy, switch to X11:

```bash
sudo raspi-config
```

→ **Advanced Options** → **Wayland** → select **X11** → reboot.

Confirm which session you're running with:

```bash
echo $XDG_SESSION_TYPE
```

It should print `x11`.

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

## 3Dprint files
Also available are files for 3D printing the pieces that attach the monitor to the kegerator. Files are for a 4-tap Komos kegerator.

Files are in 3Dprint_files. STL and STEP files are included. Parts were created/modified in OnShape, so links are also provided for direct access.

The `keg_cap` is original to this project. The **monitor frame** and **monitor back cover** are adapted from [Raspberry Show — a Raspberry Pi 3B/4 case with embedded 7″ display](https://www.printables.com/model/1006894-raspberry-show-a-raspberry-pi-3b4-case-with-embedd) by Ciro Lucio Tecce, used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See [3Dprint_files/LICENSE.md](3Dprint_files/LICENSE.md) for the full attribution and the list of modifications — crediting him is required if you redistribute those files.

For the keg_cap, the piece that sits on the top of the tap tower:
https://cad.onshape.com/documents/7b540bec6c0b23e93142f414/w/38894cd1cf6efaa625041dfd/e/9bd5d41a02a29f798dda2a9c?renderMode=0&uiState=6ada9633de49b5e753042f31

For the Monitor frame, used for the Elecrow 7-inch 1024x600 raspberry pi monitor:
https://cad.onshape.com/documents/e406d0c0a4214a8ba2170324/w/4877de233f648fc769db1573/e/704da8c5f349d3efb70cd7fd?renderMode=0&uiState=6ada97cd47974a0021c27b53

For the back frame of the monitor, attaches the Monitor frame and keg cap:
https://cad.onshape.com/documents/f5e7625d781ff9b2b7112170/w/74f7e3d18356ae620982d11e/e/94ef9df744d482d954514f33?renderMode=0&uiState=6ada9781ccc75100699e9a3a

## License

| What | Where | License | SPDX |
|------|-------|---------|------|
| App code, example config, keg artwork | `kegerator.py`, `config.example.ini`, `keg.svg` | [MIT](LICENSE) | `MIT` |
| 3D print files | `3Dprint_files/` | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | `CC-BY-4.0` |

The [MIT license](LICENSE) covers the software only. The print files are covered
separately in [3Dprint_files/LICENSE.md](3Dprint_files/LICENSE.md), because two of
the three parts are modifications of a design by
[Ciro Lucio Tecce](https://www.printables.com/model/1006894-raspberry-show-a-raspberry-pi-3b4-case-with-embedd)
used under CC BY 4.0. Attribution is required if you share or adapt them.
