"""
dashboard.py - Futuristic Desktop Dashboard for AIRMOUSE AI
Modern dark cyber-themed graphical user interface built with CustomTkinter.
"""

import sys
import time
import threading
import queue
from datetime import datetime
from typing import Optional, List, Tuple

import cv2
import numpy as np
from PIL import Image
import customtkinter as ctk

from settings import AppSettings
from hand_tracker import HandTracker
from gesture_recognizer import GestureRecognizer, GestureType
from mouse_controller import MouseController

# Set default theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class FuturisticColors:
    BG_DARK = "#0a0e17"
    BG_CARD = "#111827"
    BG_CARD_ALT = "#162032"
    BORDER_CYAN = "#00f0ff"
    BORDER_DIM = "#1e293b"
    ACCENT_CYAN = "#00f0ff"
    ACCENT_BLUE = "#3b82f6"
    ACCENT_GREEN = "#10b981"
    ACCENT_AMBER = "#f59e0b"
    ACCENT_RED = "#ef4444"
    TEXT_MAIN = "#f8fafc"
    TEXT_MUTED = "#94a3b8"


class AirMouseDashboard(ctk.CTk):
    """Main Application Window and Futuristic HUD Controller."""

    def __init__(self, settings: Optional[AppSettings] = None):
        super().__init__()

        self.settings = settings or AppSettings()
        self.tracker = HandTracker(
            camera_index=self.settings.camera_index,
            width=self.settings.camera_width,
            height=self.settings.camera_height,
        )
        self.recognizer = GestureRecognizer()
        self.mouse_ctrl = MouseController(self.settings)

        # Worker thread and synchronization
        self.worker_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self.event_queue: queue.Queue = queue.Queue()

        # UI state variables
        self.current_gesture_str = "STANDBY"
        self.is_hand_detected = False
        self.fps_display = 0.0
        self.latency_display = 0.0

        # Configure Main Window
        self.title("AIRMOUSE AI — Futuristic Gesture-Controlled Computer System")
        self.geometry("1300x860")
        self.minsize(1100, 750)
        self.configure(fg_color=FuturisticColors.BG_DARK)

        # Handle window close & shortcuts
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Escape>", lambda event: self.trigger_emergency_stop())

        # Build UI Components
        self._build_header()
        self._build_main_layout()
        self._create_empty_camera_placeholder()

        # Start UI periodic update loops
        self.after(30, self._update_camera_frame)
        self.after(100, self._process_events)

        self.log_event("AIRMOUSE AI System Initialized.")
        self.log_event("Mouse control is currently STANDBY (Safe mode).")

    def _build_header(self) -> None:
        """Construct top cyber-styled header bar."""
        header = ctk.CTkFrame(
            self,
            fg_color=FuturisticColors.BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=FuturisticColors.BORDER_DIM,
            height=70,
        )
        header.pack(fill="x", padx=18, pady=(14, 10))

        # Title & Subtitle
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=10)

        title_lbl = ctk.CTkLabel(
            title_box,
            text="⚡ AIRMOUSE AI",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=FuturisticColors.ACCENT_CYAN,
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            title_box,
            text="TOUCHLESS HUMAN-COMPUTER INTERACTION SYSTEM",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=FuturisticColors.TEXT_MUTED,
        )
        sub_lbl.pack(anchor="w")

        # Right-side status indicators
        status_box = ctk.CTkFrame(header, fg_color="transparent")
        status_box.pack(side="right", padx=20, pady=10)

        # Camera status pill
        self.camera_status_badge = ctk.CTkLabel(
            status_box,
            text="📷 CAMERA: DISCONNECTED",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=FuturisticColors.TEXT_MUTED,
            fg_color="#1f2937",
            corner_radius=8,
            padx=12,
            pady=6,
        )
        self.camera_status_badge.pack(side="left", padx=8)

        # Mouse control status pill
        self.mouse_status_badge = ctk.CTkLabel(
            status_box,
            text="🖱️ MOUSE: STANDBY",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=FuturisticColors.TEXT_MUTED,
            fg_color="#1f2937",
            corner_radius=8,
            padx=12,
            pady=6,
        )
        self.mouse_status_badge.pack(side="left", padx=8)

    def _build_main_layout(self) -> None:
        """Construct primary split workspace: Left (Camera & HUD), Right (Controls & Stats)."""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=18, pady=6)

        # Left Column: Video Preview and Live Telemetry (approx 62% width)
        left_col = ctk.CTkFrame(content, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self._build_video_panel(left_col)
        self._build_telemetry_bar(left_col)
        self._build_gesture_guide(left_col)

        # Right Column: Controls, Sliders, Toggles, and Activity Log (approx 38% width)
        right_col = ctk.CTkFrame(content, fg_color="transparent", width=460)
        right_col.pack(side="right", fill="both", padx=(10, 0))

        self._build_controls_card(right_col)
        self._build_tuning_card(right_col)
        self._build_activity_card(right_col)

    def _build_video_panel(self, parent: ctk.CTkFrame) -> None:
        """Webcam display screen with cyber border."""
        self.video_frame = ctk.CTkFrame(
            parent,
            fg_color="#000000",
            corner_radius=12,
            border_width=2,
            border_color=FuturisticColors.BORDER_DIM,
        )
        self.video_frame.pack(fill="both", expand=True, pady=(0, 8))

        self.video_label = ctk.CTkLabel(
            self.video_frame,
            text="",
            fg_color="#000000",
            corner_radius=10,
        )
        self.video_label.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_telemetry_bar(self, parent: ctk.CTkFrame) -> None:
        """Telemetry indicators below webcam (Hand state, Active gesture, FPS/Latency)."""
        bar = ctk.CTkFrame(
            parent,
            fg_color=FuturisticColors.BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=FuturisticColors.BORDER_DIM,
            height=50,
        )
        bar.pack(fill="x", pady=(0, 8))

        # Hand detected indicator
        self.hand_detected_badge = ctk.CTkLabel(
            bar,
            text="● NO HAND DETECTED",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=FuturisticColors.ACCENT_RED,
            padx=14,
        )
        self.hand_detected_badge.pack(side="left", pady=10)

        # Active Gesture indicator
        self.gesture_badge = ctk.CTkLabel(
            bar,
            text="GESTURE: SEARCHING",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=FuturisticColors.ACCENT_CYAN,
            padx=14,
        )
        self.gesture_badge.pack(side="left", expand=True, pady=10)

        # Live Metrics
        self.metrics_badge = ctk.CTkLabel(
            bar,
            text="FPS: 0.0  |  0.0 ms",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=FuturisticColors.TEXT_MUTED,
            padx=14,
        )
        self.metrics_badge.pack(side="right", pady=10)

    def _build_gesture_guide(self, parent: ctk.CTkFrame) -> None:
        """Visual gesture quick reference card."""
        guide = ctk.CTkFrame(
            parent,
            fg_color=FuturisticColors.BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=FuturisticColors.BORDER_DIM,
            height=85,
        )
        guide.pack(fill="x", pady=(0, 0))

        lbl = ctk.CTkLabel(
            guide,
            text="GESTURE MATRIX REFERENCE",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=FuturisticColors.TEXT_MUTED,
        )
        lbl.pack(anchor="w", padx=14, pady=(6, 2))

        grid = ctk.CTkFrame(guide, fg_color="transparent")
        grid.pack(fill="x", padx=10, pady=(0, 6))

        refs = [
            ("☝️ Index Up", "Cursor Move"),
            ("🤏 Thumb+Index", "Left Click"),
            ("✊ Pinch & Hold", "Drag & Drop"),
            ("✌️ Thumb+Mid", "V-Scroll"),
            ("🖐️ Open Palm", "Pause Action"),
            ("🤛 Closed Fist", "Stop Cursor"),
        ]

        for i, (gesture_name, action_name) in enumerate(refs):
            card = ctk.CTkFrame(grid, fg_color=FuturisticColors.BG_CARD_ALT, corner_radius=6)
            card.pack(side="left", fill="both", expand=True, padx=3)

            g_lbl = ctk.CTkLabel(
                card,
                text=gesture_name,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=FuturisticColors.ACCENT_CYAN,
            )
            g_lbl.pack(pady=(3, 0))

            a_lbl = ctk.CTkLabel(
                card,
                text=action_name,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=FuturisticColors.TEXT_MUTED,
            )
            a_lbl.pack(pady=(0, 3))

    def _build_controls_card(self, parent: ctk.CTkFrame) -> None:
        """Main system execution buttons."""
        card = ctk.CTkFrame(
            parent,
            fg_color=FuturisticColors.BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=FuturisticColors.BORDER_DIM,
        )
        card.pack(fill="x", pady=(0, 8))

        lbl = ctk.CTkLabel(
            card,
            text="COMMAND CONTROLS",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=FuturisticColors.ACCENT_CYAN,
        )
        lbl.pack(anchor="w", padx=16, pady=(10, 6))

        # Row 1: Start/Stop Camera & Enable/Disable Mouse
        r1 = ctk.CTkFrame(card, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=4)

        self.btn_camera = ctk.CTkButton(
            r1,
            text="START CAMERA",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#1e3a8a",
            hover_color="#2563eb",
            command=self.toggle_camera,
            height=36,
        )
        self.btn_camera.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_mouse = ctk.CTkButton(
            r1,
            text="ENABLE MOUSE",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#065f46",
            hover_color="#059669",
            command=self.toggle_mouse_control,
            height=36,
        )
        self.btn_mouse.pack(side="right", fill="x", expand=True, padx=(6, 0))

        # Row 2: Pause/Resume & Emergency Stop
        r2 = ctk.CTkFrame(card, fg_color="transparent")
        r2.pack(fill="x", padx=14, pady=(4, 12))

        self.btn_pause = ctk.CTkButton(
            r2,
            text="PAUSE",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#78350f",
            hover_color="#b45309",
            command=self.toggle_pause,
            height=36,
        )
        self.btn_pause.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_emergency = ctk.CTkButton(
            r2,
            text="STOP ALL (ESC)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#7f1d1d",
            hover_color="#b91c1c",
            command=self.trigger_emergency_stop,
            height=36,
        )
        self.btn_emergency.pack(side="right", fill="x", expand=True, padx=(6, 0))

    def _build_tuning_card(self, parent: ctk.CTkFrame) -> None:
        """Sliders for sensitivity, smoothing, pinch threshold, and gesture toggles."""
        card = ctk.CTkFrame(
            parent,
            fg_color=FuturisticColors.BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=FuturisticColors.BORDER_DIM,
        )
        card.pack(fill="x", pady=(0, 8))

        lbl = ctk.CTkLabel(
            card,
            text="CALIBRATION & SENSITIVITY",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=FuturisticColors.ACCENT_CYAN,
        )
        lbl.pack(anchor="w", padx=16, pady=(10, 4))

        # Sensitivity Slider
        self.lbl_sens_val = ctk.CTkLabel(
            card,
            text=f"Sensitivity: {self.settings.sensitivity:.1f}x",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=FuturisticColors.TEXT_MAIN,
        )
        self.lbl_sens_val.pack(anchor="w", padx=16, pady=(2, 0))

        self.slider_sens = ctk.CTkSlider(
            card,
            from_=0.8,
            to=3.2,
            number_of_steps=24,
            command=self._on_sensitivity_change,
        )
        self.slider_sens.set(self.settings.sensitivity)
        self.slider_sens.pack(fill="x", padx=16, pady=(2, 8))

        # Smoothing Slider
        self.lbl_smooth_val = ctk.CTkLabel(
            card,
            text=f"Cursor Smoothing: {self.settings.smoothing_factor:.2f}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=FuturisticColors.TEXT_MAIN,
        )
        self.lbl_smooth_val.pack(anchor="w", padx=16, pady=(2, 0))

        self.slider_smooth = ctk.CTkSlider(
            card,
            from_=0.1,
            to=0.9,
            number_of_steps=16,
            command=self._on_smoothing_change,
        )
        self.slider_smooth.set(self.settings.smoothing_factor)
        self.slider_smooth.pack(fill="x", padx=16, pady=(2, 8))

        # Pinch Threshold Slider
        self.lbl_pinch_val = ctk.CTkLabel(
            card,
            text=f"Pinch Threshold: {self.settings.pinch_threshold:.3f}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=FuturisticColors.TEXT_MAIN,
        )
        self.lbl_pinch_val.pack(anchor="w", padx=16, pady=(2, 0))

        self.slider_pinch = ctk.CTkSlider(
            card,
            from_=0.03,
            to=0.09,
            number_of_steps=20,
            command=self._on_pinch_change,
        )
        self.slider_pinch.set(self.settings.pinch_threshold)
        self.slider_pinch.pack(fill="x", padx=16, pady=(2, 10))

        # Feature Switches Grid
        switch_frame = ctk.CTkFrame(card, fg_color="transparent")
        switch_frame.pack(fill="x", padx=16, pady=(0, 10))

        # Row 1 switches
        r1 = ctk.CTkFrame(switch_frame, fg_color="transparent")
        r1.pack(fill="x", pady=2)

        self.sw_cursor = ctk.CTkSwitch(
            r1,
            text="Move Cursor",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self._toggle_setting("enable_cursor_movement", self.sw_cursor),
        )
        self.sw_cursor.select() if self.settings.enable_cursor_movement else self.sw_cursor.deselect()
        self.sw_cursor.pack(side="left", expand=True)

        self.sw_click = ctk.CTkSwitch(
            r1,
            text="Left-Click",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self._toggle_setting("enable_left_click", self.sw_click),
        )
        self.sw_click.select() if self.settings.enable_left_click else self.sw_click.deselect()
        self.sw_click.pack(side="right", expand=True)

        # Row 2 switches
        r2 = ctk.CTkFrame(switch_frame, fg_color="transparent")
        r2.pack(fill="x", pady=2)

        self.sw_drag = ctk.CTkSwitch(
            r2,
            text="Drag & Drop",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self._toggle_setting("enable_drag_and_drop", self.sw_drag),
        )
        self.sw_drag.select() if self.settings.enable_drag_and_drop else self.sw_drag.deselect()
        self.sw_drag.pack(side="left", expand=True)

        self.sw_scroll = ctk.CTkSwitch(
            r2,
            text="V-Scroll",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self._toggle_setting("enable_scrolling", self.sw_scroll),
        )
        self.sw_scroll.select() if self.settings.enable_scrolling else self.sw_scroll.deselect()
        self.sw_scroll.pack(side="right", expand=True)

        # Row 3 switches
        r3 = ctk.CTkFrame(switch_frame, fg_color="transparent")
        r3.pack(fill="x", pady=2)

        self.sw_dot = ctk.CTkSwitch(
            r3,
            text="🔴/🔵 Cursor Halo",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self._toggle_setting("show_cursor_dot", self.sw_dot),
        )
        self.sw_dot.select() if getattr(self.settings, "show_cursor_dot", True) else self.sw_dot.deselect()
        self.sw_dot.pack(side="left", expand=True)

    def _build_activity_card(self, parent: ctk.CTkFrame) -> None:
        """Activity log displaying system events."""
        card = ctk.CTkFrame(
            parent,
            fg_color=FuturisticColors.BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=FuturisticColors.BORDER_DIM,
        )
        card.pack(fill="both", expand=True)

        lbl = ctk.CTkLabel(
            card,
            text="SYSTEM ACTIVITY LOG",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=FuturisticColors.ACCENT_CYAN,
        )
        lbl.pack(anchor="w", padx=16, pady=(10, 4))

        self.log_textbox = ctk.CTkTextbox(
            card,
            fg_color="#080c14",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8,
            border_width=1,
            border_color="#1f2937",
        )
        self.log_textbox.pack(fill="both", expand=True, padx=14, pady=(2, 12))
        self.log_textbox.configure(state="disabled")

    def _create_empty_camera_placeholder(self) -> None:
        """Display cyber graphic placeholder when camera is not feeding."""
        w, h = 640, 480
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:] = (12, 15, 22)

        # Draw tech grid lines
        grid_step = 40
        for x in range(0, w, grid_step):
            cv2.line(img, (x, 0), (x, h), (24, 30, 42), 1)
        for y in range(0, h, grid_step):
            cv2.line(img, (0, y), (w, y), (24, 30, 42), 1)

        # Central text
        cv2.putText(
            img,
            "AIRMOUSE AI — SENSORS STANDBY",
            (w // 2 - 180, h // 2 - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 240, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            img,
            "CLICK 'START CAMERA' TO INITIALIZE OPTICAL STREAM",
            (w // 2 - 210, h // 2 + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (150, 170, 190),
            1,
            cv2.LINE_AA,
        )

        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        ctk_img = ctk.CTkImage(pil_img, size=(640, 480))
        self.video_label.configure(image=ctk_img)
        self.video_label.image = ctk_img

    # ---- Event Logging ----
    def log_event(self, message: str) -> None:
        """Enqueue message to appear in the activity log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.event_queue.put(f"[{timestamp}] {message}")

    def _process_events(self) -> None:
        """Drain event queue and append to GUI textbox."""
        has_new = False
        while not self.event_queue.empty():
            entry = self.event_queue.get_nowait()
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", entry + "\n")
            has_new = True

        if has_new:
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")

        self.after(120, self._process_events)

    # ---- Controls & Callbacks ----
    def toggle_camera(self) -> None:
        """Start or stop the webcam thread."""
        if not self.is_running:
            success = self.tracker.start_camera()
            if not success:
                self.log_event("ERROR: Failed to initialize webcam.")
                return

            self.is_running = True
            self.btn_camera.configure(text="STOP CAMERA", fg_color="#b91c1c", hover_color="#dc2626")
            self.camera_status_badge.configure(text="📷 CAMERA: ONLINE", text_color=FuturisticColors.ACCENT_GREEN, fg_color="#064e3b")
            self.video_frame.configure(border_color=FuturisticColors.BORDER_CYAN)

            # Spawn worker thread
            self.worker_thread = threading.Thread(target=self._camera_processing_loop, daemon=True)
            self.worker_thread.start()
            self.log_event("Webcam stream started. Hand tracking active.")
        else:
            self.is_running = False
            self.tracker.stop_camera()
            self.mouse_ctrl.release_all()
            self.btn_camera.configure(text="START CAMERA", fg_color="#1e3a8a", hover_color="#2563eb")
            self.camera_status_badge.configure(text="📷 CAMERA: DISCONNECTED", text_color=FuturisticColors.TEXT_MUTED, fg_color="#1f2937")
            self.video_frame.configure(border_color=FuturisticColors.BORDER_DIM)
            self._create_empty_camera_placeholder()
            self.hand_detected_badge.configure(text="● NO HAND DETECTED", text_color=FuturisticColors.ACCENT_RED)
            self.gesture_badge.configure(text="GESTURE: STANDBY", text_color=FuturisticColors.TEXT_MUTED)
            self.metrics_badge.configure(text="FPS: 0.0  |  0.0 ms")
            self.log_event("Webcam stream stopped.")

    def toggle_mouse_control(self) -> None:
        """Enable or disable mouse actions."""
        if not self.is_running:
            self.toggle_camera()

        self.settings.mouse_control_enabled = not self.settings.mouse_control_enabled
        if self.settings.mouse_control_enabled:
            # Re-arm failsafe flag and reset tracking state
            self.mouse_ctrl.failsafe_triggered = False
            self.mouse_ctrl.has_previous_position = False
            self.settings.emergency_stop = False
            self.btn_mouse.configure(text="DISABLE MOUSE", fg_color="#b91c1c", hover_color="#dc2626")
            self.mouse_status_badge.configure(text="🖱️ MOUSE: LIVE", text_color=FuturisticColors.ACCENT_GREEN, fg_color="#064e3b")
            self.log_event("ACTIVE: Mouse control ENABLED across Windows desktop.")
        else:
            self.mouse_ctrl.release_all()
            self.btn_mouse.configure(text="ENABLE MOUSE", fg_color="#065f46", hover_color="#059669")
            self.mouse_status_badge.configure(text="🖱️ MOUSE: STANDBY", text_color=FuturisticColors.TEXT_MUTED, fg_color="#1f2937")
            self.log_event("STANDBY: Mouse control DISABLED.")

    def toggle_pause(self) -> None:
        """Pause or resume mouse control actions."""
        self.settings.is_paused = not self.settings.is_paused
        if self.settings.is_paused:
            self.mouse_ctrl.release_all()
            self.btn_pause.configure(text="RESUME", fg_color="#15803d", hover_color="#16a34a")
            self.mouse_status_badge.configure(text="⏸️ MOUSE: PAUSED", text_color=FuturisticColors.ACCENT_AMBER, fg_color="#451a03")
            self.log_event("System PAUSED. Mouse control suspended.")
        else:
            self.btn_pause.configure(text="PAUSE", fg_color="#78350f", hover_color="#b45309")
            if self.settings.mouse_control_enabled:
                self.mouse_status_badge.configure(text="🖱️ MOUSE: LIVE", text_color=FuturisticColors.ACCENT_GREEN, fg_color="#064e3b")
            else:
                self.mouse_status_badge.configure(text="🖱️ MOUSE: STANDBY", text_color=FuturisticColors.TEXT_MUTED, fg_color="#1f2937")
            self.log_event("System RESUMED.")

    def trigger_emergency_stop(self) -> None:
        """Emergency Stop shortcut / button handler."""
        self.settings.emergency_stop = True
        self.settings.mouse_control_enabled = False
        self.mouse_ctrl.release_all()
        self.btn_mouse.configure(text="ENABLE MOUSE", fg_color="#065f46", hover_color="#059669")
        self.mouse_status_badge.configure(text="🛑 EMERGENCY STOPPED", text_color="#ef4444", fg_color="#450a0a")
        self.log_event("EMERGENCY STOP TRIGGERED: Mouse control immediately disabled.")

    def _on_sensitivity_change(self, val: float) -> None:
        self.settings.sensitivity = round(val, 2)
        self.lbl_sens_val.configure(text=f"Sensitivity: {self.settings.sensitivity:.1f}x")

    def _on_smoothing_change(self, val: float) -> None:
        self.settings.smoothing_factor = round(val, 2)
        self.lbl_smooth_val.configure(text=f"Cursor Smoothing: {self.settings.smoothing_factor:.2f}")

    def _on_pinch_change(self, val: float) -> None:
        self.settings.pinch_threshold = round(val, 3)
        self.settings.scroll_pinch_threshold = round(val, 3)
        self.lbl_pinch_val.configure(text=f"Pinch Threshold: {self.settings.pinch_threshold:.3f}")

    def _toggle_setting(self, attr_name: str, widget: ctk.CTkSwitch) -> None:
        is_active = bool(widget.get())
        setattr(self.settings, attr_name, is_active)
        state_str = "Enabled" if is_active else "Disabled"
        self.log_event(f"Setting updated: {attr_name} -> {state_str}")

    # ---- Camera Processing Worker Thread ----
    def _camera_processing_loop(self) -> None:
        """Background thread handling continuous webcam capture, inference, and mouse execution."""
        last_gesture_enum = GestureType.NO_HAND

        while self.is_running:
            success, raw_frame, norm_lms, px_lms = self.tracker.process_frame(mirror=True)
            if not success or raw_frame is None:
                time.sleep(0.01)
                continue

            # Classify Gesture
            gesture_enum, meta = self.recognizer.classify_gesture(
                norm_lms,
                pinch_threshold=self.settings.pinch_threshold,
                scroll_pinch_threshold=self.settings.scroll_pinch_threshold,
                drag_hold_duration=self.settings.drag_hold_duration,
                enable_drag=self.settings.enable_drag_and_drop,
            )

            # Log significant gesture state changes
            if gesture_enum != last_gesture_enum:
                if gesture_enum != GestureType.OTHER:
                    self.log_event(f"Recognized: {gesture_enum.value}")
                last_gesture_enum = gesture_enum

            # Execute Mouse Actions safely
            self.mouse_ctrl.execute_actions(
                gesture_enum,
                meta,
                on_event_cb=self.log_event,
            )

            # Determine pinch point for visual tether
            pinch_active = gesture_enum in (GestureType.PINCH_INDEX, GestureType.DRAGGING, GestureType.PINCH_MIDDLE)
            pinch_target = None
            if pinch_active and px_lms and len(px_lms) == 21:
                if gesture_enum == GestureType.PINCH_MIDDLE:
                    pinch_target = px_lms[HandTracker.MIDDLE_TIP]
                else:
                    pinch_target = px_lms[HandTracker.INDEX_TIP]

            # Render Futuristic Cyber HUD onto frame
            annotated_frame = self.tracker.draw_futuristic_hud(
                frame=raw_frame,
                pixel_landmarks=px_lms,
                active_gesture=gesture_enum.value,
                mouse_enabled=self.settings.mouse_control_enabled,
                is_paused=self.settings.is_paused,
                margin_x=self.settings.margin_x,
                margin_y=self.settings.margin_y,
                pinch_active=pinch_active,
                pinch_point=pinch_target,
            )

            # Pass to UI via queue (drop stale frames if queue is full)
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass

            self.frame_queue.put({
                "frame": annotated_frame,
                "gesture": gesture_enum.value,
                "has_hand": len(norm_lms) == 21,
                "fps": self.tracker.fps,
                "latency": self.tracker.latency_ms,
            })

            # Modest sleep to prevent thread thrashing
            time.sleep(0.005)

    # ---- UI Update Loop ----
    def _update_camera_frame(self) -> None:
        """Drain processed frames from worker queue and update GUI."""
        if self.is_running and not self.frame_queue.empty():
            try:
                data = self.frame_queue.get_nowait()
                bgr_frame = data["frame"]
                gesture_name = data["gesture"]
                has_hand = data["has_hand"]
                fps = data["fps"]
                latency = data["latency"]

                # Convert BGR to RGB for CTkImage
                rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)

                # Resize to fit display label dynamically
                lbl_w = max(100, self.video_label.winfo_width())
                lbl_h = max(100, self.video_label.winfo_height())
                
                # Maintain aspect ratio (4:3 default)
                scale = min(lbl_w / 640.0, lbl_h / 480.0)
                disp_w = max(10, int(640 * scale))
                disp_h = max(10, int(480 * scale))

                pil_img = Image.fromarray(rgb_frame)
                ctk_img = ctk.CTkImage(pil_img, size=(disp_w, disp_h))
                self.video_label.configure(image=ctk_img)
                self.video_label.image = ctk_img

                # Update Telemetry Badges
                if has_hand:
                    self.hand_detected_badge.configure(text="● HAND TRACKED", text_color=FuturisticColors.ACCENT_GREEN)
                else:
                    self.hand_detected_badge.configure(text="● NO HAND DETECTED", text_color=FuturisticColors.ACCENT_RED)

                self.gesture_badge.configure(text=f"GESTURE: {gesture_name.upper()}")
                self.metrics_badge.configure(text=f"FPS: {fps:.1f}  |  {latency:.1f} ms")

            except Exception as e:
                pass

        # Schedule next frame update (~30-60 FPS)
        self.after(20, self._update_camera_frame)

    def on_closing(self) -> None:
        """Clean shutdown handler."""
        self.log_event("Shutting down AIRMOUSE AI...")
        self.is_running = False
        self.mouse_ctrl.release_all()
        self.tracker.stop_camera()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)
        self.destroy()


def launch_dashboard():
    """Application launcher."""
    settings = AppSettings()
    app = AirMouseDashboard(settings)
    app.mainloop()


if __name__ == "__main__":
    launch_dashboard()
