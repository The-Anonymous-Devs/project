#!/usr/bin/env python3
"""FrameForge - Adobe-inspired stick-animation editor prototype.

Requirements:
    pip install PyQt6

Run:
    python x.py
"""

import json
import math
import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "FrameForge"
STAGE_W = 960
STAGE_H = 540


class Pose:
    def __init__(self, x=0.5, y=0.52, lean=0.0, arm=0.0, leg=0.0):
        self.x = x
        self.y = y
        self.lean = lean
        self.arm = arm
        self.leg = leg

    def to_dict(self):
        return {
            "x": self.x,
            "y": self.y,
            "lean": self.lean,
            "arm": self.arm,
            "leg": self.leg,
        }


class StageWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.dragging = False
        self.drag_offset = QPointF(0, 0)
        self.setMouseTracking(True)

    def _map_to_stage(self, pos):
        rect = self.rect()
        padding = 18
        w = max(1, rect.width() - padding * 2)
        h = max(1, rect.height() - padding * 2)
        scale = min(w / STAGE_W, h / STAGE_H)
        stage_w = STAGE_W * scale
        stage_h = STAGE_H * scale
        offset_x = (rect.width() - stage_w) / 2
        offset_y = (rect.height() - stage_h) / 2
        sx = (pos.x() - offset_x) / scale
        sy = (pos.y() - offset_y) / scale
        return QPointF(sx, sy), (offset_x, offset_y, scale)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pose = self.parent.frames[self.parent.current]
        p, _ = self._map_to_stage(event.pos())
        x = pose.x * STAGE_W
        y = pose.y * STAGE_H
        if math.hypot(p.x() - x, p.y() - y) < 80:
            self.dragging = True
            self.drag_offset = QPointF(p.x() - x, p.y() - y)

    def mouseMoveEvent(self, event):
        if not self.dragging:
            return
        p, _ = self._map_to_stage(event.pos())
        pose = self.parent.frames[self.parent.current]
        pose.x = max(0.04, min(0.96, (p.x() - self.drag_offset.x()) / STAGE_W))
        pose.y = max(0.18, min(0.82, (p.y() - self.drag_offset.y()) / STAGE_H))
        self.parent.update_properties()
        self.parent.update_scene()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.parent.status.setText("Pose updated · Save to keep your changes")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, QColor("#f4f6fb"))

        padding = 18
        w = max(1, rect.width() - padding * 2)
        h = max(1, rect.height() - padding * 2)
        scale = min(w / STAGE_W, h / STAGE_H)
        stage_w = STAGE_W * scale
        stage_h = STAGE_H * scale
        offset_x = (rect.width() - stage_w) / 2
        offset_y = (rect.height() - stage_h) / 2

        # stage background
        painter.fillRect(
            offset_x,
            offset_y,
            stage_w,
            stage_h,
            QColor("#f8f9fb"),
        )

        # grid
        grid_color = QColor("#e5eaf3")
        pen = QPen(grid_color, 1)
        painter.setPen(pen)
        for gx in range(0, STAGE_W + 1, 48):
            x = offset_x + gx * scale
            painter.drawLine(int(x), int(offset_y), int(x), int(offset_y + stage_h))
        for gy in range(0, STAGE_H + 1, 48):
            y = offset_y + gy * scale
            painter.drawLine(int(offset_x), int(y), int(offset_x + stage_w), int(y))

        # floor line
        painter.setPen(QPen(QColor("#cfd7e5"), 2))
        painter.drawLine(
            int(offset_x),
            int(offset_y + 0.83 * stage_h),
            int(offset_x + stage_w),
            int(offset_y + 0.83 * stage_h),
        )

        if self.parent.onion and len(self.parent.frames) > 1 and not self.parent.playing:
            prev = self.parent.frames[(self.parent.current - 1) % len(self.parent.frames)]
            self._draw_figure(painter, prev, offset_x, offset_y, scale, QColor("#a0aeff"), ghost=True)

        self._draw_figure(painter, self.parent.frames[self.parent.current], offset_x, offset_y, scale, QColor("#252b38"), ghost=False)

        # stage label
        painter.setPen(QPen(QColor("#9aa5b5"), 1))
        painter.setFont(QFont("Sans Serif", 8))
        painter.drawText(int(offset_x + 12), int(offset_y + 18), "960 × 540")

    def _draw_figure(self, painter, pose, offset_x, offset_y, scale, color, ghost=False):
        x = offset_x + pose.x * STAGE_W * scale
        y = offset_y + pose.y * STAGE_H * scale
        s = scale

        head_r = 20 * s
        painter.setPen(QPen(color, max(2, int(4 * s))))
        painter.setBrush(QColor("#f8f9fb"))
        painter.drawEllipse(int(x - head_r), int(y - 105 * s), int(head_r * 2), int(head_r * 2))

        shoulder_x = x + pose.lean * 10 * s
        shoulder_y = y - 54 * s
        hip_x = x
        hip_y = y + 15 * s

        painter.setPen(QPen(color, max(1, int(5 * s))))
        painter.drawLine(int(x), int(y - 54 * s), int(hip_x), int(hip_y))

        for side in (-1, 1):
            arm = (-0.75 if side < 0 else 0.75) + pose.arm
            elbow_x = shoulder_x + math.sin(arm) * 34 * s
            elbow_y = shoulder_y + math.cos(arm) * 34 * s
            hand_x = shoulder_x + math.sin(arm) * 67 * s
            hand_y = shoulder_y + math.cos(arm) * 67 * s
            painter.drawLine(int(shoulder_x), int(shoulder_y), int(elbow_x), int(elbow_y))
            painter.drawLine(int(elbow_x), int(elbow_y), int(hand_x), int(hand_y))

            leg = (0.50 if side < 0 else -0.50) + pose.leg
            knee_x = hip_x + side * 17 * s + math.sin(leg) * 35 * s
            knee_y = hip_y + 43 * s
            foot_x = hip_x + side * 20 * s + math.sin(leg) * 62 * s
            foot_y = hip_y + 90 * s
            painter.drawLine(int(hip_x), int(hip_y), int(knee_x), int(knee_y))
            painter.drawLine(int(knee_x), int(knee_y), int(foot_x), int(foot_y))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FrameForge — Untitled Animation")
        self.resize(1280, 820)
        self.frames = [Pose() for _ in range(12)]
        self.current = 0
        self.onion = True
        self.playing = False
        self.project_path = None
        self.dragging = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.play_next_frame)

        self._build_ui()
        self.update_scene()
        self.refresh_timeline()

    def _build_ui(self):
        # Header
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet("background:#171b22; color:#e9edf7; border:1px solid #2f3542;")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(16, 8, 16, 8)
        logo = QLabel("✦ FRAMEFORGE")
        logo.setStyleSheet("font-weight:700; font-size:14px;")
        hlay.addWidget(logo)
        brand = QLabel("STICK ANIMATION STUDIO")
        brand.setStyleSheet("color:#9ca6b5; font-size:8px; font-weight:700; letter-spacing:1px;")
        hlay.addWidget(brand)
        spacer = QWidget(); spacer.setSizePolicy(1, 1)
        hlay.addWidget(spacer)
        self.project_name = QLabel("Untitled Animation")
        hlay.addWidget(self.project_name)
        self.new_btn = QPushButton("New")
        self.open_btn = QPushButton("Open")
        self.save_btn = QPushButton("Save")
        self.export_btn = QPushButton("Export SVG")
        self.export_btn.setStyleSheet("background:#8d76ff; color:white; border:none; padding:8px 16px; border-radius:10px;")
        for btn in (self.new_btn, self.open_btn, self.save_btn, self.export_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("background:#20242d; color:#edf0f6; border:1px solid #303642; border-radius:10px; padding:8px 14px;")
        self.new_btn.clicked.connect(self.new_project)
        self.open_btn.clicked.connect(self.open_project)
        self.save_btn.clicked.connect(self.save_project)
        self.export_btn.clicked.connect(self.export_svg)
        hlay.addWidget(self.new_btn)
        hlay.addWidget(self.open_btn)
        hlay.addWidget(self.save_btn)
        hlay.addWidget(self.export_btn)

        self.setCentralWidget(QWidget())
        root = self.centralWidget()
        root.setStyleSheet("background:#111318; color:#e9edf7;")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addWidget(header)

        content = QWidget()
        content.setStyleSheet("background:#111318;")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # left tool rail
        left = QWidget()
        left.setFixedWidth(72)
        left.setStyleSheet("background:#191c23; border:1px solid #2f3542; border-radius:10px;")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 12, 8, 12)
        left_title = QLabel("TOOLS")
        left_title.setStyleSheet("color:#9ca6b5; font-size:8px; font-weight:700; letter-spacing:1px;")
        left_layout.addWidget(left_title, 0, Qt.AlignmentFlag.AlignHCenter)
        left_layout.addStretch(1)
        for label, callback in (("↖", lambda: None), ("＋", self.add_frame), ("◉", self.toggle_onion)):
            btn = QPushButton(label)
            btn.setFixedSize(42, 42)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("background:#20242d; border:1px solid #323947; color:#edf0f6; border-radius:10px; font-size:16px; font-weight:700;")
            if label == "◉":
                self.onion_btn = btn
            btn.clicked.connect(callback)
            left_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
        left_layout.addStretch(2)
        content_layout.addWidget(left)

        # center stage
        stage_wrap = QWidget()
        stage_wrap.setStyleSheet("background:#111318;")
        stage_layout = QVBoxLayout(stage_wrap)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(6)

        stage_header = QWidget(); stage_header.setFixedHeight(28)
        stage_header.setStyleSheet("background:#111318;")
        stage_head_l = QHBoxLayout(stage_header)
        stage_head_l.setContentsMargins(0, 0, 0, 0)
        stage_label = QLabel("STAGE")
        stage_label.setStyleSheet("color:#edf0f6; font-size:10px; font-weight:700;")
        stage_head_l.addWidget(stage_label)
        self.frame_counter = QLabel("Frame 1 / 12")
        self.frame_counter.setStyleSheet("color:#9ca6b5; font-size:9px;")
        stage_head_l.addWidget(self.frame_counter, 0, Qt.AlignmentFlag.AlignRight)
        stage_layout.addWidget(stage_header)

        self.stage = StageWidget(self)
        self.stage.setStyleSheet("background:#252a33; border:1px solid #313b4d; border-radius:10px;")
        stage_layout.addWidget(self.stage)

        content_layout.addWidget(stage_wrap, 1)

        # properties
        props = QWidget()
        props.setFixedWidth(210)
        props.setStyleSheet("background:#191c23; border:1px solid #2f3542; border-radius:10px;")
        props_layout = QVBoxLayout(props)
        props_layout.setContentsMargins(14, 14, 14, 14)
        props_layout.setSpacing(8)

        title = QLabel("PROPERTIES")
        title.setStyleSheet("color:#edf0f6; font-size:10px; font-weight:700;")
        props_layout.addWidget(title)

        for label, value in (("Stage", "960 × 540"), ("Frame rate", "12 fps")):
            row = QWidget(); row.setStyleSheet("background:transparent;")
            rlay = QHBoxLayout(row); rlay.setContentsMargins(0, 0, 0, 0)
            lab = QLabel(label); lab.setStyleSheet("color:#9ca6b5; font-size:9px;")
            val = QLabel(value); val.setStyleSheet("color:#edf0f6; font-size:9px;")
            rlay.addWidget(lab); rlay.addWidget(val, 0, Qt.AlignmentFlag.AlignRight)
            props_layout.addWidget(row)

        props_layout.addWidget(QLabel(""))
        self.position_label = QLabel("Position 50%, 52%")
        self.position_label.setStyleSheet("color:#edf0f6; font-size:9px;")
        props_layout.addWidget(self.position_label)

        self.lean_slider = self._make_slider("Lean", -100, 100, 0)
        self.arm_slider = self._make_slider("Arm", -100, 100, 0)
        self.leg_slider = self._make_slider("Leg", -100, 100, 0)
        props_layout.addWidget(self.lean_slider)
        props_layout.addWidget(self.arm_slider)
        props_layout.addWidget(self.leg_slider)

        info = QLabel(
            "Drag the figure to pose it, add frames, and preview the motion.\n\nEach frame is a pose; the timeline controls playback."
        )
        info.setStyleSheet("color:#9ca6b5; font-size:9px; line-height:1.4;")
        info.setWordWrap(True)
        props_layout.addWidget(info)
        content_layout.addWidget(props)

        layout.addWidget(content)

        # timeline
        timeline = QWidget()
        timeline.setFixedHeight(170)
        timeline.setStyleSheet("background:#191c23; border:1px solid #2f3542; border-radius:10px;")
        tl_layout = QVBoxLayout(timeline)
        tl_layout.setContentsMargins(12, 10, 12, 10)

        tl_top = QWidget(); tl_top.setStyleSheet("background:transparent;")
        tlay = QHBoxLayout(tl_top); tlay.setContentsMargins(0, 0, 0, 0)
        tlabel = QLabel("TIMELINE"); tlabel.setStyleSheet("color:#edf0f6; font-size:10px; font-weight:700;")
        tlay.addWidget(tlabel)
        tlay.addStretch(1)
        add_tb = QPushButton("＋ Frame")
        dup_tb = QPushButton("Duplicate")
        del_tb = QPushButton("Delete")
        play_tb = QPushButton("▶ Play")
        for btn in (add_tb, dup_tb, del_tb, play_tb):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("background:#20242d; color:#edf0f6; border:1px solid #303642; border-radius:10px; padding:6px 12px;")
        add_tb.clicked.connect(self.add_frame)
        dup_tb.clicked.connect(self.duplicate_frame)
        del_tb.clicked.connect(self.delete_frame)
        play_tb.clicked.connect(self.toggle_play)
        self.play_btn = play_tb
        tlay.addWidget(add_tb); tlay.addWidget(dup_tb); tlay.addWidget(del_tb); tlay.addWidget(play_tb)
        tl_layout.addWidget(tl_top)

        self.timeline_area = QWidget(); self.timeline_area.setStyleSheet("background:transparent;")
        self.timeline_layout = QHBoxLayout(self.timeline_area)
        self.timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_layout.setSpacing(6)
        tl_layout.addWidget(self.timeline_area)

        footer = QWidget(); footer.setStyleSheet("background:transparent;")
        fly = QHBoxLayout(footer); fly.setContentsMargins(0, 0, 0, 0)
        fly.addWidget(QLabel("12 fps"))
        self.status = QLabel("Ready · Drag the figure to pose this frame")
        self.status.setStyleSheet("color:#9ca6b5; font-size:9px;")
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight)
        fly.addWidget(self.status)
        tl_layout.addWidget(footer)
        layout.addWidget(timeline)

        # connect sliders
        self.lean_slider.valueChanged.connect(lambda v: self.set_pose_value("lean", v / 100.0))
        self.arm_slider.valueChanged.connect(lambda v: self.set_pose_value("arm", v / 100.0))
        self.leg_slider.valueChanged.connect(lambda v: self.set_pose_value("leg", v / 100.0))

    def _make_slider(self, title, minimum, maximum, default):
        wrapper = QWidget(); wrapper.setStyleSheet("background:transparent;")
        wlay = QVBoxLayout(wrapper); wlay.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title); label.setStyleSheet("color:#9ca6b5; font-size:9px;")
        wlay.addWidget(label)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(default)
        slider.setStyleSheet("QSlider::groove:horizontal {background:#2a2f39; height:4px; border-radius:2px;} QSlider::handle:horizontal {background:#8d76ff; width:12px; height:12px; border-radius:6px; margin:-4px 0;}" )
        wlay.addWidget(slider)
        return wrapper

    def set_pose_value(self, key, value):
        p = self.frames[self.current]
        setattr(p, key, value)
        self.update_scene()

    def update_properties(self):
        pose = self.frames[self.current]
        self.position_label.setText(f"Position {round(pose.x * 100)}%, {round(pose.y * 100)}%")
        self.lean_slider.setValue(int(round(pose.lean * 100)))
        self.arm_slider.setValue(int(round(pose.arm * 100)))
        self.leg_slider.setValue(int(round(pose.leg * 100)))

    def update_scene(self):
        self.frame_counter.setText(f"Frame {self.current + 1} / {len(self.frames)}")
        self.update_properties()
        self.stage.update()

    def refresh_timeline(self):
        for i in reversed(range(self.timeline_layout.count())):
            widget = self.timeline_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        for i in range(len(self.frames)):
            btn = QPushButton(f"{i + 1:02d}\n●")
            btn.setFixedSize(64, 40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "background:#2b3040; color:#c9bdff; border:1px solid #3a4154; border-radius:8px; font-size:10px; font-weight:700;"
                if i == self.current else
                "background:#1d2129; color:#9ca6b5; border:1px solid #2a2f3a; border-radius:8px; font-size:10px;"
            )
            btn.clicked.connect(lambda _, index=i: self.select_frame(index))
            self.timeline_layout.addWidget(btn)

    def select_frame(self, index):
        self.current = max(0, min(index, len(self.frames) - 1))
        self.refresh_timeline()
        self.update_scene()

    def add_frame(self):
        source = self.frames[self.current]
        clone = Pose(source.x, source.y, source.lean, source.arm, source.leg)
        self.frames.insert(self.current + 1, clone)
        self.current += 1
        self.refresh_timeline()
        self.update_scene()
        self.status.setText("Frame added")

    def duplicate_frame(self):
        self.add_frame()
        self.status.setText("Frame duplicated")

    def delete_frame(self):
        if len(self.frames) <= 1:
            self.status.setText("At least one frame is required")
            return
        del self.frames[self.current]
        self.current = max(0, min(self.current, len(self.frames) - 1))
        self.refresh_timeline()
        self.update_scene()
        self.status.setText("Frame deleted")

    def toggle_onion(self):
        self.onion = not self.onion
        self.onion_btn.setStyleSheet(
            "background:#8d76ff; color:#ffffff; border:1px solid #8d76ff; border-radius:10px; font-size:16px; font-weight:700;"
            if self.onion else
            "background:#20242d; color:#edf0f6; border:1px solid #323947; border-radius:10px; font-size:16px; font-weight:700;"
        )
        self.stage.update()

    def toggle_play(self):
        self.playing = not self.playing
        self.play_btn.setText("❚❚ Pause" if self.playing else "▶ Play")
        if self.playing:
            self.timer.start(83)
            self.status.setText("Playback running")
        else:
            self.timer.stop()
            self.status.setText("Playback paused")
        self.stage.update()

    def play_next_frame(self):
        if not self.playing:
            return
        self.current = (self.current + 1) % len(self.frames)
        self.refresh_timeline()
        self.update_scene()

    def new_project(self):
        reply = QMessageBox.question(
            self,
            APP_NAME,
            "Start a new animation? Unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.frames = [Pose() for _ in range(12)]
        self.current = 0
        self.project_path = None
        self.project_name.setText("Untitled Animation")
        self.refresh_timeline()
        self.update_scene()

    def save_project(self):
        path = self.project_path or QFileDialog.getSaveFileName(
            self,
            "Save animation",
            str(Path.home()),
            "FrameForge project (*.frameforge);;JSON (*.json)",
        )[0]
        if not path:
            return
        data = {
            "format": "frameforge",
            "version": 1,
            "fps": 12,
            "frames": [p.to_dict() for p in self.frames],
        }
        try:
            Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.project_path = path
            self.project_name.setText(Path(path).stem)
            self.status.setText(f"Saved {Path(path).name}")
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def open_project(self):
        path = QFileDialog.getOpenFileName(
            self,
            "Open animation",
            str(Path.home()),
            "FrameForge project (*.frameforge *.json);;All files (*.*)",
        )[0]
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            frames = raw.get("frames", [])
            if not frames:
                raise ValueError("Project contains no frames")
            self.frames = []
            for item in frames:
                self.frames.append(
                    Pose(
                        x=float(item.get("x", 0.5)),
                        y=float(item.get("y", 0.52)),
                        lean=float(item.get("lean", 0.0)),
                        arm=float(item.get("arm", 0.0)),
                        leg=float(item.get("leg", 0.0)),
                    )
                )
            self.current = 0
            self.project_path = path
            self.project_name.setText(Path(path).stem)
            self.refresh_timeline(); self.update_scene(); self.status.setText(f"Opened {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Could not open project", str(exc))

    def export_svg(self):
        path = QFileDialog.getSaveFileName(self, "Export current frame as SVG", str(Path.home()), "SVG (*.svg)")[0]
        if not path:
            return
        pose = self.frames[self.current]
        x = pose.x * STAGE_W
        y = pose.y * STAGE_H
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{STAGE_W}" height="{STAGE_H}" viewBox="0 0 {STAGE_W} {STAGE_H}">
<rect width="100%" height="100%" fill="#f7f8fb"/>
<g stroke="#252b38" stroke-width="5" stroke-linecap="round" fill="none">
<circle cx="{x:.1f}" cy="{y-85:.1f}" r="20"/>
<path d="M {x:.1f} {y-54:.1f} L {x:.1f} {y+15:.1f}"/>
<path d="M {x:.1f} {y-54:.1f} L {x-28:.1f} {y-20:.1f} L {x-49:.1f} {y+5:.1f}"/>
<path d="M {x:.1f} {y-54:.1f} L {x+28:.1f} {y-20:.1f} L {x+49:.1f} {y+5:.1f}"/>
<path d="M {x:.1f} {y+15:.1f} L {x-18:.1f} {y+58:.1f} L {x-32:.1f} {y+105:.1f}"/>
<path d="M {x:.1f} {y+15:.1f} L {x+18:.1f} {y+58:.1f} L {x+32:.1f} {y+105:.1f}"/>
</g>
</svg>'''
        try:
            Path(path).write_text(svg, encoding="utf-8")
            self.status.setText(f"Exported {Path(path).name}")
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
