import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import threading
import time
import math
import os

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

        self.update_animation()

    def start_drag(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def do_drag(self, event):
        x = self.winfo_pointerx() - self._offset_x
        y = self.winfo_pointery() - self._offset_y
        self.geometry(f"+{x}+{y}")

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
        if not self.winfo_exists(): return
        try:
            self.canvas.delete("all")
            cx, cy = 100, 100
            
            color_map = {"idle": "#00D2FF", "listening": "#FF3131", "thinking": "#FFD700", "speaking": "#39FF14"}
            base_color = color_map.get(self.assistant_state, "#00D2FF")
            
            speed_mult = 2.8 if self.assistant_state == "thinking" else 1.0
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
                self.canvas.create_rectangle(px-s, py-s, px+s, py+s, fill=base_color, outline="")

            self.after(20, self.update_animation)
        except:
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
