"""
gui.py — Sylphya desktop integration: system tray icon + global hotkey (Alt+Space)
Sends IPC signals to the Electron frontend window.
"""
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import threading
import time
import math
import os
import sys
import subprocess


# ─── System Tray (pystray) ─────────────────────────────────────────────────────

def _create_tray_icon_image() -> Image.Image:
    """Draw a simple cat-silhouette icon for the system tray."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Body circle
    draw.ellipse([12, 22, 52, 60], fill=(180, 140, 255, 230))
    # Head circle
    draw.ellipse([16, 8, 48, 36], fill=(200, 160, 255, 230))
    # Left ear
    draw.polygon([(16, 14), (10, 2), (22, 8)], fill=(220, 180, 255, 230))
    # Right ear
    draw.polygon([(48, 14), (54, 2), (42, 8)], fill=(220, 180, 255, 230))
    # Eyes
    draw.ellipse([22, 16, 28, 22], fill=(60, 40, 120, 255))
    draw.ellipse([36, 16, 42, 22], fill=(60, 40, 120, 255))
    return img


def _start_tray(on_show, on_hide, on_quit):
    """Start pystray system tray icon in its own thread."""
    try:
        import pystray
        icon_image = _create_tray_icon_image()

        def _on_show(icon, item): on_show()
        def _on_hide(icon, item): on_hide()
        def _on_quit(icon, item):
            icon.stop()
            on_quit()

        menu = pystray.Menu(
            pystray.MenuItem("Show Sylphya", _on_show, default=True),
            pystray.MenuItem("Hide", _on_hide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", _on_quit),
        )
        icon = pystray.Icon("Sylphya", icon_image, "Sylphya — Friday 2.0", menu)
        icon.run()
    except ImportError:
        print("[Tray] pystray not installed — system tray disabled.")
    except Exception as e:
        print(f"[Tray] Error: {e}")


def _start_global_hotkey(on_summon):
    """Listen for Alt+Space globally to summon/dismiss Sylphya from any app."""
    try:
        import keyboard
        keyboard.add_hotkey("alt+space", on_summon, suppress=True)
        print("[Hotkey] Alt+Space registered — press to summon Sylphya from anywhere!")
        keyboard.wait()  # Block this thread
    except ImportError:
        print("[Hotkey] 'keyboard' package not installed — global hotkey disabled.")
    except Exception as e:
        print(f"[Hotkey] Error: {e}")


# ─── Animated Orb GUI ─────────────────────────────────────────────────────────

class FridayGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Friday 2.0")
        self.attributes("-topmost", True)
        self.overrideredirect(True)
        self.attributes("-transparentcolor", "#010101")
        self.config(bg="#010101")

        # Enhanced Layout for Orb + Dynamic Text
        width, height = 450, 220
        x = self.winfo_screenwidth() - width - 40
        y = self.winfo_screenheight() - height - 80
        self.geometry(f"{width}x{height}+{x}+{y}")
        self._win_x = x
        self._win_y = y
        self._visible = True

        # State Variables
        self.assistant_state = "idle"
        self.rotation_angle = 0.0
        self.particles = []
        self.num_particles = 70
        self.init_particles()

        # UI Framework
        self.main_container = tk.Frame(self, bg="#010101")
        self.main_container.pack(fill="both", expand=True)

        # Left: The Orb
        self.canvas = tk.Canvas(self.main_container, width=200, height=200, bg="#010101", highlightthickness=0)
        self.canvas.pack(side="left", padx=(10, 0))

        # Right: The Text Panel (Sleek and transparent-looking)
        self.info_panel = tk.Frame(self.main_container, bg="#010101")
        self.info_panel.pack(side="right", fill="both", expand=True, padx=15, pady=20)

        self.msg_display = tk.Text(
            self.info_panel,
            wrap="word",
            bg="#010101",
            fg="#00D2FF",
            font=("Segoe UI Variable", 11, "italic"),
            bd=0,
            highlightthickness=0,
            padx=5,
            pady=5
        )
        self.msg_display.pack(fill="both", expand=True)
        self.msg_display.tag_configure("user", foreground="#FF3131", font=("Segoe UI Variable", 10, "bold"))
        self.msg_display.tag_configure("friday", foreground="#00D2FF")
        self.msg_display.config(state="disabled")

        # Window Dragging Logic
        for widget in [self, self.main_container, self.canvas, self.info_panel]:
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.do_drag)

        self._offset_x = 0
        self._offset_y = 0

        # ── System Tray Integration ──────────────────────────────────────────
        tray_thread = threading.Thread(
            target=_start_tray,
            args=(self._show_window, self._hide_window, self._quit_app),
            daemon=True
        )
        tray_thread.start()

        # ── Global Hotkey: Alt+Space ─────────────────────────────────────────
        hotkey_thread = threading.Thread(
            target=_start_global_hotkey,
            args=(self._toggle_visibility,),
            daemon=True
        )
        hotkey_thread.start()

        self.update_animation()

    # ── Window control methods ───────────────────────────────────────────────

    def _show_window(self):
        self.after(0, lambda: (
            self.deiconify(),
            self.attributes("-topmost", True),
            self.lift()
        ))
        self._visible = True

    def _hide_window(self):
        self.after(0, self.withdraw)
        self._visible = False

    def _toggle_visibility(self):
        if self._visible:
            self._hide_window()
        else:
            self._show_window()

    def _quit_app(self):
        self.after(0, self.destroy)

    def start_drag(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def do_drag(self, event):
        x = self.winfo_pointerx() - self._offset_x
        y = self.winfo_pointery() - self._offset_y
        self.geometry(f"+{x}+{y}")
        self._win_x = x
        self._win_y = y

    def init_particles(self):
        import random
        for _ in range(self.num_particles):
            phi = random.uniform(0, 2 * math.pi)
            costheta = random.uniform(-1, 1)
            theta = math.acos(costheta)
            self.particles.append({
                'phi': phi, 'theta': theta, 'radius': random.uniform(55, 75),
                'size': random.uniform(1, 2.8), 'speed': random.uniform(0.01, 0.035)
            })

    def update_animation(self):
        if not self.winfo_exists():
            return
        try:
            self.canvas.delete("all")
            cx, cy = 100, 100

            color_map = {
                "idle": "#00D2FF",
                "listening": "#FF3131",
                "thinking": "#FFD700",
                "speaking": "#39FF14",
                "excited": "#FF69B4",
                "sleeping": "#8B7EC8",
            }
            base_color = color_map.get(self.assistant_state, "#00D2FF")

            speed_mult = 2.8 if self.assistant_state == "thinking" else (
                1.8 if self.assistant_state == "excited" else
                0.4 if self.assistant_state == "sleeping" else 1.0
            )
            self.rotation_angle += 0.022 * speed_mult

            projected = []
            for p in self.particles:
                phi = p['phi'] + self.rotation_angle * p['speed'] * 50
                theta = p['theta'] + self.rotation_angle * 0.5
                x = p['radius'] * math.sin(theta) * math.cos(phi)
                y = p['radius'] * math.sin(theta) * math.sin(phi)
                z = p['radius'] * math.cos(theta)
                factor = 200 / (220 - z)
                px, py = x * factor + cx, y * factor + cy
                projected.append((z, px, py, p['size'] * factor))

            projected.sort(key=lambda x: x[0])
            for z, px, py, s in projected:
                self.canvas.create_rectangle(px - s, py - s, px + s, py + s, fill=base_color, outline="")

            self.after(20, self.update_animation)
        except Exception:
            pass

    def update_status(self, text, state="idle"):
        self.assistant_state = state

    def add_message(self, sender, message):
        self.msg_display.config(state="normal")
        if sender == "YOU":
            self.msg_display.delete("1.0", tk.END)
            self.msg_display.insert(tk.END, f"SIR: {message}\n", "user")
        else:
            self.msg_display.delete("1.0", tk.END)
            self.msg_display.insert(tk.END, f"FRIDAY: {message}", "friday")

        self.msg_display.see(tk.END)
        self.msg_display.config(state="disabled")


if __name__ == "__main__":
    app = FridayGUI()
    app.mainloop()
