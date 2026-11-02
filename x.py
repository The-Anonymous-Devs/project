#!/usr/bin/env python3
"""FrameForge: a simple cross-platform stick-animation editor prototype.
Run with python3 x.py (requires Tkinter)."""
import json
import math
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

BG, PANEL, PANEL2, BORDER, TEXT, MUTED, ACCENT = "#111318", "#191c23", "#20242d", "#303641", "#e8ebf2", "#929baa", "#8c72ff"
W, H = 960, 540

def pose(x=.5, y=.52):
    return {"x": x, "y": y}

class FrameForge:
    def __init__(self, root):
        self.root = root
        root.title("FrameForge — Untitled Animation")
        root.geometry("1200x790")
        root.minsize(850, 600)
        root.configure(bg=BG)
        self.frames = [pose() for _ in range(12)]
        self.current, self.playing, self.onion, self.path = 0, False, True, None
        self.drag = None
        self._ui()
        self.draw()
        self.timeline()
        root.protocol("WM_DELETE_WINDOW", self.close)

    def button(self, parent, text, cmd, active=False):
        return tk.Button(parent, text=text, command=cmd, bg=ACCENT if active else PANEL2,
                         fg="white" if active else TEXT, activebackground="#a18cff",
                         relief="flat", bd=0, padx=10, pady=6, cursor="hand2")

    def _ui(self):
        head = tk.Frame(self.root, bg="#171a20", height=52); head.pack(fill="x"); head.pack_propagate(False)
        tk.Label(head, text="✦ FRAMEFORGE", bg="#171a20", fg=TEXT, font=("TkDefaultFont", 13, "bold")).pack(side="left", padx=18)
        tk.Label(head, text="STICK ANIMATION STUDIO", bg="#171a20", fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(side="left", padx=8)
        self.name = tk.Label(head, text="Untitled Animation", bg="#171a20", fg=TEXT); self.name.pack(side="left", padx=20)
        for label, fn, active in (("New", self.new, False), ("Open", self.open, False), ("Save", self.save, False), ("Export SVG", self.export, True)):
            self.button(head, label, fn, active).pack(side="right", padx=4, pady=8)
        area = tk.Frame(self.root, bg=BG); area.pack(fill="both", expand=True, padx=12, pady=12)
        rail = tk.Frame(area, bg=PANEL, width=60); rail.pack(side="left", fill="y"); rail.pack_propagate(False)
        tk.Label(rail, text="TOOLS", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(pady=14)
        self.button(rail, "↖", lambda: None, True).pack(padx=8, pady=4)
        self.button(rail, "＋", self.add).pack(padx=8, pady=4)
        self.onion_btn = self.button(rail, "◉", self.toggle_onion); self.onion_btn.pack(padx=8, pady=4)
        center = tk.Frame(area, bg=BG); center.pack(side="left", fill="both", expand=True, padx=10)
        top = tk.Frame(center, bg=BG); top.pack(fill="x", pady=(0, 7))
        tk.Label(top, text="STAGE", bg=BG, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(side="left")
        self.frame_label = tk.Label(top, text="Frame 1 / 12", bg=BG, fg=MUTED); self.frame_label.pack(side="right")
        self.canvas = tk.Canvas(center, bg="#252a33", highlightthickness=1, highlightbackground=BORDER)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<ButtonPress-1>", self.start_drag); self.canvas.bind("<B1-Motion>", self.move_drag); self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        props = tk.Frame(area, bg=PANEL, width=175); props.pack(side="right", fill="y"); props.pack_propagate(False)
        tk.Label(props, text="PROPERTIES", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=14, pady=16)
        for title, value in (("DOCUMENT", ""), ("Stage", "960 × 540"), ("Frame rate", "12 fps"), ("SELECTED FRAME", "")):
            tk.Label(props, text=title, bg=PANEL, fg=MUTED if not value else TEXT, font=("TkDefaultFont", 9, "bold" if not value else "TkDefaultFont")).pack(anchor="w", padx=14, pady=(8, 2))
            if value: tk.Label(props, text=value, bg=PANEL, fg=TEXT).pack(anchor="w", padx=14)
        self.position = tk.Label(props, text="Position 50%, 52%", bg=PANEL, fg=TEXT); self.position.pack(anchor="w", padx=14, pady=12)
        tk.Label(props, text="Drag the stick figure to pose it. Add or duplicate frames to create motion.", wraplength=145, justify="left", bg=PANEL, fg=MUTED).pack(anchor="w", padx=14, pady=10)
        timeline = tk.Frame(self.root, bg=PANEL, height=160); timeline.pack(fill="x", padx=12, pady=(0, 12)); timeline.pack_propagate(False)
        bar = tk.Frame(timeline, bg=PANEL); bar.pack(fill="x", padx=12, pady=10)
        tk.Label(bar, text="TIMELINE", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(side="left")
        self.button(bar, "＋ Frame", self.add, True).pack(side="left", padx=(14, 4))
        self.button(bar, "Duplicate", self.duplicate).pack(side="left", padx=4)
        self.button(bar, "Delete", self.delete).pack(side="left", padx=4)
        self.play_btn = self.button(bar, "▶ Play", self.toggle_play, True); self.play_btn.pack(side="right")
        self.strip = tk.Frame(timeline, bg=PANEL); self.strip.pack(fill="x", padx=12)
        self.status = tk.Label(timeline, text="Ready · Drag the figure to pose this frame", bg=PANEL, fg=MUTED); self.status.pack(side="right", padx=14, pady=8)

    def box(self):
        cw, ch = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        scale = min((cw-24)/W, (ch-24)/H); sw, sh = W*scale, H*scale
        return (cw-sw)/2, (ch-sh)/2, sw, sh

    def draw(self):
        if not hasattr(self, "canvas"): return
        c = self.canvas; c.delete("all"); ox, oy, sw, sh = self.box()
        c.create_rectangle(ox, oy, ox+sw, oy+sh, fill="#f7f8fb", outline="")
        for x in range(0, W+1, 48): c.create_line(ox+sw*x/W, oy, ox+sw*x/W, oy+sh, fill="#edf0f5")
        for y in range(0, H+1, 48): c.create_line(ox, oy+sh*y/H, ox+sw, oy+sh*y/H, fill="#edf0f5")
        c.create_line(ox, oy+sh*.83, ox+sw, oy+sh*.83, fill="#cfd5df", width=2)
        if self.onion and len(self.frames)>1 and not self.playing: self.figure(self.frames[(self.current-1)%len(self.frames)], ox, oy, sw, sh, "#9ba9db")
        self.figure(self.frames[self.current], ox, oy, sw, sh, "#252b38")
        f=self.frames[self.current]; self.position.config(text=f"Position {round(f['x']*100)}%, {round(f['y']*100)}%")
        self.frame_label.config(text=f"Frame {self.current+1} / {len(self.frames)}")

    def figure(self, f, ox, oy, sw, sh, color):
        x,y=ox+f["x"]*sw,oy+f["y"]*sh; s=min(sw/W,sh/H); c=self.canvas
        c.create_oval(x-20*s,y-105*s,x+20*s,y-65*s,outline=color,width=max(2,4*s),fill="#f7f8fb")
        def line(a,b,d,e,width=5): c.create_line(a,b,d,e,fill=color,width=max(1,width*s),capstyle=tk.ROUND)
        line(x,y-54*s,x,y+15*s)
        for side in (-1,1):
            line(x,y-54*s,x+side*28*s,y-20*s,4); line(x+side*28*s,y-20*s,x+side*49*s,y+5*s,4)
            line(x,y+15*s,x+side*18*s,y+58*s); line(x+side*18*s,y+58*s,x+side*32*s,y+105*s)

    def timeline(self):
        for w in self.strip.winfo_children(): w.destroy()
        cv=tk.Canvas(self.strip,height=47,bg=PANEL,highlightthickness=0); sb=tk.Scrollbar(self.strip,orient="horizontal",command=cv.xview); cv.configure(xscrollcommand=sb.set); cv.pack(fill="x"); sb.pack(fill="x")
        inner=tk.Frame(cv,bg=PANEL); cv.create_window((0,0),window=inner,anchor="nw")
        for i in range(len(self.frames)):
            tk.Button(inner,text=f"{i+1:02d}  ●",command=lambda n=i:self.select(n),bg="#3a315f" if i==self.current else PANEL2,fg="#c9bdff" if i==self.current else MUTED,relief="flat",bd=0,width=8,height=2).pack(side="left",padx=(0,5))
        inner.update_idletasks(); cv.configure(scrollregion=cv.bbox("all"))

    def select(self,i): self.current=max(0,min(i,len(self.frames)-1)); self.timeline(); self.draw()
    def add(self): self.frames.insert(self.current+1,dict(self.frames[self.current])); self.select(self.current+1); self.status.config(text="Frame added")
    def duplicate(self): self.add(); self.status.config(text="Frame duplicated")
    def delete(self):
        if len(self.frames)>1: del self.frames[self.current]; self.select(min(self.current,len(self.frames)-1)); self.status.config(text="Frame deleted")
        else: self.status.config(text="Keep at least one frame")
    def toggle_onion(self): self.onion=not self.onion; self.onion_btn.config(bg=ACCENT if self.onion else PANEL2); self.draw()
    def start_drag(self,e):
        ox,oy,sw,sh=self.box(); f=self.frames[self.current]; x,y=ox+f["x"]*sw,oy+f["y"]*sh
        if math.hypot(e.x-x,e.y-y)<100*min(sw/W,sh/H): self.drag=(e.x,e.y,f["x"],f["y"])
    def move_drag(self,e):
        if self.drag:
            ox,oy,sw,sh=self.box(); sx,sy,x,y=self.drag; f=self.frames[self.current]
            f["x"]=min(.96,max(.04,x+(e.x-sx)/sw)); f["y"]=min(.78,max(.18,y+(e.y-sy)/sh)); self.draw()
    def end_drag(self,e):
        if self.drag: self.drag=None; self.status.config(text="Pose updated · Save to keep changes")
    def toggle_play(self):
        self.playing=not self.playing; self.play_btn.config(text="❚❚ Pause" if self.playing else "▶ Play")
        if self.playing: self.step()
        elif hasattr(self,"timer"): self.root.after_cancel(self.timer)
        self.draw()
    def step(self):
        if self.playing: self.current=(self.current+1)%len(self.frames); self.timeline(); self.draw(); self.timer=self.root.after(83,self.step)
    def new(self):
        if messagebox.askyesno("FrameForge","Start a new animation? Unsaved changes will be lost."):
            self.frames=[pose() for _ in range(12)]; self.current=0; self.path=None; self.name.config(text="Untitled Animation"); self.timeline(); self.draw()
    def save(self):
        path=self.path or filedialog.asksaveasfilename(defaultextension=".frameforge",filetypes=[("FrameForge project","*.frameforge"),("JSON","*.json")])
        if path:
            try:
                Path(path).write_text(json.dumps({"format":"frameforge","version":1,"fps":12,"frames":self.frames},indent=2),encoding="utf-8"); self.path=path; self.name.config(text=Path(path).stem); self.status.config(text=f"Saved {Path(path).name}")
            except OSError as e: messagebox.showerror("Save failed",str(e))
    def open(self):
        path=filedialog.askopenfilename(filetypes=[("FrameForge project","*.frameforge *.json"),("All files","*.*")])
        if path:
            try:
                data=json.loads(Path(path).read_text(encoding="utf-8")); frames=data["frames"]
                if not isinstance(frames,list) or not frames: raise ValueError("Project has no frames")
                self.frames=[{"x":float(f.get("x",.5)),"y":float(f.get("y",.52))} for f in frames]; self.current=0; self.path=path; self.name.config(text=Path(path).stem); self.timeline(); self.draw(); self.status.config(text=f"Opened {Path(path).name}")
            except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as e: messagebox.showerror("Could not open project",str(e))
    def export(self):
        path=filedialog.asksaveasfilename(defaultextension=".svg",filetypes=[("SVG image","*.svg")])
        if not path:return
        x,y=self.frames[self.current]["x"]*W,self.frames[self.current]["y"]*H
        svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="#f7f8fb"/><g stroke="#252b38" stroke-width="5" stroke-linecap="round" fill="none"><circle cx="{x}" cy="{y-85}" r="20"/><path d="M{x} {y-54}V{y+15} M{x} {y-54}l-28 34-21 25 M{x} {y-54}l28 34 21 25 M{x} {y+15}l-18 43-14 47 M{x} {y+15}l18 43 14 47"/></g></svg>'''
        try: Path(path).write_text(svg,encoding="utf-8"); self.status.config(text=f"Exported {Path(path).name}")
        except OSError as e: messagebox.showerror("Export failed",str(e))
    def close(self):
        if self.playing and hasattr(self,"timer"): self.root.after_cancel(self.timer)
        self.root.destroy()

if __name__ == "__main__":
    root=tk.Tk(); FrameForge(root); root.mainloop()
