"""
floating_hud.py - Always-On-Top Floating Webcam Screen for AIRMOUSE AI
Floats on top of all Windows desktop applications and keeps the camera feed visible
when you switch out of the browser, minimize, or operate desktop apps.
"""

import sys
import os
import time
import ctypes
import json
import urllib.request
import cv2
import numpy as np

STREAM_URL = "http://127.0.0.1:5000/video_feed"
STATUS_URL = "http://127.0.0.1:5000/api/status"
WINDOW_NAME = "⚡ AIRMOUSE AI — Live Camera (Always On Top)"

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


def attach_to_desktop():
    """Ensure process is on the user's interactive desktop."""
    if os.name == "nt":
        try:
            user32 = ctypes.windll.user32
            h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_desk:
                user32.SetThreadDesktop(h_desk)
        except Exception:
            pass


def ensure_single_instance() -> bool:
    """Ensure only one floating HUD runs at a time."""
    if os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32
            mutex = kernel32.CreateMutexW(None, False, "Global\\AIRMOUSE_AI_FLOATING_HUD_MUTEX")
            last_err = kernel32.GetLastError()
            ERROR_ALREADY_EXISTS = 183
            if last_err == ERROR_ALREADY_EXISTS:
                # Bring existing window to front
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, WINDOW_NAME)
                if hwnd:
                    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                return False
        except Exception:
            pass
    return True


def apply_topmost(hwnd, pos_x: int, pos_y: int, width: int, height: int):
    """Pin window on top without stealing keyboard or mouse focus."""
    if os.name == "nt" and hwnd:
        try:
            user32 = ctypes.windll.user32
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                pos_x,
                pos_y,
                width,
                height,
                SWP_SHOWWINDOW | SWP_NOACTIVATE,
            )
        except Exception:
            pass


def main():
    if not ensure_single_instance():
        print("[*] Floating HUD is already running on the desktop.")
        return

    attach_to_desktop()

    print(f"Connecting to live video stream at {STREAM_URL}...")
    cap = cv2.VideoCapture(STREAM_URL)

    # Retry connection if server is still starting
    retries = 0
    while not cap.isOpened() and retries < 20:
        time.sleep(0.4)
        cap = cv2.VideoCapture(STREAM_URL)
        retries += 1

    if not cap.isOpened():
        print("[-] Could not connect to AIRMOUSE live stream.")
        return

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    win_w, win_h = 360, 270
    cv2.resizeWindow(WINDOW_NAME, win_w, win_h)

    # Position in bottom-right corner of desktop (above taskbar)
    pos_x, pos_y = 100, 100
    if os.name == "nt":
        try:
            user32 = ctypes.windll.user32
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            pos_x = max(0, screen_w - win_w - 24)
            pos_y = max(0, screen_h - win_h - 70)
            cv2.moveWindow(WINDOW_NAME, pos_x, pos_y)
        except Exception:
            pass

    # Ensure topmost
    try:
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass

    hwnd = None
    if os.name == "nt":
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, WINDOW_NAME)
            if hwnd:
                apply_topmost(hwnd, pos_x, pos_y, win_w, win_h)
        except Exception:
            pass

    last_topmost_check = time.time()
    last_status_check = time.time()
    server_offline_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.02)
                continue

            cv2.imshow(WINDOW_NAME, frame)

            now = time.time()

            # Refresh topmost every 2 seconds in case other apps try to cover it
            if now - last_topmost_check > 2.0:
                last_topmost_check = now
                if os.name == "nt" and hwnd:
                    apply_topmost(hwnd, pos_x, pos_y, win_w, win_h)

            # Check server heartbeat every 3 seconds: if server shuts down, exit cleanly
            if now - last_status_check > 3.0:
                last_status_check = now
                try:
                    req = urllib.request.Request(STATUS_URL, headers={"User-Agent": "AIRMOUSE-FloatingHUD"})
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        if resp.status == 200:
                            server_offline_count = 0
                            # If server explicitly paused or stopped mouse and user closed browser
                            data = json.loads(resp.read().decode("utf-8"))
                            if data.get("emergency_stop", False):
                                break
                        else:
                            server_offline_count += 1
                except Exception:
                    server_offline_count += 1

                # If server is unreachable for 3 checks (9 seconds), exit cleanly
                if server_offline_count >= 3:
                    print("[*] AIRMOUSE server disconnected. Closing floating HUD.")
                    break

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break

            # Resize shortcuts (+ / -)
            if key in (ord("+"), ord("=")):
                win_w = min(720, int(win_w * 1.15))
                win_h = min(540, int(win_h * 1.15))
                cv2.resizeWindow(WINDOW_NAME, win_w, win_h)
            elif key in (ord("-"), ord("_")):
                win_w = max(240, int(win_w * 0.85))
                win_h = max(180, int(win_h * 0.85))
                cv2.resizeWindow(WINDOW_NAME, win_w, win_h)

            # Check if user clicked window close 'X'
            try:
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except Exception:
                pass

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
