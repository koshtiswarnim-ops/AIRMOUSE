"""
test_coordinates.py - Unit tests for coordinate transformation and smoothing in AIRMOUSE AI
"""

import pytest
from settings import AppSettings
from mouse_controller import MouseController


def test_coordinate_mapping_center():
    settings = AppSettings(margin_x=0.15, margin_y=0.15, sensitivity=1.0, smoothing_factor=0.0)
    controller = MouseController(settings)
    controller.screen_w, controller.screen_h = 1920, 1080

    sx, sy = controller.map_coordinates(0.5, 0.5)
    assert abs(sx - 960) <= 2
    assert abs(sy - 540) <= 2


def test_screen_bounds_clamping():
    settings = AppSettings(margin_x=0.15, margin_y=0.15, sensitivity=2.0)
    controller = MouseController(settings)
    controller.screen_w, controller.screen_h = 1920, 1080

    # Extremes outside the active margin box
    sx_min, sy_min = controller.map_coordinates(-0.2, -0.2)
    assert 0 <= sx_min < 1920
    assert 0 <= sy_min < 1080

    sx_max, sy_max = controller.map_coordinates(1.5, 1.5)
    assert 0 <= sx_max < 1920
    assert 0 <= sy_max < 1080


def test_smoothing_progression():
    settings = AppSettings(margin_x=0.0, margin_y=0.0, sensitivity=1.0, smoothing_factor=0.5)
    controller = MouseController(settings)
    controller.screen_w, controller.screen_h = 1000, 1000

    import time
    # Start at origin
    x1, y1 = controller.map_coordinates(0.0, 0.0)
    assert x1 < 100

    # Advance time and step
    time.sleep(0.02)
    x2, y2 = controller.map_coordinates(1.0, 1.0)
    assert x2 > x1
    assert x2 < 995


def test_safety_release_functionality():
    settings = AppSettings()
    controller = MouseController(settings)
    controller.is_left_down = True
    controller.release_all()
    assert controller.is_left_down is False
