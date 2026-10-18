"""
test_gestures.py - Unit tests for gesture classification in AIRMOUSE AI
"""

import time
import pytest
from gesture_recognizer import GestureRecognizer, GestureType


def build_synthetic_landmarks(
    thumb_ext=True,
    index_ext=False,
    middle_ext=False,
    ring_ext=False,
    pinky_ext=False,
    pinch_index=False,
    pinch_middle=False,
):
    """Generate 21 synthetic normalized landmarks matching given posture."""
    # Base palm landmarks
    lms = [{"x": 0.5, "y": 0.7, "z": 0.0} for _ in range(21)]
    # Wrist
    lms[0] = {"x": 0.5, "y": 0.8, "z": 0.0}

    # Pinky MCP (17) for thumb reference
    lms[17] = {"x": 0.65, "y": 0.65, "z": 0.0}

    # Thumb (1 to 4)
    lms[1] = {"x": 0.45, "y": 0.75, "z": 0.0}
    lms[2] = {"x": 0.40, "y": 0.70, "z": 0.0}
    lms[3] = {"x": 0.35, "y": 0.65, "z": 0.0}
    if thumb_ext:
        lms[4] = {"x": 0.25, "y": 0.60, "z": 0.0}  # Extended outward away from pinky MCP
    else:
        lms[4] = {"x": 0.55, "y": 0.65, "z": 0.0}  # Folded towards palm

    # Index finger (5 to 8)
    lms[5] = {"x": 0.45, "y": 0.55, "z": 0.0}  # MCP
    lms[6] = {"x": 0.45, "y": 0.45, "z": 0.0}  # PIP
    lms[7] = {"x": 0.45, "y": 0.38, "z": 0.0}  # DIP
    if index_ext:
        lms[8] = {"x": 0.45, "y": 0.25, "z": 0.0}  # Extended high
    else:
        lms[8] = {"x": 0.45, "y": 0.60, "z": 0.0}  # Curled down

    # Middle finger (9 to 12)
    lms[9] = {"x": 0.50, "y": 0.53, "z": 0.0}  # MCP
    lms[10] = {"x": 0.50, "y": 0.43, "z": 0.0}
    lms[11] = {"x": 0.50, "y": 0.35, "z": 0.0}
    if middle_ext:
        lms[12] = {"x": 0.50, "y": 0.22, "z": 0.0}
    else:
        lms[12] = {"x": 0.50, "y": 0.60, "z": 0.0}

    # Ring finger (13 to 16)
    lms[13] = {"x": 0.55, "y": 0.55, "z": 0.0}
    lms[14] = {"x": 0.55, "y": 0.45, "z": 0.0}
    lms[15] = {"x": 0.55, "y": 0.38, "z": 0.0}
    if ring_ext:
        lms[16] = {"x": 0.55, "y": 0.26, "z": 0.0}
    else:
        lms[16] = {"x": 0.55, "y": 0.60, "z": 0.0}

    # Pinky finger (17 to 20)
    lms[18] = {"x": 0.62, "y": 0.52, "z": 0.0}
    lms[19] = {"x": 0.62, "y": 0.45, "z": 0.0}
    if pinky_ext:
        lms[20] = {"x": 0.62, "y": 0.32, "z": 0.0}
    else:
        lms[20] = {"x": 0.62, "y": 0.60, "z": 0.0}

    # Overwrite tips if pinching
    if pinch_index:
        lms[4] = {"x": 0.45, "y": 0.35, "z": 0.0}  # Thumb tip
        lms[8] = {"x": 0.46, "y": 0.36, "z": 0.0}  # Index tip near thumb
    elif pinch_middle:
        lms[4] = {"x": 0.50, "y": 0.35, "z": 0.0}  # Thumb tip
        lms[12] = {"x": 0.51, "y": 0.36, "z": 0.0}  # Middle tip near thumb
        lms[8] = {"x": 0.40, "y": 0.25, "z": 0.0}  # Index tip far away

    return lms


def test_no_hand_detection():
    recognizer = GestureRecognizer()
    gesture, meta = recognizer.classify_gesture([])
    assert gesture == GestureType.NO_HAND
    assert meta["trigger_click"] is False
    assert meta["index_point"] is None


def test_open_hand_move():
    recognizer = GestureRecognizer()
    lms = build_synthetic_landmarks(thumb_ext=True, index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True)
    gesture, meta = recognizer.classify_gesture(lms)
    assert gesture == GestureType.MOVE
    assert meta["can_move"] is True
    assert meta["trigger_click"] is False


def test_fist_stop():
    recognizer = GestureRecognizer()
    lms = build_synthetic_landmarks(thumb_ext=False, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
    gesture, meta = recognizer.classify_gesture(lms)
    assert gesture == GestureType.FIST
    assert meta["can_move"] is False
    assert meta["trigger_click"] is False


def test_pointing_cursor_move():
    recognizer = GestureRecognizer()
    lms = build_synthetic_landmarks(thumb_ext=False, index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False)
    gesture, meta = recognizer.classify_gesture(lms)
    assert gesture == GestureType.MOVE
    assert meta["can_move"] is True
    assert meta["index_point"] is not None


def test_index_pinch_and_single_click():
    recognizer = GestureRecognizer()
    lms = build_synthetic_landmarks(pinch_index=True)

    # First frame of pinch -> should trigger click
    g1, meta1 = recognizer.classify_gesture(lms)
    assert g1 == GestureType.PINCH_INDEX
    assert meta1["trigger_click"] is True

    # Second consecutive frame of pinch -> should NOT trigger repeated click
    g2, meta2 = recognizer.classify_gesture(lms)
    assert g2 == GestureType.PINCH_INDEX
    assert meta2["trigger_click"] is False


def test_middle_pinch_scroll():
    recognizer = GestureRecognizer()
    lms = build_synthetic_landmarks(pinch_middle=True)

    # Initial middle pinch frame establishes anchor
    g1, meta1 = recognizer.classify_gesture(lms)
    assert g1 == GestureType.PINCH_MIDDLE

    # Move hand upward (smaller y) to simulate upward scroll
    lms[4]["y"] -= 0.05
    lms[12]["y"] -= 0.05
    g2, meta2 = recognizer.classify_gesture(lms)
    assert g2 == GestureType.PINCH_MIDDLE
    assert meta2["scroll_delta"] > 0.0  # Upward scroll delta
