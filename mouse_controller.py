"""
mouse_controller.py - Ultra-Smooth Virtual Mouse Controller for AIRMOUSE AI
Directly drives Windows system cursor with 1€ (One-Euro) adaptive filtering,
click position anchoring, rapid double-tap detection, and failsafe protections.
"""

import os
import time
import math
import logging
import ctypes
from typing import Tuple, Optional, Dict, Any

from settings import AppSettings
from gesture_recognizer import GestureType

logger = logging.getLogger("MouseController")

# Win32 Mouse Event Constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800


class OneEuroFilter:
    """Adaptive 1-Euro filter: Zero-jitter when still, zero-lag when moving fast."""

    def __init__(self, min_cutoff: float = 0.8, beta: float = 0.015, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev: Optional[float] = None
        self.dx_prev: float = 0.0
        self.t_prev: Optional[float] = None

    @staticmethod
    def _alpha(rate: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te = 1.0 / rate if rate > 0 else 0.033
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float, t: Optional[float] = None) -> float:
        t = t or time.perf_counter()
        if self.t_prev is None:
            self.x_prev = x
            self.t_prev = t
            return x

        dt = max(1e-4, t - self.t_prev)
        rate = 1.0 / dt
        self.t_prev = t

        # Filter derivative (speed)
        dx = (x - (self.x_prev or x)) / dt
        alpha_d = self._alpha(rate, self.d_cutoff)
        dx_hat = alpha_d * dx + (1.0 - alpha_d) * self.dx_prev
        self.dx_prev = dx_hat

        # Adaptive cutoff based on movement velocity
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        alpha = self._alpha(rate, cutoff)

        x_hat = alpha * x + (1.0 - alpha) * (self.x_prev if self.x_prev is not None else x)
        self.x_prev = x_hat
        return x_hat

    def reset(self):
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None


class MouseController:
    """Controls Windows system cursor with 1€ filtering, click anchoring, and double-tap detection."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.is_windows = (os.name == "nt")
        self.user32 = ctypes.windll.user32 if self.is_windows else None

        self._attach_to_default_desktop()
        self.screen_w, self.screen_h = self._get_screen_size()

        # 1-Euro adaptive filters for X and Y axes
        self.filter_x = OneEuroFilter(min_cutoff=0.8, beta=0.02)
        self.filter_y = OneEuroFilter(min_cutoff=0.8, beta=0.02)

        # Cursor position state
        self.prev_screen_x = float(self.screen_w // 2)
        self.prev_screen_y = float(self.screen_h // 2)
        self.has_previous_position = False

        # Click anchoring & Double-tap detection
        self.is_left_down = False
        self.last_tap_time = 0.0
        self.last_tap_pos: Optional[Tuple[int, int]] = None
        self.tap_lock_pos: Optional[Tuple[int, int]] = None
        self.tap_lock_expiry: float = 0.0
        self.anchor_pos: Optional[Tuple[int, int]] = None  # Freezes cursor while pinching
        self.double_tap_window = 0.55  # Max seconds between 2 taps to register double-click

        self.failsafe_triggered = False

        # Real-time Cursor Dot Halo Overlay (Red on move, Blue on click)
        self.cursor_overlay = None
        if self.is_windows:
            try:
                from cursor_overlay import get_cursor_overlay
                self.cursor_overlay = get_cursor_overlay()
            except Exception as e:
                logger.warning(f"Cursor overlay not initialized: {e}")

    def _attach_to_default_desktop(self) -> None:
        """Attach current thread to interactive user desktop (WinSta0\\Default)."""
        if self.is_windows and self.user32:
            try:
                h_desk = self.user32.OpenDesktopW("Default", 0, False, 0x01FF)
                if h_desk:
                    self.user32.SetThreadDesktop(h_desk)
            except Exception:
                pass

    def _get_screen_size(self) -> Tuple[int, int]:
        """Fetch system screen dimensions."""
        if self.is_windows and self.user32:
            try:
                w = self.user32.GetSystemMetrics(0)
                h = self.user32.GetSystemMetrics(1)
                if w > 0 and h > 0:
                    return w, h
            except Exception:
                pass
        return 1920, 1080

    def release_all(self) -> None:
        """Release any held mouse buttons and reset state."""
        if self.is_left_down:
            if self.is_windows and self.user32:
                try:
                    self._attach_to_default_desktop()
                    self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                except Exception:
                    pass
            self.is_left_down = False
            self.anchor_pos = None

        if self.cursor_overlay:
            try:
                self.cursor_overlay.set_clicking(False)
                self.cursor_overlay.hide()
            except Exception:
                pass

    def map_coordinates(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """Map normalized hand coordinates to desktop resolution with 1€ adaptive smoothing."""
        mx = max(0.06, min(0.28, self.settings.margin_x))
        my = max(0.06, min(0.28, self.settings.margin_y))

        box_w = max(0.1, 1.0 - 2.0 * mx)
        box_h = max(0.1, 1.0 - 2.0 * my)

        clamped_nx = max(0.0, min(1.0, (norm_x - mx) / box_w))
        clamped_ny = max(0.0, min(1.0, (norm_y - my) / box_h))

        # Sensitivity curve
        sens = max(0.5, min(4.0, self.settings.sensitivity))
        centered_x = (clamped_nx - 0.5) * sens + 0.5
        centered_y = (clamped_ny - 0.5) * sens + 0.5

        final_nx = max(0.0, min(1.0, centered_x))
        final_ny = max(0.0, min(1.0, centered_y))

        raw_x = final_nx * (self.screen_w - 1)
        raw_y = final_ny * (self.screen_h - 1)

        # Dynamically adjust 1-Euro filter based on user smoothing factor
        smooth = max(0.1, min(0.95, self.settings.smoothing_factor))
        self.filter_x.min_cutoff = 0.25 + (1.0 - smooth) * 0.65
        self.filter_y.min_cutoff = 0.25 + (1.0 - smooth) * 0.65
        self.filter_x.beta = 0.01 + (1.0 - smooth) * 0.04
        self.filter_y.beta = 0.01 + (1.0 - smooth) * 0.04

        # 1-Euro Adaptive Filter: smooths hovering micro-tremors, snaps instantly on fast motion
        now_t = time.perf_counter()
        smooth_x = self.filter_x.filter(raw_x, now_t)
        smooth_y = self.filter_y.filter(raw_y, now_t)

        self.prev_screen_x = smooth_x
        self.prev_screen_y = smooth_y
        self.has_previous_position = True

        target_x = int(max(4, min(self.screen_w - 5, round(smooth_x))))
        target_y = int(max(4, min(self.screen_h - 5, round(smooth_y))))
        return target_x, target_y

    def execute_actions(
        self,
        gesture: GestureType,
        meta: Dict[str, Any],
        on_event_cb=None,
    ) -> None:
        """Process gestures with click anchoring, double-tap recognition, and OS mouse actuation."""
        now = time.time()

        if not self.settings.mouse_control_enabled or self.settings.is_paused or self.settings.emergency_stop:
            self.release_all()
            self.filter_x.reset()
            self.filter_y.reset()
            self.has_previous_position = False
            return

        self._attach_to_default_desktop()

        try:
            # 1. Idle Gestures: Freeze cursor & release buttons
            if gesture in (GestureType.NO_HAND, GestureType.FIST):
                self.release_all()
                self.has_previous_position = False
                return

            # Check for drag release
            if meta.get("release_drag", False):
                if self.is_left_down:
                    if self.is_windows and self.user32:
                        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    self.is_left_down = False
                    self.anchor_pos = None
                    if self.cursor_overlay:
                        self.cursor_overlay.set_clicking(False)
                    if on_event_cb:
                        on_event_cb("Drag & Drop: Released")

            # 2. System Cursor Movement
            index_pt = meta.get("index_point")
            is_pinching = (gesture in (GestureType.PINCH_INDEX, GestureType.DRAGGING))

            if meta.get("can_move", False) and self.settings.enable_cursor_movement and index_pt:
                # Map hand to desktop coordinates
                target_x, target_y = self.map_coordinates(index_pt["x"], index_pt["y"])

                # Tap-Lock: If user tapped recently (within 0.45s), pin cursor to the target so hand release drift doesn't slide off option
                if (now < self.tap_lock_expiry) and (self.tap_lock_pos is not None):
                    drift_dist = math.hypot(target_x - self.tap_lock_pos[0], target_y - self.tap_lock_pos[1])
                    if drift_dist < 120:  # Hand shifted within 120px while tapping: keep cursor pinned on option!
                        target_x, target_y = self.tap_lock_pos
                    else:
                        # User moved hand far away intentionally: release lock
                        self.tap_lock_expiry = 0.0
                        self.tap_lock_pos = None

                # Pinch-Lock: While pinching, freeze at starting position so finger pressure doesn't shift cursor
                if is_pinching and self.anchor_pos and not self.settings.enable_drag_and_drop:
                    screen_x, screen_y = self.anchor_pos
                else:
                    screen_x, screen_y = target_x, target_y
                    if not is_pinching:
                        self.anchor_pos = (screen_x, screen_y)

                if self.is_windows and self.user32:
                    self.user32.SetCursorPos(screen_x, screen_y)
                    # Update real-time Red/Blue cursor halo
                    if self.cursor_overlay and getattr(self.settings, "show_cursor_dot", True):
                        self.cursor_overlay.update_position(screen_x, screen_y, visible=True)

            # 3. Left-Click and Double-Tap Detection
            if self.settings.enable_left_click and meta.get("trigger_click", False):
                time_since_last_tap = now - self.last_tap_time

                # Determine system double-click threshold (typically 500ms)
                dbl_time_limit = 0.55
                if self.is_windows and self.user32:
                    try:
                        sys_dbl = self.user32.GetDoubleClickTime() / 1000.0
                        if 0.35 <= sys_dbl <= 0.8:
                            dbl_time_limit = sys_dbl + 0.05
                    except Exception:
                        pass

                # Double-tap confirmed if within double-tap window and we have previous tap pos
                if (0.04 <= time_since_last_tap <= dbl_time_limit) and (self.last_tap_pos is not None):
                    # Double-tap confirmed! Snap cursor to the EXACT same pixel as Tap 1
                    screen_x, screen_y = self.last_tap_pos
                    if self.is_windows and self.user32:
                        self.user32.SetCursorPos(screen_x, screen_y)
                        time.sleep(0.015)
                        # Execute clean second click with solid 35ms hold time so all Windows UI controls detect it
                        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        time.sleep(0.035)
                        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

                    # Turn cursor halo BLUE for double tap
                    if self.cursor_overlay and getattr(self.settings, "show_cursor_dot", True):
                        self.cursor_overlay.update_position(screen_x, screen_y, visible=True)
                        self.cursor_overlay.flash_click(0.40)

                    # Reset double-tap state
                    self.last_tap_time = 0.0
                    self.last_tap_pos = None
                    self.tap_lock_expiry = 0.0
                    self.tap_lock_pos = None

                    if on_event_cb:
                        try:
                            on_event_cb("DOUBLE-TAP EXECUTED: Option Selected & Applied!")
                        except Exception:
                            pass
                else:
                    # Single click (Tap 1)
                    if self.anchor_pos:
                        screen_x, screen_y = self.anchor_pos
                    elif self.has_previous_position:
                        screen_x, screen_y = int(self.prev_screen_x), int(self.prev_screen_y)
                    else:
                        screen_x, screen_y = self.screen_w // 2, self.screen_h // 2

                    self.last_tap_time = now
                    self.last_tap_pos = (screen_x, screen_y)
                    self.tap_lock_pos = (screen_x, screen_y)
                    self.tap_lock_expiry = now + 0.45  # Lock cursor to option for next 450ms!

                    if self.is_windows and self.user32:
                        self.user32.SetCursorPos(screen_x, screen_y)
                        time.sleep(0.015)
                        # Execute clean click with solid 35ms hold time
                        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        time.sleep(0.035)
                        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

                    # Turn cursor halo BLUE for single click
                    if self.cursor_overlay and getattr(self.settings, "show_cursor_dot", True):
                        self.cursor_overlay.update_position(screen_x, screen_y, visible=True)
                        self.cursor_overlay.flash_click(0.32)

                    if on_event_cb:
                        try:
                            on_event_cb("Single Click Executed (Option Clicked)")
                        except Exception:
                            pass

            # 4. Drag & Drop
            if self.settings.enable_drag_and_drop and gesture == GestureType.DRAGGING:
                if not self.is_left_down:
                    if self.is_windows and self.user32:
                        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    self.is_left_down = True
                    if self.cursor_overlay:
                        self.cursor_overlay.set_clicking(True)
                    if on_event_cb:
                        on_event_cb("Drag & Drop: Holding Left Button")

            # 5. Vertical Scrolling (Middle Pinch)
            if self.settings.enable_scrolling and gesture == GestureType.PINCH_MIDDLE:
                scroll_delta = meta.get("scroll_delta", 0.0)
                if abs(scroll_delta) > self.settings.scroll_deadzone:
                    ticks = int(scroll_delta * self.settings.scroll_speed * 120)
                    if ticks != 0 and self.is_windows and self.user32:
                        self.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, ticks, 0)
                        if on_event_cb:
                            action = "UP" if ticks > 0 else "DOWN"
                            on_event_cb(f"Scroll {action} ({abs(ticks)})")

        except Exception as e:
            logger.error(f"Error executing mouse action: {e}")
            self.release_all()
