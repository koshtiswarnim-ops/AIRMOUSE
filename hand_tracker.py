"""
hand_tracker.py - Real-Time Hand Landmark Detection and Futuristic HUD Visualizer
Supports both modern MediaPipe Tasks HandLandmarker (1.x+) and classic mp.solutions.hands.
"""

import os
import time
import urllib.request
import logging
from typing import List, Tuple, Optional, Dict, Any

import cv2
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HandTracker")

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
MODEL_FILENAME = "hand_landmarker.task"


class HandTracker:
    """Detects and tracks 21 hand landmarks from webcam frames with futuristic visualization."""

    # Landmark indices for easy reference
    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20

    # Hand skeleton bone connections
    BONES = [
        # Palm base
        (WRIST, THUMB_CMC),
        (WRIST, INDEX_MCP),
        (WRIST, PINKY_MCP),
        (INDEX_MCP, MIDDLE_MCP),
        (MIDDLE_MCP, RING_MCP),
        (RING_MCP, PINKY_MCP),
        # Thumb
        (THUMB_CMC, THUMB_MCP),
        (THUMB_MCP, THUMB_IP),
        (THUMB_IP, THUMB_TIP),
        # Index
        (INDEX_MCP, INDEX_PIP),
        (INDEX_PIP, INDEX_DIP),
        (INDEX_DIP, INDEX_TIP),
        # Middle
        (MIDDLE_MCP, MIDDLE_PIP),
        (MIDDLE_PIP, MIDDLE_DIP),
        (MIDDLE_DIP, MIDDLE_TIP),
        # Ring
        (RING_MCP, RING_PIP),
        (RING_PIP, RING_DIP),
        (RING_DIP, RING_TIP),
        # Pinky
        (PINKY_MCP, PINKY_PIP),
        (PINKY_PIP, PINKY_DIP),
        (PINKY_DIP, PINKY_TIP),
    ]

    def __init__(self, camera_index: int = 0, width: int = 640, height: int = 480):
        self.camera_index = camera_index
        self.width = width
        self.height = height

        self.cap: Optional[cv2.VideoCapture] = None
        self.is_camera_running = False

        # Performance monitoring
        self.fps = 0.0
        self.latency_ms = 0.0
        self._frame_count = 0
        self._start_time = time.time()
        self._last_frame_time = time.time()

        # Backend detection model
        self.use_tasks_api = False
        self.detector = None
        self._mp_module = None
        self._init_mediapipe_backend()

    def _ensure_task_model(self) -> str:
        """Download hand_landmarker.task if not present locally."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, MODEL_FILENAME)
        if not os.path.exists(model_path) or os.path.getsize(model_path) < 1000000:
            logger.info("Downloading MediaPipe hand_landmarker model bundle...")
            try:
                urllib.request.urlretrieve(MODEL_URL, model_path)
                logger.info(f"Model saved to {model_path} ({os.path.getsize(model_path)} bytes)")
            except Exception as e:
                logger.error(f"Failed to download MediaPipe model: {e}")
                raise
        return model_path

    def _init_mediapipe_backend(self) -> None:
        """Initialize MediaPipe using either the modern tasks API or legacy solutions API."""
        import mediapipe as mp
        self._mp_module = mp

        # Check for legacy solutions API first
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "hands"):
            logger.info("Initializing MediaPipe Hands using legacy solutions API.")
            self.detector = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.6,
            )
            self.use_tasks_api = False
        else:
            # Modern tasks API (MediaPipe 1.x+)
            logger.info("Initializing MediaPipe HandLandmarker using modern Tasks API.")
            model_path = self._ensure_task_model()
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            base_options = mp_python.BaseOptions(model_asset_path=model_path)
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_hands=1,
                min_hand_detection_confidence=0.55,
                min_hand_presence_confidence=0.55,
                min_tracking_confidence=0.55,
            )
            self.detector = vision.HandLandmarker.create_from_options(options)
            self.use_tasks_api = True

    def start_camera(self) -> bool:
        """Open the webcam with configured resolution."""
        if self.cap is not None and self.cap.isOpened():
            self.is_camera_running = True
            return True

        logger.info(f"Opening camera index {self.camera_index}...")
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
        if not self.cap.isOpened():
            # Fallback to default backend
            self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            logger.error(f"Failed to open webcam index {self.camera_index}")
            self.is_camera_running = False
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self.is_camera_running = True
        self._last_frame_time = time.time()
        self._frame_count = 0
        self._start_time = time.time()
        logger.info("Webcam started successfully.")
        return True

    def stop_camera(self) -> None:
        """Release the webcam capture."""
        self.is_camera_running = False
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception as e:
                logger.warning(f"Error releasing camera: {e}")
            self.cap = None
        logger.info("Webcam stopped and resources released.")

    def process_frame(
        self,
        frame_input: Optional[np.ndarray] = None,
        mirror: bool = True,
    ) -> Tuple[bool, Optional[np.ndarray], List[Dict[str, float]], List[Tuple[int, int]]]:
        """
        Capture and process a single frame.
        
        Returns:
            (success, processed_bgr_frame, normalized_landmarks, pixel_landmarks)
            where normalized_landmarks is a list of 21 dicts {'x': float, 'y': float, 'z': float}
            and pixel_landmarks is a list of 21 (x_px, y_px) tuples.
        """
        t_start = time.perf_counter()

        if frame_input is None:
            if not self.is_camera_running or self.cap is None or not self.cap.isOpened():
                return False, None, [], []
            ret, frame = self.cap.read()
            if not ret or frame is None:
                return False, None, [], []
        else:
            frame = frame_input

        # Flip horizontally for natural mirror behavior
        if mirror:
            frame = cv2.flip(frame, 1)

        h, w = frame.shape[:2]
        self.width, self.height = w, h

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        normalized_landmarks: List[Dict[str, float]] = []
        pixel_landmarks: List[Tuple[int, int]] = []

        try:
            if self.use_tasks_api:
                # Modern Tasks API
                mp_img = self._mp_module.Image(
                    image_format=self._mp_module.ImageFormat.SRGB,
                    data=rgb_frame,
                )
                result = self.detector.detect(mp_img)
                if result.hand_landmarks and len(result.hand_landmarks) > 0:
                    first_hand = result.hand_landmarks[0]
                    for lm in first_hand:
                        normalized_landmarks.append({"x": float(lm.x), "y": float(lm.y), "z": float(lm.z)})
                        pixel_landmarks.append((int(lm.x * w), int(lm.y * h)))
            else:
                # Legacy mp.solutions API
                results = self.detector.process(rgb_frame)
                if results.multi_hand_landmarks and len(results.multi_hand_landmarks) > 0:
                    first_hand = results.multi_hand_landmarks[0]
                    for lm in first_hand.landmark:
                        normalized_landmarks.append({"x": float(lm.x), "y": float(lm.y), "z": float(lm.z)})
                        pixel_landmarks.append((int(lm.x * w), int(lm.y * h)))
        except Exception as e:
            logger.error(f"Error in hand detection inference: {e}")

        # Update FPS and latency
        t_end = time.perf_counter()
        self.latency_ms = (t_end - t_start) * 1000.0

        now = time.time()
        self._frame_count += 1
        elapsed = now - self._start_time
        if elapsed >= 0.5:
            self.fps = round(self._frame_count / elapsed, 1)
            self._frame_count = 0
            self._start_time = now

        return True, frame, normalized_landmarks, pixel_landmarks

    def draw_futuristic_hud(
        self,
        frame: np.ndarray,
        pixel_landmarks: List[Tuple[int, int]],
        active_gesture: str = "SEARCHING...",
        mouse_enabled: bool = False,
        is_paused: bool = False,
        margin_x: float = 0.15,
        margin_y: float = 0.15,
        pinch_active: bool = False,
        pinch_point: Optional[Tuple[int, int]] = None,
    ) -> np.ndarray:
        """Render a clean, futuristic cyber overlay on the webcam frame."""
        h, w = frame.shape[:2]
        hud_frame = frame.copy()

        # Color palette (BGR format for OpenCV)
        CYAN_PRIMARY = (255, 240, 0)     # #00f0ff
        CYAN_GLOW = (245, 180, 20)      # Soft cyan
        ELECTRIC_BLUE = (255, 120, 0)   # #0078ff
        EMERALD_GREEN = (80, 240, 80)   # #50f050
        ALERT_AMBER = (40, 180, 255)    # #ffb428
        ALERT_RED = (60, 60, 240)       # #f03c3c
        DARK_HUD_BG = (15, 20, 25)

        # 1. Active Screen Boundary Corner Brackets
        x_min = int(margin_x * w)
        x_max = int((1.0 - margin_x) * w)
        y_min = int(margin_y * h)
        y_max = int((1.0 - margin_y) * h)

        bracket_len = 24
        bracket_color = CYAN_PRIMARY if mouse_enabled else (120, 140, 150)
        thick = 2

        # Top-left corner
        cv2.line(hud_frame, (x_min, y_min), (x_min + bracket_len, y_min), bracket_color, thick)
        cv2.line(hud_frame, (x_min, y_min), (x_min, y_min + bracket_len), bracket_color, thick)
        # Top-right corner
        cv2.line(hud_frame, (x_max, y_min), (x_max - bracket_len, y_min), bracket_color, thick)
        cv2.line(hud_frame, (x_max, y_min), (x_max, y_min + bracket_len), bracket_color, thick)
        # Bottom-left corner
        cv2.line(hud_frame, (x_min, y_max), (x_min + bracket_len, y_max), bracket_color, thick)
        cv2.line(hud_frame, (x_min, y_max), (x_min, y_max - bracket_len), bracket_color, thick)
        # Bottom-right corner
        cv2.line(hud_frame, (x_max, y_max), (x_max - bracket_len, y_max), bracket_color, thick)
        cv2.line(hud_frame, (x_max, y_max), (x_max, y_max - bracket_len), bracket_color, thick)

        # Subtle crosshairs in center of active zone
        cx, cy = (x_min + x_max) // 2, (y_min + y_max) // 2
        cv2.line(hud_frame, (cx - 8, cy), (cx + 8, cy), (80, 100, 110), 1)
        cv2.line(hud_frame, (cx, cy - 8), (cx, cy + 8), (80, 100, 110), 1)

        # 2. Draw Hand Landmarks Skeleton
        if pixel_landmarks and len(pixel_landmarks) == 21:
            # Draw bones (connections)
            for p1_idx, p2_idx in self.BONES:
                pt1 = pixel_landmarks[p1_idx]
                pt2 = pixel_landmarks[p2_idx]
                cv2.line(hud_frame, pt1, pt2, ELECTRIC_BLUE, 2, cv2.LINE_AA)
                cv2.line(hud_frame, pt1, pt2, CYAN_GLOW, 1, cv2.LINE_AA)

            # Draw joints (nodes)
            for idx, pt in enumerate(pixel_landmarks):
                if idx in (self.INDEX_TIP, self.THUMB_TIP, self.MIDDLE_TIP):
                    # Highlight interactive fingertips
                    node_color = CYAN_PRIMARY if idx == self.INDEX_TIP else EMERALD_GREEN
                    cv2.circle(hud_frame, pt, 7, node_color, -1, cv2.LINE_AA)
                    cv2.circle(hud_frame, pt, 11, CYAN_GLOW, 1, cv2.LINE_AA)
                else:
                    cv2.circle(hud_frame, pt, 3, CYAN_PRIMARY, -1, cv2.LINE_AA)

            # Draw visual pinch tether if pinching
            if pinch_active and pinch_point:
                thumb_pt = pixel_landmarks[self.THUMB_TIP]
                cv2.line(hud_frame, thumb_pt, pinch_point, EMERALD_GREEN, 2, cv2.LINE_AA)
                cv2.circle(hud_frame, pinch_point, 9, EMERALD_GREEN, 2, cv2.LINE_AA)

            # Index fingertip targeting reticle
            index_pt = pixel_landmarks[self.INDEX_TIP]
            cv2.circle(hud_frame, index_pt, 14, CYAN_PRIMARY, 1, cv2.LINE_AA)
            cv2.drawMarker(hud_frame, index_pt, CYAN_PRIMARY, cv2.MARKER_CROSS, 16, 1)

        # 3. Top HUD Status Bar Overlay
        top_bar_height = 42
        overlay = hud_frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, top_bar_height), DARK_HUD_BG, -1)
        cv2.addWeighted(overlay, 0.75, hud_frame, 0.25, 0, hud_frame)

        # Thin cyan accent line under header
        cv2.line(hud_frame, (0, top_bar_height), (w, top_bar_height), CYAN_GLOW, 1)

        # Status Badge: Mouse Control
        if is_paused:
            status_text = "PAUSED"
            status_color = ALERT_AMBER
        elif mouse_enabled:
            status_text = "MOUSE: LIVE"
            status_color = EMERALD_GREEN
        else:
            status_text = "MOUSE: STANDBY"
            status_color = (180, 180, 180)

        cv2.putText(hud_frame, status_text, (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2, cv2.LINE_AA)

        # Center Gesture Badge
        gesture_display = f"GESTURE: {active_gesture.upper()}"
        text_size = cv2.getTextSize(gesture_display, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)[0]
        gx = (w - text_size[0]) // 2
        cv2.putText(hud_frame, gesture_display, (gx, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, CYAN_PRIMARY, 2, cv2.LINE_AA)

        # Right FPS & Latency
        fps_text = f"FPS {self.fps} | {self.latency_ms:.1f}ms"
        fps_size = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)[0]
        cv2.putText(hud_frame, fps_text, (w - fps_size[0] - 12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 230, 240), 1, cv2.LINE_AA)

        # 4. Prominent Mode Banner (Just like in AI Hand Mouse)
        act_upper = active_gesture.upper()
        if "MOVE" in act_upper:
            act_col = (50, 240, 50)  # Bright green
            act_txt = "MOVE"
        elif "CLICK" in act_upper:
            act_col = (255, 240, 0)  # Neon cyan
            act_txt = "CLICK"
        elif "SCROLL" in act_upper:
            act_col = (0, 215, 255)  # Amber / Yellow
            act_txt = "SCROLL"
        elif "STOP" in act_upper:
            act_col = (60, 60, 245)  # Red
            act_txt = "STOP"
        else:
            act_col = (180, 180, 180)
            act_txt = act_upper

        cv2.putText(hud_frame, act_txt, (20, 75), cv2.FONT_HERSHEY_DUPLEX, 0.95, act_col, 2, cv2.LINE_AA)

        return hud_frame
