"""
settings.py - Configuration and Settings for AIRMOUSE AI
Futuristic Gesture-Controlled Computer System
"""

import dataclasses
from typing import Dict, Any


@dataclasses.dataclass
class AppSettings:
    """Application configuration and gesture tuning parameters."""

    # Camera settings
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30

    # Safety and Global Controls
    mouse_control_enabled: bool = False  # Must start disabled for safety
    is_paused: bool = False
    emergency_stop: bool = False

    # Mouse Tracking & Smoothing
    # Active interaction box margins (normalized 0.0 to 0.5)
    margin_x: float = 0.15
    margin_y: float = 0.15
    sensitivity: float = 1.6  # Multiplier for cursor movement
    smoothing_factor: float = 0.55  # Exponential smoothing (0.1 = raw/fast, 0.9 = ultra-smooth)

    # Pinch & Click Thresholds
    pinch_threshold: float = 0.065  # Euclidean distance between normalized thumb & index tips
    scroll_pinch_threshold: float = 0.060  # Distance between thumb & middle finger tips
    click_cooldown: float = 0.25  # Seconds to wait between successive click triggers
    drag_hold_duration: float = 0.40  # Seconds pinch must be held to engage drag-and-drop

    # Scrolling
    scroll_speed: int = 35  # Scroll units multiplier
    scroll_deadzone: float = 0.015  # Minimum Y movement to trigger scroll

    # Feature Toggles
    enable_cursor_movement: bool = True
    enable_left_click: bool = True
    enable_drag_and_drop: bool = False  # Disabled by default, opt-in
    enable_scrolling: bool = True
    enable_palm_pause: bool = True
    enable_fist_stop: bool = True

    # Visual HUD options
    show_landmarks: bool = True
    show_hud: bool = True
    hud_cyber_mode: bool = True
    auto_float_camera: bool = True  # Automatically show floating camera window on desktop when outside website
    show_cursor_dot: bool = True  # Floating red/blue cursor dot halo over mouse pointer

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return dataclasses.asdict(self)

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update settings fields from dictionary."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
