"""
cursor_overlay.py - Real-Time Click-Through Cursor Dot Visualizer for AIRMOUSE AI
Displays an interactive glowing halo directly over the system cursor pointer:
- RED halo when moving the cursor with hand gestures
- BLUE halo when clicking, double-tapping, or dragging
- Fully click-through (WS_EX_TRANSPARENT) so it never blocks desktop clicks
- Never steals focus (WS_EX_NOACTIVATE) and stays always on top (WS_EX_TOPMOST)
"""

import os
import sys
import time
import threading
import logging
from typing import Optional

logger = logging.getLogger("CursorOverlay")

IS_WINDOWS = (os.name == "nt")

# Win32 Constants
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
ULW_ALPHA = 0x00000002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01


class DummyCursorOverlay:
    """Fallback no-op overlay for non-Windows platforms (e.g. Vercel / Linux)."""
    def update_position(self, x: int, y: int, visible: bool = True): pass
    def flash_click(self, duration: float = 0.3): pass
    def set_clicking(self, clicking: bool = True): pass
    def hide(self): pass
    def stop(self): pass


class Win32CursorDotOverlay:
    """Ultra-responsive, per-pixel alpha cursor halo using pure Win32 GDI & Layered Windows."""

    def __init__(self, size: int = 42):
        self.size = size
        self.half = size // 2
        self.x = 0
        self.y = 0
        self.visible = False
        self.is_clicking = False
        self.click_expiry = 0.0
        self.running = True
        self.ready_event = threading.Event()
        self.lock = threading.Lock()

        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.wintypes = wintypes
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32

        # Start background window manager thread
        self.thread = threading.Thread(target=self._worker, daemon=True, name="AirmouseCursorDot")
        self.thread.start()
        self.ready_event.wait(timeout=2.0)

    def _create_dib(self, hdc_screen, fill_rgba, border_rgba):
        from PIL import Image, ImageDraw
        import numpy as np

        img = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Smooth circular halo (anti-aliased)
        draw.ellipse(
            [3, 3, self.size - 4, self.size - 4],
            fill=fill_rgba,
            outline=border_rgba,
            width=2,
        )

        arr = np.array(img, dtype=np.uint16)
        alpha = arr[:, :, 3] / 255.0
        arr[:, :, 0] = (arr[:, :, 0] * alpha).astype(np.uint8)
        arr[:, :, 1] = (arr[:, :, 1] * alpha).astype(np.uint8)
        arr[:, :, 2] = (arr[:, :, 2] * alpha).astype(np.uint8)

        # Format as pre-multiplied BGRA for Windows UpdateLayeredWindow
        bgra = np.zeros_like(arr, dtype=np.uint8)
        bgra[:, :, 0] = arr[:, :, 2]  # B
        bgra[:, :, 1] = arr[:, :, 1]  # G
        bgra[:, :, 2] = arr[:, :, 0]  # R
        bgra[:, :, 3] = arr[:, :, 3]  # A
        bgra = np.flipud(bgra)  # Windows DIB bottom-up
        raw_bytes = bgra.tobytes()

        class BITMAPINFOHEADER(self.ctypes.Structure):
            _fields_ = [
                ("biSize", self.wintypes.DWORD),
                ("biWidth", self.wintypes.LONG),
                ("biHeight", self.wintypes.LONG),
                ("biPlanes", self.wintypes.WORD),
                ("biBitCount", self.wintypes.WORD),
                ("biCompression", self.wintypes.DWORD),
                ("biSizeImage", self.wintypes.DWORD),
                ("biXPelsPerMeter", self.wintypes.LONG),
                ("biYPelsPerMeter", self.wintypes.LONG),
                ("biClrUsed", self.wintypes.DWORD),
                ("biClrImportant", self.wintypes.DWORD),
            ]

        class BITMAPINFO(self.ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", self.wintypes.DWORD * 3)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = self.ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.size
        bmi.bmiHeader.biHeight = self.size
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        ppvBits = self.ctypes.c_void_p()
        hbmp = self.gdi32.CreateDIBSection(hdc_screen, self.ctypes.byref(bmi), 0, self.ctypes.byref(ppvBits), 0, 0)
        self.ctypes.memmove(ppvBits, raw_bytes, len(raw_bytes))
        return hbmp

    def _worker(self):
        """Worker thread hosting the transparent layered Win32 window."""
        try:
            # Attach to user's interactive desktop WinSta0\Default
            h_desk = self.user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_desk:
                self.user32.SetThreadDesktop(h_desk)
        except Exception:
            pass

        class POINT(self.ctypes.Structure):
            _fields_ = [("x", self.ctypes.c_long), ("y", self.ctypes.c_long)]

        class SIZE(self.ctypes.Structure):
            _fields_ = [("cx", self.ctypes.c_long), ("cy", self.ctypes.c_long)]

        class BLENDFUNCTION(self.ctypes.Structure):
            _fields_ = [
                ("BlendOp", self.ctypes.c_byte),
                ("BlendFlags", self.ctypes.c_byte),
                ("SourceConstantAlpha", self.ctypes.c_byte),
                ("AlphaFormat", self.ctypes.c_byte),
            ]

        # Create borderless, click-through, topmost layered window
        hwnd = self.user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            "STATIC",
            "AIRMOUSE_CURSOR_DOT",
            WS_POPUP,
            -200, -200, self.size, self.size,
            0, 0, 0, 0
        )

        hdc_screen = self.user32.GetDC(0)
        hdc_mem = self.gdi32.CreateCompatibleDC(hdc_screen)

        # 1. Vibrant Red Halo for Cursor Movement
        hbmp_red = self._create_dib(
            hdc_screen,
            fill_rgba=(240, 25, 25, 205),
            border_rgba=(255, 255, 255, 235),
        )

        # 2. Electric Blue Halo for Click & Drag
        hbmp_blue = self._create_dib(
            hdc_screen,
            fill_rgba=(25, 125, 255, 220),
            border_rgba=(255, 255, 255, 245),
        )

        self.gdi32.SelectObject(hdc_mem, hbmp_red)

        pt_dst = POINT(-200, -200)
        sz = SIZE(self.size, self.size)
        pt_src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)

        self.user32.UpdateLayeredWindow(
            hwnd, hdc_screen, self.ctypes.byref(pt_dst), self.ctypes.byref(sz),
            hdc_mem, self.ctypes.byref(pt_src), 0, self.ctypes.byref(blend), ULW_ALPHA
        )

        self.ready_event.set()
        last_drawn_blue = False
        last_shown = False
        last_x, last_y = -999, -999

        msg = self.wintypes.MSG()

        while self.running:
            # Process any incoming Win32 messages
            while self.user32.PeekMessageW(self.ctypes.byref(msg), 0, 0, 0, 1):
                self.user32.TranslateMessage(self.ctypes.byref(msg))
                self.user32.DispatchMessageW(self.ctypes.byref(msg))

            now = time.time()
            with self.lock:
                active_blue = self.is_clicking or (now < self.click_expiry)
                cur_x, cur_y = self.x, self.y
                is_vis = self.visible

            # Switch between Red and Blue bitmap when state changes
            if active_blue != last_drawn_blue:
                bmp = hbmp_blue if active_blue else hbmp_red
                self.gdi32.SelectObject(hdc_mem, bmp)
                self.user32.UpdateLayeredWindow(
                    hwnd, hdc_screen, None, None,
                    hdc_mem, self.ctypes.byref(pt_src), 0, self.ctypes.byref(blend), ULW_ALPHA
                )
                last_drawn_blue = active_blue

            # Visibility and screen positioning
            if is_vis:
                if not last_shown:
                    self.user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
                    last_shown = True

                if (cur_x != last_x) or (cur_y != last_y):
                    self.user32.SetWindowPos(
                        hwnd, -1, cur_x - self.half, cur_y - self.half, 0, 0,
                        SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOZORDER | SWP_SHOWWINDOW
                    )
                    last_x, last_y = cur_x, cur_y
            else:
                if last_shown:
                    self.user32.ShowWindow(hwnd, SW_HIDE)
                    last_shown = False

            time.sleep(0.007)  # ~140 FPS ultra-low latency loop

        # Cleanup
        try:
            self.user32.ShowWindow(hwnd, SW_HIDE)
            self.gdi32.DeleteObject(hbmp_red)
            self.gdi32.DeleteObject(hbmp_blue)
            self.gdi32.DeleteDC(hdc_mem)
            self.user32.ReleaseDC(0, hdc_screen)
            self.user32.DestroyWindow(hwnd)
        except Exception:
            pass

    def update_position(self, x: int, y: int, visible: bool = True):
        """Update cursor position and ensure visibility."""
        with self.lock:
            self.x = int(x)
            self.y = int(y)
            self.visible = visible

    def flash_click(self, duration: float = 0.32):
        """Turn halo BLUE for duration (used for single clicks and double taps)."""
        with self.lock:
            self.click_expiry = max(self.click_expiry, time.time() + duration)

    def set_clicking(self, clicking: bool = True):
        """Set continuous blue state (used during drag and drop or mouse-down)."""
        with self.lock:
            self.is_clicking = clicking

    def hide(self):
        """Hide the cursor halo when idle or control is disabled."""
        with self.lock:
            self.visible = False

    def stop(self):
        """Stop worker and destroy window."""
        self.running = False


_GLOBAL_OVERLAY: Optional[Win32CursorDotOverlay] = None
_INIT_LOCK = threading.Lock()


def get_cursor_overlay() -> Win32CursorDotOverlay:
    """Return shared singleton CursorDotOverlay instance."""
    global _GLOBAL_OVERLAY
    if not IS_WINDOWS:
        return DummyCursorOverlay()

    if _GLOBAL_OVERLAY is None:
        with _INIT_LOCK:
            if _GLOBAL_OVERLAY is None:
                try:
                    _GLOBAL_OVERLAY = Win32CursorDotOverlay(size=42)
                except Exception as e:
                    logger.warning(f"Could not initialize Win32CursorDotOverlay: {e}")
                    _GLOBAL_OVERLAY = DummyCursorOverlay()
    return _GLOBAL_OVERLAY
