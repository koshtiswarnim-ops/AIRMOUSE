"""
ai_hand_mouse.py - Floating Desktop Gesture Mouse (Matches user photo)
Directly opens the clean floating 'AI Hand Mouse' camera window on the desktop.
Controls the system cursor across the entire operating system.
Press ESC or 'q' to exit.
"""

import os
import sys
import time
import cv2

from settings import AppSettings
from hand_tracker import HandTracker
from gesture_recognizer import GestureRecognizer, GestureType
from mouse_controller import MouseController


def run_floating_mouse():
    print("=" * 60)
    print("⚡ AI Hand Mouse — Direct Desktop Cursor Controller")
    print("Operating system cursor across all windows and desktop.")
    print("Press 'q' or ESC in the camera window to exit.")
    print("=" * 60)

    settings = AppSettings()
    settings.mouse_control_enabled = True  # Fully enabled on launch!

    tracker = HandTracker(camera_index=settings.camera_index, width=640, height=480)
    recognizer = GestureRecognizer()
    mouse_ctrl = MouseController(settings)

    if not tracker.start_camera():
        print("[-] ERROR: Could not open webcam.")
        return

    window_name = "AI Hand Mouse"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    # Set window to always on top if desired
    try:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass

    try:
        while True:
            success, raw_frame, norm_lms, px_lms = tracker.process_frame(mirror=True)
            if not success or raw_frame is None:
                time.sleep(0.01)
                continue

            # Classify Gesture
            gesture_enum, meta = recognizer.classify_gesture(
                norm_lms,
                pinch_threshold=settings.pinch_threshold,
                scroll_pinch_threshold=settings.scroll_pinch_threshold,
                drag_hold_duration=settings.drag_hold_duration,
                enable_drag=settings.enable_drag_and_drop,
            )

            # Move real system mouse
            mouse_ctrl.execute_actions(gesture_enum, meta)

            # Pinch indicator tether
            pinch_active = gesture_enum in (GestureType.PINCH_INDEX, GestureType.DRAGGING, GestureType.PINCH_MIDDLE)
            pinch_target = None
            if pinch_active and px_lms and len(px_lms) == 21:
                if gesture_enum == GestureType.PINCH_MIDDLE:
                    pinch_target = px_lms[HandTracker.MIDDLE_TIP]
                else:
                    pinch_target = px_lms[HandTracker.INDEX_TIP]

            # Draw futuristic HUD & large status badge (MOVE, CLICK, SCROLL, STOP)
            display_frame = tracker.draw_futuristic_hud(
                frame=raw_frame,
                pixel_landmarks=px_lms,
                active_gesture=gesture_enum.value,
                mouse_enabled=settings.mouse_control_enabled,
                is_paused=settings.is_paused,
                margin_x=settings.margin_x,
                margin_y=settings.margin_y,
                pinch_active=pinch_active,
                pinch_point=pinch_target,
            )

            cv2.imshow(window_name, display_frame)

            # Check for window close (X button) or key press
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                print("[*] Exit key pressed. Shutting down...")
                break

            # If window was closed with X
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                print("[*] Window closed by user. Shutting down...")
                break

    finally:
        mouse_ctrl.release_all()
        tracker.stop_camera()
        cv2.destroyAllWindows()
        print("[+] Mouse control released and camera closed successfully.")


if __name__ == "__main__":
    run_floating_mouse()
