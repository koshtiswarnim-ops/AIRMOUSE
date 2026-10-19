"""
Unit tests for CursorDotOverlay (Red on move, Blue on click).
"""

import time
import pytest
from cursor_overlay import get_cursor_overlay, DummyCursorOverlay, Win32CursorDotOverlay


def test_cursor_overlay_singleton():
    overlay1 = get_cursor_overlay()
    overlay2 = get_cursor_overlay()
    assert overlay1 is overlay2


def test_cursor_overlay_methods():
    overlay = get_cursor_overlay()
    
    # Test position update
    overlay.update_position(300, 300, visible=True)
    if isinstance(overlay, Win32CursorDotOverlay):
        assert overlay.x == 300
        assert overlay.y == 300
        assert overlay.visible is True

    # Test flash click (turns blue)
    overlay.flash_click(0.3)
    if isinstance(overlay, Win32CursorDotOverlay):
        assert overlay.click_expiry > time.time()

    # Test drag state
    overlay.set_clicking(True)
    if isinstance(overlay, Win32CursorDotOverlay):
        assert overlay.is_clicking is True

    overlay.set_clicking(False)
    if isinstance(overlay, Win32CursorDotOverlay):
        assert overlay.is_clicking is False

    # Test hide
    overlay.hide()
    if isinstance(overlay, Win32CursorDotOverlay):
        assert overlay.visible is False
