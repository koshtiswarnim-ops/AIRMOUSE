"""
web_server.py - Futuristic Localhost Web Dashboard for AIRMOUSE AI
Serves live MJPEG optical feed with cyber HUD overlay, telemetry, and interactive controls via browser.
"""

import os
import sys
import time
import subprocess
import threading
import logging
from datetime import datetime
from collections import deque
from typing import Optional

try:
    import cv2
except Exception:
    cv2 = None

import numpy as np
from flask import Flask, Response, jsonify, request, render_template_string

from settings import AppSettings

# Detect cloud/serverless deployment (Vercel, AWS Lambda)
IS_CLOUD_DEPLOYMENT = bool(
    os.environ.get("VERCEL")
    or os.environ.get("VERCEL_ENV")
    or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    or os.environ.get("NOW_REGION")
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AIRMOUSE-WEB")

app = Flask(__name__)

# Application Core Settings
settings = AppSettings()

# Desktop components initialized lazily on local execution
tracker = None
recognizer = None
mouse_ctrl = None
GestureType = None


def init_desktop_components() -> bool:
    """Safely initialize local desktop camera and mouse controllers."""
    global tracker, recognizer, mouse_ctrl, GestureType
    if IS_CLOUD_DEPLOYMENT:
        return False

    try:
        from gesture_recognizer import GestureRecognizer, GestureType as GT
        GestureType = GT
        if recognizer is None:
            recognizer = GestureRecognizer()
    except Exception as e:
        logger.warning(f"GestureRecognizer deferred: {e}")

    try:
        from hand_tracker import HandTracker
        if tracker is None:
            tracker = HandTracker(
                camera_index=settings.camera_index,
                width=settings.camera_width,
                height=settings.camera_height,
            )
    except Exception as e:
        logger.warning(f"HandTracker deferred: {e}")

    try:
        from mouse_controller import MouseController
        if mouse_ctrl is None:
            mouse_ctrl = MouseController(settings)
    except Exception as e:
        logger.warning(f"MouseController deferred: {e}")

    return tracker is not None


# Initialize on local desktop startup (kept out of Vercel serverless startup)
if not IS_CLOUD_DEPLOYMENT:
    try:
        init_desktop_components()
    except Exception as e:
        logger.warning(f"Local desktop initialization deferred: {e}")

# Global State
is_camera_active = False
camera_thread: Optional[threading.Thread] = None
latest_encoded_jpeg: Optional[bytes] = None
frame_lock = threading.Lock()

current_gesture = "STANDBY"
has_hand_detected = False
live_fps = 0.0
live_latency = 0.0
event_logs = deque(maxlen=60)


def log_event(message: str) -> None:
    """Append timestamped message to event log."""
    ts = datetime.now().strftime("%H:%M:%S")
    event_logs.append(f"[{ts}] {message}")


if IS_CLOUD_DEPLOYMENT:
    log_event("AIRMOUSE AI Cloud Preview initialized.")
    log_event("Webcam & Virtual Mouse run locally on desktop.")
else:
    log_event("AIRMOUSE AI Web Core initialized.")
    log_event("Mouse control is STANDBY (Safe mode).")


def generate_empty_placeholder_jpeg() -> bytes:
    """Generate futuristic standby image when camera is off."""
    w, h = 640, 480
    if cv2 is not None:
        try:
            img = np.zeros((h, w, 3), dtype=np.uint8)
            img[:] = (10, 14, 22)

            # Cyber Grid
            for x in range(0, w, 40):
                cv2.line(img, (x, 0), (x, h), (20, 26, 38), 1)
            for y in range(0, h, 40):
                cv2.line(img, (0, y), (w, y), (20, 26, 38), 1)

            title_txt = "AIRMOUSE AI — CLOUD PREVIEW" if IS_CLOUD_DEPLOYMENT else "AIRMOUSE AI — SENSORS STANDBY"
            sub_txt = "RUN LOCALLY FOR LIVE WEBCAM & MOUSE" if IS_CLOUD_DEPLOYMENT else "CLICK 'START CAMERA' TO ACTIVATE LIVE STREAM"

            cv2.putText(
                img,
                title_txt,
                (w // 2 - 180, h // 2 - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 240, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                img,
                sub_txt,
                (w // 2 - 200, h // 2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (140, 160, 180),
                1,
                cv2.LINE_AA,
            )
            _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return buf.tobytes()
        except Exception:
            pass

    # Fallback with Pillow if OpenCV is unavailable in cloud environment
    try:
        from PIL import Image, ImageDraw
        import io
        img = Image.new("RGB", (w, h), (10, 14, 22))
        draw = ImageDraw.Draw(img)
        title_txt = "AIRMOUSE AI — CLOUD PREVIEW" if IS_CLOUD_DEPLOYMENT else "AIRMOUSE AI — SENSORS STANDBY"
        sub_txt = "RUN LOCALLY FOR LIVE WEBCAM & MOUSE" if IS_CLOUD_DEPLOYMENT else "CLICK 'START CAMERA' TO ACTIVATE LIVE STREAM"
        draw.text((w // 2 - 140, h // 2 - 15), title_txt, fill=(0, 240, 255))
        draw.text((w // 2 - 170, h // 2 + 15), sub_txt, fill=(140, 160, 180))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except Exception:
        # Minimal valid 1x1 black JPEG fallback
        return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'


latest_encoded_jpeg = generate_empty_placeholder_jpeg()


def camera_worker_loop():
    """Background worker continuously running camera capture, inference, and mouse control."""
    global is_camera_active, latest_encoded_jpeg, current_gesture, has_hand_detected, live_fps, live_latency

    if tracker is None or recognizer is None:
        return

    last_gesture_enum = None

    while is_camera_active:
        try:
            success, raw_frame, norm_lms, px_lms = tracker.process_frame(mirror=True)
            if not success or raw_frame is None:
                time.sleep(0.01)
                continue

            # Gesture Classification
            gesture_enum, meta = recognizer.classify_gesture(
                norm_lms,
                pinch_threshold=settings.pinch_threshold,
                scroll_pinch_threshold=settings.scroll_pinch_threshold,
                drag_hold_duration=settings.drag_hold_duration,
                enable_drag=settings.enable_drag_and_drop,
            )

            if gesture_enum != last_gesture_enum:
                if gesture_enum != GestureType.OTHER:
                    log_event(f"Recognized: {gesture_enum.value}")
                last_gesture_enum = gesture_enum

            # Execute Virtual Mouse
            mouse_ctrl.execute_actions(
                gesture_enum,
                meta,
                on_event_cb=log_event,
            )

            # Visual Pinch Tether Target
            pinch_active = gesture_enum in (GestureType.PINCH_INDEX, GestureType.DRAGGING, GestureType.PINCH_MIDDLE)
            pinch_target = None
            if pinch_active and px_lms and len(px_lms) == 21:
                if gesture_enum == GestureType.PINCH_MIDDLE:
                    pinch_target = px_lms[HandTracker.MIDDLE_TIP]
                else:
                    pinch_target = px_lms[HandTracker.INDEX_TIP]

            # Draw Cyber HUD
            annotated = tracker.draw_futuristic_hud(
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

            # Encode Frame to JPEG
            ret, jpeg_buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret:
                with frame_lock:
                    latest_encoded_jpeg = jpeg_buffer.tobytes()
                    current_gesture = gesture_enum.value
                    has_hand_detected = len(norm_lms) == 21
                    live_fps = tracker.fps
                    live_latency = tracker.latency_ms

            time.sleep(0.005)
        except Exception as e:
            logger.error(f"Error in camera loop: {e}")
            time.sleep(0.03)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIRMOUSE AI — Futuristic Gesture System</title>
    <style>
        :root {
            --bg-dark: #0a0e17;
            --bg-card: #111827;
            --bg-card-alt: #162032;
            --border-cyan: #00f0ff;
            --border-dim: #1e293b;
            --accent-cyan: #00f0ff;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --accent-red: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        /* Header */
        header {
            background: var(--bg-card);
            border: 1px solid var(--border-dim);
            border-radius: 12px;
            padding: 14px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 20px rgba(0, 240, 255, 0.05);
        }

        .header-title h1 {
            font-size: 24px;
            font-weight: 800;
            color: var(--accent-cyan);
            letter-spacing: 1px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .header-title p {
            font-size: 11px;
            font-weight: 700;
            color: var(--text-muted);
            letter-spacing: 1.5px;
        }

        .badges {
            display: flex;
            gap: 10px;
        }

        .badge {
            padding: 6px 14px;
            border-radius: 8px;
            font-family: 'Consolas', monospace;
            font-size: 12px;
            font-weight: 700;
            background: #1f2937;
            color: var(--text-muted);
            border: 1px solid var(--border-dim);
            transition: all 0.2s;
        }

        .badge.online {
            background: #064e3b;
            color: var(--accent-green);
            border-color: #059669;
        }

        .badge.active {
            background: #064e3b;
            color: var(--accent-green);
            border-color: #059669;
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
        }

        .badge.paused {
            background: #451a03;
            color: var(--accent-amber);
            border-color: #d97706;
        }

        .badge.stopped {
            background: #450a0a;
            color: var(--accent-red);
            border-color: #dc2626;
        }

        /* Layout Grid */
        .workspace {
            display: grid;
            grid-template-columns: 1fr 420px;
            gap: 16px;
            flex: 1;
        }

        @media (max-width: 1024px) {
            .workspace {
                grid-template-columns: 1fr;
            }
        }

        /* Left Column */
        .left-col {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .video-card {
            background: #000;
            border: 2px solid var(--border-dim);
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
            position: relative;
            min-height: 480px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            transition: border-color 0.3s;
        }

        .video-card.live {
            border-color: var(--border-cyan);
            box-shadow: 0 0 25px rgba(0, 240, 255, 0.2);
        }

        .video-card img {
            width: 100%;
            height: 100%;
            max-height: 540px;
            object-fit: contain;
            display: block;
        }

        .telemetry-bar {
            background: var(--bg-card);
            border: 1px solid var(--border-dim);
            border-radius: 10px;
            padding: 10px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 13px;
        }

        .telemetry-item {
            font-weight: 700;
        }

        .telemetry-item.hand-on { color: var(--accent-green); }
        .telemetry-item.hand-off { color: var(--accent-red); }
        .telemetry-item.gesture-label { color: var(--accent-cyan); font-family: 'Consolas', monospace; }
        .telemetry-item.metrics { color: var(--text-muted); font-family: 'Consolas', monospace; }

        /* Gesture Reference Guide */
        .guide-card {
            background: var(--bg-card);
            border: 1px solid var(--border-dim);
            border-radius: 10px;
            padding: 12px 16px;
        }

        .card-header {
            font-size: 11px;
            font-weight: 800;
            color: var(--text-muted);
            letter-spacing: 1px;
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .guide-grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 8px;
        }

        @media (max-width: 800px) {
            .guide-grid {
                grid-template-columns: repeat(3, 1fr);
            }
        }

        .guide-item {
            background: var(--bg-card-alt);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 6px;
            padding: 8px 4px;
            text-align: center;
        }

        .guide-item .g-name {
            font-size: 11px;
            font-weight: 700;
            color: var(--accent-cyan);
            margin-bottom: 2px;
        }

        .guide-item .g-act {
            font-size: 10px;
            color: var(--text-muted);
        }

        /* Right Column */
        .right-col {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-dim);
            border-radius: 12px;
            padding: 16px;
        }

        .card-title {
            font-size: 13px;
            font-weight: 800;
            color: var(--accent-cyan);
            letter-spacing: 1px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        /* Buttons Grid */
        .btn-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .btn {
            padding: 10px 14px;
            border: none;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.5px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            color: #fff;
        }

        .btn:hover {
            transform: translateY(-1px);
            filter: brightness(1.15);
        }

        .btn-camera-start { background: #1e3a8a; }
        .btn-camera-stop { background: #b91c1c; }
        .btn-mouse-enable { background: #065f46; }
        .btn-mouse-disable { background: #b91c1c; }
        .btn-pause { background: #78350f; }
        .btn-emergency { background: #7f1d1d; }

        /* Sliders */
        .slider-group {
            margin-bottom: 12px;
        }

        .slider-header {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-main);
            margin-bottom: 4px;
        }

        .slider-header span.val {
            font-family: 'Consolas', monospace;
            color: var(--accent-cyan);
            font-weight: 700;
        }

        input[type="range"] {
            width: 100%;
            height: 6px;
            background: #1f2937;
            border-radius: 4px;
            outline: none;
            accent-color: var(--accent-cyan);
            cursor: pointer;
        }

        /* Switches */
        .switches-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
            border-top: 1px solid var(--border-dim);
            padding-top: 10px;
        }

        .switch-label {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: var(--text-muted);
            cursor: pointer;
        }

        .switch-label input {
            accent-color: var(--accent-cyan);
            cursor: pointer;
        }

        /* Activity Log */
        .log-box {
            background: #080c14;
            border: 1px solid #1f2937;
            border-radius: 8px;
            height: 180px;
            overflow-y: auto;
            padding: 10px;
            font-family: 'Consolas', monospace;
            font-size: 11px;
            color: #94a3b8;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .log-entry {
            white-space: pre-wrap;
            word-break: break-all;
        }
    </style>
</head>
<body>

    <!-- Header -->
    <header>
        <div class="header-title">
            <h1>⚡ AIRMOUSE AI</h1>
            <p>TOUCHLESS HUMAN-COMPUTER INTERACTION SYSTEM</p>
        </div>
        <div class="badges">
            <div id="badge-camera" class="badge">📷 CAMERA: STANDBY</div>
            <div id="badge-mouse" class="badge">🖱️ MOUSE: STANDBY</div>
        </div>
    </header>

    <!-- Main Workspace -->
    <div class="workspace">
        
        <!-- Left: Video & Guides -->
        <div class="left-col">
            <div id="video-card" class="video-card">
                <img id="stream-img" src="/video_feed" alt="AIRMOUSE Optical Feed">
            </div>

            <div class="telemetry-bar">
                <div id="telemetry-hand" class="telemetry-item hand-off">● NO HAND DETECTED</div>
                <div id="telemetry-gesture" class="telemetry-item gesture-label">GESTURE: STANDBY</div>
                <div id="telemetry-metrics" class="telemetry-item metrics">FPS: 0.0 | 0.0 ms</div>
            </div>

            <div class="guide-card">
                <div class="card-header">Gesture Matrix Reference</div>
                <div class="guide-grid">
                    <div class="guide-item">
                        <div class="g-name">☝️ Pointing</div>
                        <div class="g-act">Move Cursor</div>
                    </div>
                    <div class="guide-item">
                        <div class="g-name">🤏 Index Pinch</div>
                        <div class="g-act">Left Click</div>
                    </div>
                    <div class="guide-item">
                        <div class="g-name">✊ Pinch Hold</div>
                        <div class="g-act">Drag & Drop</div>
                    </div>
                    <div class="guide-item">
                        <div class="g-name">✌️ Mid Pinch</div>
                        <div class="g-act">V-Scroll</div>
                    </div>
                    <div class="guide-item">
                        <div class="g-name">🖐️ Open Palm</div>
                        <div class="g-act">Pause Action</div>
                    </div>
                    <div class="guide-item">
                        <div class="g-name">🤛 Closed Fist</div>
                        <div class="g-act">Stop Cursor</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Right: Controls & Log -->
        <div class="right-col">
            
            <!-- Controls Card -->
            <div class="card">
                <div class="card-title">COMMAND CONTROLS</div>
                <div class="btn-grid">
                    <button id="btn-camera" class="btn btn-camera-start" onclick="toggleCamera()">START CAMERA</button>
                    <button id="btn-mouse" class="btn btn-mouse-enable" onclick="toggleMouse()">ENABLE MOUSE</button>
                    <button id="btn-pause" class="btn btn-pause" onclick="togglePause()">PAUSE</button>
                    <button id="btn-emergency" class="btn btn-emergency" onclick="emergencyStop()">STOP ALL (ESC)</button>
                    <button id="btn-float-open" class="btn" style="background: #0284c7;" onclick="openFloatingWindow()">📺 FLOAT WEBCAM (DESKTOP)</button>
                    <button id="btn-float-close" class="btn" style="background: #334155;" onclick="closeFloatingWindow()">❌ HIDE WEBCAM</button>
                </div>
            </div>

            <!-- Tuning Card -->
            <div class="card">
                <div class="card-title">CALIBRATION & SENSITIVITY</div>
                
                <div class="slider-group">
                    <div class="slider-header">
                        <span>Sensitivity</span>
                        <span id="val-sens" class="val">1.6x</span>
                    </div>
                    <input type="range" id="slider-sens" min="0.8" max="3.2" step="0.1" value="1.6" oninput="updateSettings()">
                </div>

                <div class="slider-group">
                    <div class="slider-header">
                        <span>Cursor Smoothing</span>
                        <span id="val-smooth" class="val">0.55</span>
                    </div>
                    <input type="range" id="slider-smooth" min="0.1" max="0.9" step="0.05" value="0.55" oninput="updateSettings()">
                </div>

                <div class="slider-group">
                    <div class="slider-header">
                        <span>Pinch Threshold</span>
                        <span id="val-pinch" class="val">0.055</span>
                    </div>
                    <input type="range" id="slider-pinch" min="0.03" max="0.09" step="0.005" value="0.055" oninput="updateSettings()">
                </div>

                <div class="switches-grid">
                    <label class="switch-label" style="grid-column: span 2; color: #ff5252; font-weight: 600;">
                        <input type="checkbox" id="sw-cursor-dot" checked onchange="updateSettings()"> 🔴/🔵 Cursor Dot Halo (Red on move, Blue on click)
                    </label>
                    <label class="switch-label" style="grid-column: span 2; color: #38bdf8; font-weight: 600;">
                        <input type="checkbox" id="sw-auto-float" checked onchange="updateSettings()"> ⚡ Auto-Show Camera on Desktop when leaving website
                    </label>
                    <label class="switch-label">
                        <input type="checkbox" id="sw-cursor" checked onchange="updateSettings()"> Move Cursor
                    </label>
                    <label class="switch-label">
                        <input type="checkbox" id="sw-click" checked onchange="updateSettings()"> Left Click & Double-Tap
                    </label>
                    <label class="switch-label">
                        <input type="checkbox" id="sw-drag" onchange="updateSettings()"> Drag & Drop
                    </label>
                    <label class="switch-label">
                        <input type="checkbox" id="sw-scroll" checked onchange="updateSettings()"> V-Scroll
                    </label>
                </div>
            </div>

            <!-- Activity Card -->
            <div class="card" style="flex: 1; display: flex; flex-direction: column;">
                <div class="card-title">SYSTEM ACTIVITY LOG</div>
                <div id="log-box" class="log-box"></div>
            </div>

        </div>

    </div>

    <script>
        // Keyboard Emergency Stop
        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                emergencyStop();
            }
        });

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();

                // Camera Badge & Video Frame
                const bCam = document.getElementById('badge-camera');
                const vCard = document.getElementById('video-card');
                const btnCam = document.getElementById('btn-camera');

                if (data.camera_online) {
                    bCam.className = 'badge online';
                    bCam.innerText = '📷 CAMERA: ONLINE';
                    vCard.className = 'video-card live';
                    btnCam.className = 'btn btn-camera-stop';
                    btnCam.innerText = 'STOP CAMERA';
                } else {
                    bCam.className = 'badge';
                    bCam.innerText = '📷 CAMERA: DISCONNECTED';
                    vCard.className = 'video-card';
                    btnCam.className = 'btn btn-camera-start';
                    btnCam.innerText = 'START CAMERA';
                }

                // Mouse Badge & Button
                const bMouse = document.getElementById('badge-mouse');
                const btnMouse = document.getElementById('btn-mouse');
                const btnPause = document.getElementById('btn-pause');

                if (data.is_paused) {
                    bMouse.className = 'badge paused';
                    bMouse.innerText = '⏸️ MOUSE: PAUSED';
                    btnPause.innerText = 'RESUME';
                    btnPause.style.background = '#15803d';
                } else if (data.mouse_enabled) {
                    bMouse.className = 'badge active';
                    bMouse.innerText = '🖱️ MOUSE: LIVE';
                    btnMouse.className = 'btn btn-mouse-disable';
                    btnMouse.innerText = 'DISABLE MOUSE';
                    btnPause.innerText = 'PAUSE';
                    btnPause.style.background = '#78350f';
                } else {
                    bMouse.className = 'badge';
                    bMouse.innerText = '🖱️ MOUSE: STANDBY';
                    btnMouse.className = 'btn btn-mouse-enable';
                    btnMouse.innerText = 'ENABLE MOUSE';
                    btnPause.innerText = 'PAUSE';
                    btnPause.style.background = '#78350f';
                }

                // Telemetry
                const tHand = document.getElementById('telemetry-hand');
                if (data.has_hand) {
                    tHand.className = 'telemetry-item hand-on';
                    tHand.innerText = '● HAND TRACKED';
                } else {
                    tHand.className = 'telemetry-item hand-off';
                    tHand.innerText = '● NO HAND DETECTED';
                }

                document.getElementById('telemetry-gesture').innerText = 'GESTURE: ' + data.gesture.toUpperCase();
                document.getElementById('telemetry-metrics').innerText = `FPS: ${data.fps} | ${data.latency.toFixed(1)} ms`;

                // Logs
                const logBox = document.getElementById('log-box');
                const currentText = data.logs.join('\\n');
                if (logBox.dataset.last !== currentText) {
                    logBox.innerHTML = data.logs.map(l => `<div class="log-entry">${l}</div>`).join('');
                    logBox.dataset.last = currentText;
                    logBox.scrollTop = logBox.scrollHeight;
                }

            } catch (err) {
                console.error("Status fetch error:", err);
            }
        }

        async function toggleCamera() {
            await fetch('/api/toggle_camera', { method: 'POST' });
            fetchStatus();
        }

        async function toggleMouse() {
            await fetch('/api/toggle_mouse', { method: 'POST' });
            fetchStatus();
        }

        async function togglePause() {
            await fetch('/api/toggle_pause', { method: 'POST' });
            fetchStatus();
        }

        async function emergencyStop() {
            await fetch('/api/emergency_stop', { method: 'POST' });
            fetchStatus();
        }

        async function updateSettings() {
            const sens = parseFloat(document.getElementById('slider-sens').value);
            const smooth = parseFloat(document.getElementById('slider-smooth').value);
            const pinch = parseFloat(document.getElementById('slider-pinch').value);

            document.getElementById('val-sens').innerText = sens.toFixed(1) + 'x';
            document.getElementById('val-smooth').innerText = smooth.toFixed(2);
            document.getElementById('val-pinch').innerText = pinch.toFixed(3);

            const payload = {
                sensitivity: sens,
                smoothing_factor: smooth,
                pinch_threshold: pinch,
                scroll_pinch_threshold: pinch,
                enable_cursor_movement: document.getElementById('sw-cursor').checked,
                enable_left_click: document.getElementById('sw-click').checked,
                enable_drag_and_drop: document.getElementById('sw-drag').checked,
                enable_scrolling: document.getElementById('sw-scroll').checked,
                auto_float_camera: document.getElementById('sw-auto-float').checked,
                show_cursor_dot: document.getElementById('sw-cursor-dot').checked,
            };

            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }

        async function openFloatingWindow() {
            try {
                await fetch('/api/open_floating_window', { method: 'POST' });
            } catch (err) {
                console.error("Error opening floating window:", err);
            }
        }

        async function closeFloatingWindow() {
            try {
                await fetch('/api/close_floating_window', { method: 'POST' });
            } catch (err) {
                console.error("Error closing floating window:", err);
            }
        }

        function handleAutoFloat() {
            const sw = document.getElementById('sw-auto-float');
            if (sw && sw.checked) {
                openFloatingWindow();
            }
        }

        // Auto-show floating camera when user clicks outside browser or switches to another app
        window.addEventListener('blur', () => {
            handleAutoFloat();
        });

        // Auto-show floating camera when tab is minimized or hidden
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') {
                handleAutoFloat();
            }
        });

        // Turn off mouse and clean up floating HUD when the website window is closed
        window.addEventListener('beforeunload', () => {
            navigator.sendBeacon('/api/client_exit');
        });

        // Status Polling Interval (200ms)
        setInterval(fetchStatus, 200);
        fetchStatus();
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/video_feed")
def video_feed():
    """Video streaming route returning multipart MJPEG."""
    def frame_generator():
        while True:
            with frame_lock:
                frame_data = latest_encoded_jpeg

            if frame_data is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_data + b"\r\n"
                )
            time.sleep(0.03)

    return Response(frame_generator(), mimetype="multipart/x-mixed-replace; boundary=frame")


floating_hud_proc = None
last_client_ping = time.time()


def open_floating_hud() -> bool:
    """Launch or focus always-on-top floating camera window on Windows desktop."""
    global floating_hud_proc
    if floating_hud_proc is not None and floating_hud_proc.poll() is None:
        return True
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "floating_hud.py")
        floating_hud_proc = subprocess.Popen(
            [sys.executable, script_path],
            cwd=os.path.dirname(script_path),
        )
        log_event("Popped out floating Always-On-Top webcam screen on desktop.")
        return True
    except Exception as e:
        logger.error(f"Error launching floating HUD: {e}")
        return False


def close_floating_hud() -> None:
    """Safely terminate floating camera window."""
    global floating_hud_proc
    if floating_hud_proc is not None and floating_hud_proc.poll() is None:
        try:
            floating_hud_proc.terminate()
            floating_hud_proc.wait(timeout=1.0)
        except Exception:
            try:
                floating_hud_proc.kill()
            except Exception:
                pass
        log_event("Closed floating camera screen.")
    floating_hud_proc = None


@app.before_request
def record_heartbeat():
    global last_client_ping
    last_client_ping = time.time()


def client_watchdog_loop():
    """Watchdog that stops mouse control and floating HUD when website is closed."""
    global last_client_ping
    while True:
        time.sleep(3.0)
        if settings.mouse_control_enabled and mouse_ctrl:
            # If no heartbeat received from browser for > 30s (browser window closed/killed)
            if time.time() - last_client_ping > 30.0:
                settings.mouse_control_enabled = False
                mouse_ctrl.release_all()
                close_floating_hud()
                log_event("Browser window closed: Mouse control automatically turned off.")


# Start watchdog in background only when running locally on desktop
if not IS_CLOUD_DEPLOYMENT:
    threading.Thread(target=client_watchdog_loop, daemon=True).start()


@app.route("/api/status")
def api_status():
    """Return JSON system telemetry."""
    return jsonify({
        "camera_online": is_camera_active,
        "mouse_enabled": settings.mouse_control_enabled,
        "is_paused": settings.is_paused,
        "gesture": current_gesture,
        "has_hand": has_hand_detected,
        "fps": live_fps,
        "latency": live_latency,
        "auto_float_camera": settings.auto_float_camera,
        "show_cursor_dot": getattr(settings, "show_cursor_dot", True),
        "floating_hud_active": (floating_hud_proc is not None and floating_hud_proc.poll() is None),
        "is_cloud": IS_CLOUD_DEPLOYMENT,
        "logs": list(event_logs),
    })


@app.route("/api/toggle_camera", methods=["POST"])
def api_toggle_camera():
    global is_camera_active, camera_thread, latest_encoded_jpeg

    if IS_CLOUD_DEPLOYMENT:
        log_event("NOTICE: Hardware camera capture requires local desktop execution.")
        return jsonify({
            "success": False,
            "error": "Webcam streaming requires local desktop execution. Run AIRMOUSE AI locally via start_web.bat or python web_server.py.",
            "camera_online": False,
        }), 200

    init_desktop_components()
    if tracker is None:
        log_event("ERROR: Hand tracker not available.")
        return jsonify({"success": False, "error": "Camera tracker not available."}), 500

    if not is_camera_active:
        success = tracker.start_camera()
        if not success:
            log_event("ERROR: Failed to open webcam.")
            return jsonify({"success": False, "error": "Camera open failed"}), 500

        is_camera_active = True
        camera_thread = threading.Thread(target=camera_worker_loop, daemon=True)
        camera_thread.start()
        log_event("Webcam stream started via Web Dashboard.")
        return jsonify({"success": True, "camera_online": True})
    else:
        is_camera_active = False
        if tracker:
            tracker.stop_camera()
        if mouse_ctrl:
            mouse_ctrl.release_all()
        close_floating_hud()
        latest_encoded_jpeg = generate_empty_placeholder_jpeg()
        log_event("Webcam stream stopped via Web Dashboard.")
        return jsonify({"success": True, "camera_online": False})


@app.route("/api/toggle_mouse", methods=["POST"])
def api_toggle_mouse():
    global is_camera_active, camera_thread

    if IS_CLOUD_DEPLOYMENT:
        log_event("NOTICE: Virtual mouse control operates on your local desktop.")
        return jsonify({
            "success": False,
            "error": "Virtual mouse control operates on your local desktop computer. Run AIRMOUSE AI locally via start_web.bat or python web_server.py.",
            "mouse_enabled": False,
            "camera_online": False,
        }), 200

    init_desktop_components()

    # Auto-start camera if not already active
    if not is_camera_active and tracker:
        success = tracker.start_camera()
        if success:
            is_camera_active = True
            camera_thread = threading.Thread(target=camera_worker_loop, daemon=True)
            camera_thread.start()
            log_event("Camera auto-started for mouse control.")

    settings.mouse_control_enabled = not settings.mouse_control_enabled
    if settings.mouse_control_enabled:
        if mouse_ctrl:
            mouse_ctrl.failsafe_triggered = False
            mouse_ctrl.has_previous_position = False
        settings.emergency_stop = False
        log_event("ACTIVE: Mouse control ENABLED across Windows desktop.")
        if settings.auto_float_camera:
            open_floating_hud()
    else:
        if mouse_ctrl:
            mouse_ctrl.release_all()
        log_event("STANDBY: Mouse control DISABLED.")
        close_floating_hud()

    return jsonify({
        "success": True,
        "mouse_enabled": settings.mouse_control_enabled,
        "camera_online": is_camera_active,
    })


@app.route("/api/toggle_pause", methods=["POST"])
def api_toggle_pause():
    settings.is_paused = not settings.is_paused
    if settings.is_paused:
        if mouse_ctrl:
            mouse_ctrl.release_all()
        log_event("System PAUSED via Web Dashboard.")
    else:
        log_event("System RESUMED via Web Dashboard.")
    return jsonify({"success": True, "is_paused": settings.is_paused})


@app.route("/api/emergency_stop", methods=["POST"])
def api_emergency_stop():
    settings.emergency_stop = True
    settings.mouse_control_enabled = False
    if mouse_ctrl:
        mouse_ctrl.release_all()
    close_floating_hud()
    log_event("EMERGENCY STOP TRIGGERED: Mouse control immediately disabled.")
    return jsonify({"success": True, "mouse_enabled": False})


@app.route("/api/settings", methods=["POST"])
def api_settings():
    data = request.get_json() or {}
    settings.update_from_dict(data)
    log_event("System calibration updated via Web Dashboard.")
    return jsonify({"success": True, "settings": settings.to_dict()})


@app.route("/api/current_frame.jpg")
def api_current_frame():
    """Single JPEG snapshot with CORS enabled."""
    with frame_lock:
        data = latest_encoded_jpeg
    if data is None:
        data = generate_empty_placeholder_jpeg()
    return Response(
        data,
        mimetype="image/jpeg",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@app.route("/api/open_floating_window", methods=["POST"])
def api_open_floating_window():
    if IS_CLOUD_DEPLOYMENT:
        return jsonify({"success": False, "error": "Always-On-Top floating window is a desktop feature."}), 200
    success = open_floating_hud()
    return jsonify({"success": success})


@app.route("/api/close_floating_window", methods=["POST"])
def api_close_floating_window():
    close_floating_hud()
    return jsonify({"success": True})


@app.route("/api/client_exit", methods=["POST"])
def api_client_exit():
    """Invoked when user closes the website window: turns off mouse & closes floating camera."""
    settings.mouse_control_enabled = False
    if mouse_ctrl:
        mouse_ctrl.release_all()
    close_floating_hud()
    log_event("Website window closed: Mouse control and floating camera turned off.")
    return jsonify({"success": True})


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    port = 5000
    print("================================================================")
    print(f"[*] AIRMOUSE AI Web Dashboard is running on http://localhost:{port}")
    print("================================================================")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
