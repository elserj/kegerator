#!/usr/bin/env python3
"""
Kegerator tracker — Tkinter touchscreen app for Raspberry Pi 3B+ / Elecrow 7" HDMI.

- 4 tap cards, each with a Canvas-drawn keg icon colored by volume:
    green  > 25%
    yellow 10-25%
    red    < 10%
- Tap a keg to select it, then tap Small or Large pour.
- Config file (config.ini) sets names, capacities, pour sizes, and keg resets.
- SQLite (kegs.db) persists current volume across reboots.

Runs identically on desktop and Pi. Use --fullscreen on the Pi.
"""

import configparser
import os
import sqlite3
import sys
import tkinter as tk


# ---------------------------------------------------------------- theme
# Dark mode color palette
BG = "#1e1e1e"          # main background
CARD_BG = "#2d2d2d"     # unselected tap card
CARD_SEL = "#4a4a4a"    # selected tap card (lighter so it stands out)
TEXT = "#e0e0e0"         # primary text
TEXT_DIM = "#a0a0a0"     # secondary text
OUTLINE = "#111111"        # dark outline on keg

# All kegs are 5-gallon corny kegs (640 oz). Capacity is fixed.
KEG_CAPACITY_OZ = 640.0


# ---------------------------------------------------------------- config
def load_config(path="config.ini"):
    cfg = configparser.ConfigParser()
    cfg.read(path)
    small = cfg.getfloat("kegerator", "small_pour_oz", fallback=8)
    large = cfg.getfloat("kegerator", "large_pour_oz", fallback=16)
    growler = cfg.getfloat("kegerator", "growler_pour_oz", fallback=64)
    num_taps = cfg.getint("kegerator", "num_taps", fallback=4)

    taps = []
    for i in range(1, num_taps + 1):
        section = f"tap{i}"
        try:
            reset = cfg.getboolean(section, "reset", fallback=False)
        except ValueError:
            # malformed value in config; treat as not-reset rather than crash
            reset = False
        taps.append({
            "name": cfg.get(section, "name", fallback=f"Tap {i}"),
            "reset": reset,
        })
    return small, large, growler, taps


# ---------------------------------------------------------------- database
def init_db():
    conn = sqlite3.connect("kegs.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS kegs (
        tap_id INTEGER PRIMARY KEY,
        volume_oz REAL
    )""")
    return conn


def clear_reset_flags(path, tap_ids):
    """Set reset=false for the given tap sections in config.ini, preserving
    comments and formatting via targeted text replacement.
    Only clears a value of 'true' so malformed lines are left alone."""
    if not tap_ids:
        return
    with open(path) as f:
        lines = f.readlines()
    for tid in tap_ids:
        section = f"[tap{tid}]"
        in_section = False
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if stripped.startswith("["):
                in_section = (stripped == section)
                continue
            if in_section and stripped.startswith("reset"):
                # only clear when the value is literally 'true'
                value = stripped.split("=", 1)[1].strip() if "=" in stripped else ""
                if value == "true":
                    lines[i] = "reset = false\n"
                break
    with open(path, "w") as f:
        f.writelines(lines)


def load_volumes(conn, taps, config_path="config.ini"):
    """Load persisted volumes; apply any config 'reset' flags.
    A tap named '(empty)' is always treated as 0% (empty).
    After a reset is applied, the config flag is cleared to false."""
    volumes = {}
    reset_ids = []
    for i, tap in enumerate(taps, start=1):
        # an "(empty)" tap is always empty (0%)
        if tap["name"].strip().lower() == "(empty)":
            volumes[i] = 0.0
            conn.execute("INSERT OR REPLACE INTO kegs (tap_id, volume_oz) VALUES (?,?)",
                       (i, 0.0))
            continue
        row = conn.execute("SELECT volume_oz FROM kegs WHERE tap_id=?", (i,)).fetchone()
        if tap["reset"]:
            # config says refill this keg -> set to capacity, clear flag
            volumes[i] = KEG_CAPACITY_OZ
            conn.execute("INSERT OR REPLACE INTO kegs (tap_id, volume_oz) VALUES (?,?)",
                       (i, KEG_CAPACITY_OZ))
            reset_ids.append(i)
        elif row is not None:
            volumes[i] = row[0]
        else:
            # first run, no row yet -> start at capacity
            volumes[i] = KEG_CAPACITY_OZ
            conn.execute("INSERT OR REPLACE INTO kegs (tap_id, volume_oz) VALUES (?,?)",
                       (i, KEG_CAPACITY_OZ))
    conn.commit()
    clear_reset_flags(config_path, reset_ids)
    return volumes


def save_volume(conn, tap_id, volume):
    conn.execute("UPDATE kegs SET volume_oz=? WHERE tap_id=?", (volume, tap_id))
    conn.commit()


# ---------------------------------------------------------------- color logic
def volume_color(volume_oz, capacity_oz):
    """Return (color, pct) based on live volume."""
    pct = (volume_oz / capacity_oz) * 100 if capacity_oz else 0
    if pct > 25:
        return "#2ecc71", pct      # green
    elif pct >= 10:
        return "#f1c40f", pct      # yellow
    else:
        return "#e74c3c", pct      # red


# ---------------------------------------------------------------- app
class KegeratorApp:
    def __init__(self, root, fullscreen):
        self.root = root
        self.small, self.large, self.growler, self.taps = load_config()
        self.conn = init_db()
        self.volumes = load_volumes(self.conn, self.taps)
        self.selected = 1

        root.title("Kegerator")
        root.configure(bg=BG)
        if fullscreen:
            root.attributes("-fullscreen", True)
            root.configure(cursor="none")
        else:
            # match the Elecrow resolution so desktop preview matches the Pi
            root.geometry("1024x600")

        self._build_ui()

        # watch config.ini for changes and reload automatically
        self._last_mtime = self._config_mtime()
        self._watch_config()

    # ------------------------------------------------------------ UI
    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)   # keg cards row expands

        # header
        header = tk.Label(self.root, text="Justin's Kegerator", font=("Helvetica", 28, "bold"),
                        bg=BG, fg=TEXT)
        header.grid(row=0, column=0, pady=10)

        # pour buttons
        buttons = tk.Frame(self.root, bg=BG)
        buttons.grid(row=1, column=0, pady=(0, 10))
        for c in range(3):
            buttons.columnconfigure(c, weight=1)

        self.small_btn = tk.Button(buttons, text=f"SMALL POUR\n({self.small:.0f} oz)",
                             font=("Helvetica", 18, "bold"), bg="#1f6feb", fg="white",
                             activebackground="#3a86ff", activeforeground="white",
                             width=14, height=3,
                             command=lambda: self.pour(self.small))
        self.small_btn.grid(row=0, column=0, padx=20)

        self.large_btn = tk.Button(buttons, text=f"LARGE POUR\n({self.large:.0f} oz)",
                             font=("Helvetica", 18, "bold"), bg="#8957e5", fg="white",
                             activebackground="#a06bff", activeforeground="white",
                             width=14, height=3,
                             command=lambda: self.pour(self.large))
        self.large_btn.grid(row=0, column=1, padx=20)

        self.growler_btn = tk.Button(buttons, text=f"GROWLER\n({self.growler:.0f} oz)",
                             font=("Helvetica", 18, "bold"), bg="#e67e22", fg="white",
                             activebackground="#f39c12", activeforeground="white",
                             width=14, height=3,
                             command=lambda: self.pour(self.growler))
        self.growler_btn.grid(row=0, column=2, padx=20)

        # selected-tap info bar
        self.info = tk.Label(self.root, text="", font=("Helvetica", 16, "bold"),
                           bg=BG, fg=TEXT)
        self.info.grid(row=2, column=0, pady=10)

        # tap cards row
        cards = tk.Frame(self.root, bg=BG)
        cards.grid(row=3, column=0, sticky="nsew", padx=10)
        for i in range(len(self.taps)):
            cards.columnconfigure(i, weight=1, uniform="tap")
        cards.rowconfigure(0, weight=1)

        self.card_frames = []
        self.keg_canvases = []
        self.name_labels = []
        self.vol_labels = []

        for i in range(len(self.taps)):
            frame = tk.Frame(cards, bd=3, relief="groove", bg=CARD_BG)
            frame.grid(row=0, column=i, sticky="nsew", padx=8, pady=8)
            frame.bind("<Button-1>", lambda e, idx=i + 1: self.select_tap(idx))
            self.card_frames.append(frame)

            # keg icon drawn on a canvas
            canvas = tk.Canvas(frame, width=120, height=160, highlightthickness=0,
                              bg=CARD_BG)
            canvas.pack(expand=True, pady=(10, 0))
            canvas.bind("<Button-1>", lambda e, idx=i + 1: self.select_tap(idx))
            self.keg_canvases.append(canvas)

            name = tk.Label(frame, text=self.taps[i]["name"],
                          font=("Helvetica", 14, "bold"), bg=CARD_BG, fg=TEXT)
            name.pack(pady=(4, 0))
            name.bind("<Button-1>", lambda e, idx=i + 1: self.select_tap(idx))
            self.name_labels.append(name)

            vol = tk.Label(frame, text="", font=("Helvetica", 12), bg=CARD_BG, fg=TEXT_DIM)
            vol.pack(pady=(0, 8))
            vol.bind("<Button-1>", lambda e, idx=i + 1: self.select_tap(idx))
            self.vol_labels.append(vol)

        self.refresh()

    # ------------------------------------------------------------ config watch
    def _config_mtime(self):
        try:
            return os.path.getmtime("config.ini")
        except OSError:
            return 0

    def _watch_config(self):
        """Poll config.ini's mtime; reload only when the file changes."""
        try:
            mtime = self._config_mtime()
            if mtime != self._last_mtime:
                self._last_mtime = mtime
                self._reload_config()
        except Exception:
            pass  # ignore errors so polling continues
        # always reschedule so polling continues even after an error
        self.root.after(30000, self._watch_config)

    def _reload_config(self):
        """Re-read config (names/resets), re-apply volumes, refresh UI.
        Pour sizes and capacity are fixed, so they aren't re-read here."""
        _, _, _, taps = load_config()
        self.taps = taps
        # re-apply volumes; may write reset flags back to config
        self.volumes = load_volumes(self.conn, self.taps)
        # re-read mtime after any config write so we don't self-trigger again
        self._last_mtime = self._config_mtime()
        # keep selected tap in range if num_taps changed
        if self.selected > len(self.taps):
            self.selected = len(self.taps)
        self.refresh()

    # ------------------------------------------------------------ drawing
    # Geometry extracted from keg.svg (Inkscape). All coordinates are in the
    # SVG's user space (x 65-145, y 82-263). The fill curves are the same
    # cubic bezier shape translated vertically.
    KEG_X0, KEG_X1 = 65.0, 145.0      # left / right walls
    KEG_Y_TOP = 82.0                     # top ellipse center y
    KEG_Y_BOTTOM = 262.77                # bottom curve y (0%)
    KEG_Y_FILL_TOP = 105.6              # g5 top fill line y (100%)

    # bottom curve (path1): cubic bezier right -> left
    BOTTOM_P0 = (144.99, 262.77)
    BOTTOM_P1 = (110.35, 275.63)
    BOTTOM_P2 = (99.57, 273.57)
    BOTTOM_P3 = (64.99, 262.77)
    # fill line control point offsets (relative to the level y)
    FILL_OFF1 = (-34.64, 12.86)
    FILL_OFF2 = (-45.42, 10.80)
    FILL_OFF3 = (-80.00, 0.0)
    # top ellipse (path4): cx, cy, rx, ry
    TOP_ELLIPSE = (105.2, 81.89, 40.06, 10.97)

    # fill-line reference levels (g5 top + g6-g9), drawn as faint guide lines
    REFERENCE_FILLS = [105.6, 136.45, 170.17, 201.31, 231.16]

    # SVG -> canvas transform (fit keg into 120x160 canvas).
    # X and Y scales are separate so we can widen the keg without making it taller.
    Y_SCALE = 0.72
    X_SCALE = 0.77 * 1.35   # widened 35%
    X_OFF = (120 - (KEG_X1 - KEG_X0) * X_SCALE) / 2   # center horizontally
    Y_OFF = 11.0

    @staticmethod
    def _blend(c1, c2, t):
        """Blend two hex colors: t*c1 + (1-t)*c2. Returns a hex color."""
        def hx(c):
            c = c.lstrip('#')
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
        r1, g1, b1 = hx(c1)
        r2, g2, b2 = hx(c2)
        r = int(r1 * t + r2 * (1 - t))
        g = int(g1 * t + g2 * (1 - t))
        b = int(b1 * t + b2 * (1 - t))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _tx(self, x, y):
        return (self.X_OFF + (x - self.KEG_X0) * self.X_SCALE,
                self.Y_OFF + (y - self.KEG_Y_TOP) * self.Y_SCALE)

    @staticmethod
    def _sample_bezier(p0, p1, p2, p3, n=24):
        """Sample a cubic bezier into n+1 points."""
        pts = []
        for i in range(n + 1):
            t = i / n
            mt = 1 - t
            x = mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] \
                + 3 * mt * t * t * p2[0] + t ** 3 * p3[0]
            y = mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] \
                + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]
            pts.append((x, y))
        return pts

    def _fill_line_at(self, y, n=24):
        """Return the fill-line bezier points (right -> left) at level y."""
        p0 = (144.99, y)
        p1 = (144.99 + self.FILL_OFF1[0], y + self.FILL_OFF1[1])
        p2 = (144.99 + self.FILL_OFF2[0], y + self.FILL_OFF2[1])
        p3 = (144.99 + self.FILL_OFF3[0], y + self.FILL_OFF3[1])
        return self._sample_bezier(p0, p1, p2, p3, n)

    def draw_keg(self, canvas, color, pct, card_bg):
        """Draw the keg from keg.svg geometry. The state color fills the body
        between the curved bottom and the current fill line, so the fill line
        follows the keg's curve."""
        canvas.delete("all")
        w, h = 120, 160

        # fill level y in SVG space: 100% -> g5 top, 0% -> bottom
        fill_y = self.KEG_Y_BOTTOM - (pct / 100) * (self.KEG_Y_BOTTOM - self.KEG_Y_FILL_TOP)

        # --- colored fill region (between bottom curve and current fill line) ---
        # blend the state color 50% with the card background for a translucent look
        fill_color = self._blend(color, card_bg, 0.5)
        bottom = self._sample_bezier(self.BOTTOM_P0, self.BOTTOM_P1,
                                   self.BOTTOM_P2, self.BOTTOM_P3)   # right -> left
        top = self._fill_line_at(fill_y)                                  # right -> left
        poly_svg = bottom + [(self.KEG_X0, fill_y)] + list(reversed(top)) \
            + [(self.KEG_X1, self.KEG_Y_BOTTOM)]
        poly = [self._tx(*p) for p in poly_svg]
        canvas.create_polygon(poly, smooth=True, fill=fill_color, outline="")

        # --- keg outline ---
        # bottom curve
        bpts = [self._tx(*p) for p in bottom]
        canvas.create_line(bpts, fill=OUTLINE, width=2, smooth=True)
        # side walls
        canvas.create_line(self._tx(self.KEG_X0, self.KEG_Y_TOP),
                        self._tx(self.KEG_X0, self.KEG_Y_BOTTOM),
                        fill=OUTLINE, width=2)
        canvas.create_line(self._tx(self.KEG_X1, self.KEG_Y_TOP),
                        self._tx(self.KEG_X1, self.KEG_Y_BOTTOM),
                        fill=OUTLINE, width=2)
        # top ellipse
        cx, cy, rx, ry = self.TOP_ELLIPSE
        x0, y0 = self._tx(cx - rx, cy - ry)
        x1, y1 = self._tx(cx + rx, cy + ry)
        canvas.create_oval(x0, y0, x1, y1, outline=OUTLINE, width=2)
        # current fill line
        fpts = [self._tx(*p) for p in top]
        canvas.create_line(fpts, fill=OUTLINE, width=2, smooth=True)

        # --- reference fill lines (faint marks: g5 top + g6-g9) ---
        for ly in self.REFERENCE_FILLS:
            line = self._fill_line_at(ly)
            lpts = [self._tx(*p) for p in line]
            canvas.create_line(lpts, fill=TEXT_DIM, width=1, smooth=True)

        # --- top details (fittings) ---
        # collar fittings: two rounded rects (rect4, rect4-4)
        for (rx2, ry2, rw, rh) in [(96.42, 96.61, 17.17, 5.38),
                                      (96.42, 75.20, 17.17, 5.38)]:
            fx0, fy0 = self._tx(rx2, ry2)
            fx1, fy1 = self._tx(rx2 + rw, ry2 + rh)
            canvas.create_rectangle(fx0, fy0, fx1, fy1, outline=OUTLINE, width=1)
        # valve opening (path10) - small ellipse
        vcx, vcy = self._tx(126.7, 81.49)
        vrx = 4.87 * self.X_SCALE
        vry = 1.28 * self.Y_SCALE
        canvas.create_oval(vcx - vrx, vcy - vry, vcx + vrx, vcy + vry,
                         outline=OUTLINE, width=1)
        # tap handle (path11) - polyline
        handle = [(119.41, 81.50), (120.55, 86.86), (127.39, 86.86),
                 (128.24, 84.46), (129.11, 81.57)]
        hpts = [self._tx(*p) for p in handle]
        canvas.create_line(hpts, fill=OUTLINE, width=1, smooth=True)
        # rim curves (path9, path153)
        for (p0, p1, p2, p3) in [
            ((128.14, 84.74), (132.16, 85.30), (136.23, 86.01), (140.36, 86.87)),
            ((69.64, 86.36), (85.59, 83.27), (102.25, 82.14), (119.90, 83.78)),
        ]:
            cpts = [self._tx(*p) for p in self._sample_bezier(p0, p1, p2, p3, 12)]
            canvas.create_line(cpts, fill=OUTLINE, width=1, smooth=True)

        # percentage text (below the keg)
        canvas.create_text(w / 2, h - 6, text=f"{pct:.0f}%",
                        font=("Helvetica", 11, "bold"), fill=TEXT)

    def refresh(self):
        for i, tap in enumerate(self.taps):
            idx = i + 1
            vol = self.volumes[idx]
            color, pct = volume_color(vol, KEG_CAPACITY_OZ)

            # highlight selected card
            card_bg = CARD_SEL if idx == self.selected else CARD_BG
            self.card_frames[i].config(
                relief="sunken" if idx == self.selected else "groove",
                bg=card_bg,
            )
            self.keg_canvases[i].config(bg=card_bg)
            self.name_labels[i].config(text=tap["name"], bg=card_bg)
            self.vol_labels[i].config(bg=card_bg)
            self.draw_keg(self.keg_canvases[i], color, pct, card_bg)
            self.vol_labels[i].config(text=f"{vol:.0f} oz")

        sel = self.taps[self.selected - 1]
        self.info.config(
            text=f"Selected: Tap {self.selected} — {sel['name']}  ({self.volumes[self.selected]:.0f} oz left)"
        )

    # ------------------------------------------------------------ actions
    def select_tap(self, idx):
        self.selected = idx
        self.refresh()

    def pour(self, amount):
        idx = self.selected
        new_vol = self.volumes[idx] - amount
        if new_vol < 0:
            new_vol = 0
        self.volumes[idx] = new_vol
        save_volume(self.conn, idx, new_vol)
        self.refresh()


# ---------------------------------------------------------------- main
def main():
    fullscreen = "--fullscreen" in sys.argv
    root = tk.Tk()
    KegeratorApp(root, fullscreen)
    root.mainloop()


if __name__ == "__main__":
    main()
