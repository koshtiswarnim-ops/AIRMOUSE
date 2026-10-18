# ⚡ AIRMOUSE AI — Futuristic Gesture-Controlled Computer System

**AIRMOUSE AI** is a touchless human-computer interaction (HCI) desktop system that turns any standard webcam into a high-precision, gesture-driven virtual mouse. Powered by computer vision, MediaPipe hand landmark tracking, and an interactive cyberpunk dashboard built in CustomTkinter.

---

## 🌟 Features

- **Real-Time 21-Landmark Tracking:** High-speed hand detection with dual-backend support (compatible with MediaPipe 1.x Tasks API and legacy `solutions.hands`).
- **Futuristic Cyber HUD:** Glowing neon hand skeleton, active interaction boundaries, distance meters, live FPS, and latency metrics directly rendered on the video feed.
- **Precision Cursor Control:** Jitter-free cursor movement using dynamic exponential smoothing and boundary mapping.
- **Accidental Click Prevention:** State-machine debounce, distance thresholds normalized by palm size, and cooldown timers prevent rapid phantom clicks.
- **Vertical Scrolling & Dragging:** Pinch thumb and middle finger to scroll naturally up/down; hold index pinch for drag-and-drop.
- **Safety First Architecture:**
  - Mouse control starts **disabled** by default.
  - Fail-safe trigger: Moving mouse to any screen corner immediately halts virtual actions (via PyAutoGUI fail-safe).
  - Dedicated **Emergency Stop** (`<Esc>` key and UI button).
  - Open Palm gesture pauses actions; Closed Fist freezes the cursor.
  - Automatic button release upon hand tracking loss or app exit.
  - 100% local processing — no camera footage is ever stored or transmitted.

---

## 🖐️ Gesture Control Matrix

| Gesture | Hand Posture | Action Performed |
| :--- | :--- | :--- |
| **Pointing** | Index extended, others curled | **Move cursor** smoothly across desktop |
| **Index Pinch** | Thumb tip + Index tip touching | **Left-Click** (single click per pinch) |
| **Pinch & Hold** | Keep thumb + index pinched > 0.4s | **Drag & Drop** (when enabled in settings) |
| **Middle Pinch** | Thumb tip + Middle tip touching | **Vertical Scroll** (move hand up/down) |
| **Open Palm** | All 5 fingers extended outward | **Pause Action** (safely suspend mouse control) |
| **Closed Fist** | All fingers folded into a fist | **Stop Cursor** (freeze position) |
| **Hand Lost** | Hand moves out of camera frame | **Safety Idle** (release any held buttons) |
| **Emergency Stop** | Press `<Esc>` key on keyboard | **Immediate Disable** of virtual mouse control |

---

## 🛠️ System Requirements

- **Operating System:** Windows 10 or Windows 11 (64-bit)
- **Python Version:** Python 3.11 (Recommended: 3.11.9)
- **Hardware:** Any standard USB or built-in webcam

---

## 🚀 Beginner Quickstart Guide

### 1. Open Terminal in the Project Directory

Open **PowerShell** or **Command Prompt** and navigate to the project directory:

```powershell
cd C:\Users\ASUS\.gemini\antigravity\scratch\AIRMOUSE-AI
```

### 2. Create and Activate a Virtual Environment

```powershell
# Create a virtual environment using Python 3.11
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

*(If PowerShell displays an execution policy error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` before activating).*

### 3. Install Dependencies

Install the verified packages from `requirements.txt`:

```powershell
pip install -r requirements.txt
```

### 4. Launch AIRMOUSE AI

You can run AIRMOUSE AI either as a **Localhost Web Dashboard** in your browser, or as a **Desktop Application**:

#### Option A: Localhost Web Dashboard (In Your Browser)
```powershell
python web_server.py
```
Then open your browser and navigate to:
👉 **[http://localhost:5000](http://localhost:5000)**

#### Option B: Native Desktop Window
```powershell
python main.py
```

---

## 🖥️ How to Use the Dashboard

1. **Start the Camera:**
   - Click the blue **START CAMERA** button.
   - The live optical feed will initialize with the futuristic cyan HUD overlay.
2. **Calibrate Gestures in Standby Mode:**
   - Extend your index finger and watch the reticle track your fingertip.
   - Practice pinching thumb + index (left-click) and thumb + middle (scroll).
   - Confirm the gesture name displays correctly on the telemetry bar.
3. **Engage Mouse Control:**
   - Click the green **ENABLE MOUSE** button.
   - Your index fingertip will now guide the real desktop cursor!
4. **Pause or Stop at Any Time:**
   - Show an **Open Palm** to temporarily pause mouse actions.
   - Click **PAUSE** on the dashboard.
   - Press the **`<Esc>`** key on your keyboard or slam the mouse cursor into any screen corner for an instant emergency stop.

---

## 🧪 Running Automated Tests

A comprehensive test suite is included to verify coordinate mapping, clamping, smoothing, and gesture classification without requiring camera access:

```powershell
pytest -v
```

All 10 unit tests should pass with green status:
- `tests/test_coordinates.py`: Tests screen coordinate normalization, margins, smoothing, and button release.
- `tests/test_gestures.py`: Tests gesture classification, single-click debounce, and scrolling.

---

## ❓ Troubleshooting & FAQs

### Q1: The camera fails to open ("Failed to open webcam index 0").
- Make sure no other application (Zoom, Teams, Skype, Windows Camera app) is actively using the webcam.
- If you have an external USB webcam, try changing `--camera 1`.
- Verify Windows Camera Privacy Settings: **Start > Settings > Privacy & Security > Camera** and ensure **"Let desktop apps access your camera"** is toggled **ON**.

### Q2: Cursor feels jittery or too sensitive.
- Adjust the **Cursor Smoothing** slider on the dashboard upward (e.g. `0.65` - `0.75`).
- Adjust the **Sensitivity** slider to `1.2x` - `1.4x` for finer control.

### Q3: Clicks are triggering too easily or not registering.
- Adjust the **Pinch Threshold** slider on the dashboard:
  - If clicks trigger prematurely, decrease the threshold (e.g. `0.045`).
  - If you have to squeeze too hard, increase the threshold (e.g. `0.065`).

### Q4: Emergency fail-safe triggered.
- If the cursor hits the extreme top-left (0,0) corner of your monitor, PyAutoGUI triggers its built-in safety fail-safe to prevent runaway mouse behavior.
- Simply click **ENABLE MOUSE** again on the dashboard to re-engage when ready.

---

## 📂 Project Architecture

```
AIRMOUSE-AI/
├── main.py                 # Application entry point and argument parsing
├── dashboard.py            # Futuristic CustomTkinter user interface & thread loop
├── hand_tracker.py         # OpenCV video stream, MediaPipe inference & HUD renderer
├── gesture_recognizer.py   # Finger state estimation, pinch distance & state machine
├── mouse_controller.py     # Virtual mouse actuator, EMA smoothing & safety failsafes
├── settings.py             # Configuration parameters and runtime toggles
├── requirements.txt        # Pinned compatible package versions
├── .gitignore              # Ignored cache and environment directories
├── README.md               # User manual and setup documentation
└── tests/
    ├── __init__.py
    ├── test_coordinates.py # Coordinate transformation & smoothing unit tests
    └── test_gestures.py    # Posture recognition & debounce unit tests
```

---

## 🔒 Security & Privacy Notice

AIRMOUSE AI runs **strictly on your local machine**. It contains no internet telemetry, does not upload camera feeds to external servers, and does not record or store video files on disk.
