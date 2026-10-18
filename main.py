"""
main.py - Entry point for AIRMOUSE AI
Futuristic Gesture-Controlled Computer System
"""

import sys
import argparse
import logging
from settings import AppSettings
from dashboard import AirMouseDashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AIRMOUSE")


def parse_arguments() -> AppSettings:
    """Parse command line options and construct AppSettings."""
    parser = argparse.ArgumentParser(
        description="AIRMOUSE AI — Futuristic Gesture-Controlled Computer System",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Webcam device index (default: 0)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=640,
        help="Capture frame width (default: 640)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=480,
        help="Capture frame height (default: 480)",
    )
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=1.6,
        help="Cursor sensitivity multiplier (default: 1.6)",
    )
    parser.add_argument(
        "--smoothing",
        type=float,
        default=0.55,
        help="Cursor smoothing factor (0.1 to 0.9, default: 0.55)",
    )

    args = parser.parse_args()

    settings = AppSettings(
        camera_index=args.camera,
        camera_width=args.width,
        camera_height=args.height,
        sensitivity=args.sensitivity,
        smoothing_factor=args.smoothing,
    )
    return settings


def main() -> None:
    """Initialize and run the AIRMOUSE AI application."""
    logger.info("Initializing AIRMOUSE AI...")
    try:
        settings = parse_arguments()
        app = AirMouseDashboard(settings)
        logger.info("Launching desktop dashboard interface...")
        app.mainloop()
        logger.info("AIRMOUSE AI session terminated gracefully.")
    except KeyboardInterrupt:
        logger.info("Execution interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error during runtime: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
