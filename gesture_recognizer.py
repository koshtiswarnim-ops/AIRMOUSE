"""
gesture_recognizer.py - Hand Gesture Classification and State Estimation for AIRMOUSE AI
Detects hand gestures: Hand Movement (Open Hand / Pointing), Pinch to Click, Middle Pinch to Scroll, Fist to Stop.
"""

import math
import time
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum


class GestureType(Enum):
    """Supported hand gesture states."""
    NO_HAND = "No Hand"
    MOVE = "MOVE"
    PINCH_INDEX = "CLICK"
    DRAGGING = "DRAG"
    PINCH_MIDDLE = "SCROLL"
    FIST = "STOP"
    OTHER = "MOVE"


class GestureRecognizer:
    """Classifies hand landmarks into actionable gestures with hysteresis and debouncing."""

    # Key landmark indices
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

    def __init__(self):
        self.last_gesture = GestureType.NO_HAND
        self.is_pinching_index = False
        self.is_pinching_middle = False
        self.pinch_start_time = 0.0
        self.is_dragging = False

        self.scroll_anchor_y = 0.0
        self.last_click_time = 0.0

    @staticmethod
    def _dist(p1: Dict[str, float], p2: Dict[str, float]) -> float:
        """Calculate 2D Euclidean distance between two normalized landmarks."""
        dx = p1["x"] - p2["x"]
        dy = p1["y"] - p2["y"]
        return math.hypot(dx, dy)

    def get_finger_states(self, landmarks: List[Dict[str, float]]) -> Dict[str, bool]:
        """Determine whether each finger is extended or folded."""
        if not landmarks or len(landmarks) < 21:
            return {"thumb": False, "index": False, "middle": False, "ring": False, "pinky": False}

        wrist = landmarks[self.WRIST]
        index_mcp = landmarks[self.INDEX_MCP]
        pinky_mcp = landmarks[self.PINKY_MCP]

        # Thumb
        thumb_tip = landmarks[self.THUMB_TIP]
        thumb_ip = landmarks[self.THUMB_IP]
        thumb_extended = (
            self._dist(thumb_tip, pinky_mcp) > (self._dist(thumb_ip, pinky_mcp) * 1.1)
            and self._dist(thumb_tip, index_mcp) > 0.07
        )

        def is_finger_extended(tip_idx: int, pip_idx: int, mcp_idx: int) -> bool:
            tip = landmarks[tip_idx]
            pip = landmarks[pip_idx]
            mcp = landmarks[mcp_idx]
            return (self._dist(tip, wrist) > self._dist(pip, wrist) * 1.05) and (
                self._dist(tip, mcp) > self._dist(pip, mcp) * 1.15
            )

        index_extended = is_finger_extended(self.INDEX_TIP, self.INDEX_PIP, self.INDEX_MCP)
        middle_extended = is_finger_extended(self.MIDDLE_TIP, self.MIDDLE_PIP, self.MIDDLE_MCP)
        ring_extended = is_finger_extended(self.RING_TIP, self.RING_PIP, self.RING_MCP)
        pinky_extended = is_finger_extended(self.PINKY_TIP, self.PINKY_PIP, self.PINKY_MCP)

        return {
            "thumb": thumb_extended,
            "index": index_extended,
            "middle": middle_extended,
            "ring": ring_extended,
            "pinky": pinky_extended,
        }

    def classify_gesture(
        self,
        landmarks: List[Dict[str, float]],
        pinch_threshold: float = 0.045,
        scroll_pinch_threshold: float = 0.045,
        drag_hold_duration: float = 0.40,
        enable_drag: bool = False,
    ) -> Tuple[GestureType, Dict[str, Any]]:
        """Classify current hand gesture and return action flags with hysteresis."""
        now = time.time()

        if not landmarks or len(landmarks) < 21:
            was_dragging = self.is_dragging
            self.is_pinching_index = False
            self.is_pinching_middle = False
            self.is_dragging = False
            self.last_gesture = GestureType.NO_HAND
            return GestureType.NO_HAND, {
                "trigger_click": False,
                "release_drag": was_dragging,
                "scroll_delta": 0.0,
                "index_point": None,
                "pinch_distance": 1.0,
                "can_move": False,
            }

        fingers = self.get_finger_states(landmarks)
        num_extended = sum(fingers.values())

        thumb_tip = landmarks[self.THUMB_TIP]
        index_tip = landmarks[self.INDEX_TIP]
        middle_tip = landmarks[self.MIDDLE_TIP]
        index_mcp = landmarks[self.INDEX_MCP]

        # Fingertip-accurate aiming (85% tip, 15% knuckle for micro-stabilization)
        track_point = {
            "x": index_tip["x"] * 0.85 + index_mcp["x"] * 0.15,
            "y": index_tip["y"] * 0.85 + index_mcp["y"] * 0.15,
        }

        d_index_pinch = self._dist(thumb_tip, index_tip)
        d_middle_pinch = self._dist(thumb_tip, middle_tip)
        d_index_flex = self._dist(index_tip, index_mcp)

        trigger_click = False
        release_drag = False
        scroll_delta = 0.0

        # Scale normalization with robust bounds
        wrist = landmarks[self.WRIST]
        middle_mcp = landmarks[self.MIDDLE_MCP]
        palm_scale = max(0.12, min(0.40, self._dist(wrist, middle_mcp)))
        scale_factor = max(0.80, min(1.30, palm_scale / 0.20))

        pinch_enter_th = pinch_threshold * scale_factor
        pinch_exit_th = pinch_enter_th * 1.25

        scroll_enter_th = scroll_pinch_threshold * scale_factor
        scroll_exit_th = scroll_enter_th * 1.25

        # Also support index air-tap (finger tap forward while pointing)
        is_index_air_tap = (
            d_index_flex < 0.115
            and fingers["index"]
            and not fingers["middle"]
            and not fingers["ring"]
            and not fingers["pinky"]
        )
        is_click_engaged = (d_index_pinch < pinch_enter_th) or is_index_air_tap

        # 1. Closed Fist (All fingers folded) -> STOP
        if num_extended <= 0 or (num_extended == 1 and fingers["thumb"] and not fingers["index"]):
            if self.is_dragging:
                release_drag = True
                self.is_dragging = False
            self.is_pinching_index = False
            self.is_pinching_middle = False
            self.last_gesture = GestureType.FIST
            return GestureType.FIST, {
                "trigger_click": False,
                "release_drag": release_drag,
                "scroll_delta": 0.0,
                "index_point": track_point,
                "pinch_distance": d_index_pinch,
                "can_move": False,
            }

        # 2. Middle Finger Pinch -> SCROLL
        if not self.is_pinching_middle:
            if d_middle_pinch < scroll_enter_th and d_index_pinch > pinch_exit_th:
                self.is_pinching_middle = True
                self.scroll_anchor_y = middle_tip["y"]
        else:
            if d_middle_pinch > scroll_exit_th:
                self.is_pinching_middle = False

        if self.is_pinching_middle:
            scroll_delta = self.scroll_anchor_y - middle_tip["y"]
            self.scroll_anchor_y = (self.scroll_anchor_y * 0.75) + (middle_tip["y"] * 0.25)
            self.last_gesture = GestureType.PINCH_MIDDLE
            return GestureType.PINCH_MIDDLE, {
                "trigger_click": False,
                "release_drag": False,
                "scroll_delta": scroll_delta,
                "index_point": track_point,
                "pinch_distance": d_middle_pinch,
                "can_move": False,  # Freeze cursor during scroll for stability
            }

        # 3. Index Finger Pinch or Air-Tap -> CLICK & DRAG
        if not self.is_pinching_index:
            if is_click_engaged:
                self.is_pinching_index = True
                self.pinch_start_time = now
                trigger_click = True  # Clean click on tap
        else:
            if (d_index_pinch > pinch_exit_th) and not is_index_air_tap:
                self.is_pinching_index = False
                if self.is_dragging:
                    release_drag = True
                    self.is_dragging = False
            else:
                if enable_drag and not self.is_dragging:
                    if (now - self.pinch_start_time) >= drag_hold_duration:
                        self.is_dragging = True

        if self.is_pinching_index:
            gesture = GestureType.DRAGGING if self.is_dragging else GestureType.PINCH_INDEX
            self.last_gesture = gesture
            return gesture, {
                "trigger_click": trigger_click,
                "release_drag": False,
                "scroll_delta": 0.0,
                "index_point": track_point,
                "pinch_distance": d_index_pinch,
                "can_move": True,  # Can move while dragging
            }

        # 4. Standard Navigation -> MOVE
        # In the user's photo, holding the hand up (either pointing or open palm) operates the cursor!
        self.last_gesture = GestureType.MOVE
        return GestureType.MOVE, {
            "trigger_click": False,
            "release_drag": release_drag,
            "scroll_delta": 0.0,
            "index_point": track_point,
            "pinch_distance": d_index_pinch,
            "can_move": True,
        }
