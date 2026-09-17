"""Run with --demo for a camera-free sandbox or --smoke-test for a GUI startup check."""
import argparse
import logging
import tkinter as tk
from src.config import Config
from ui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser(description="Local Phone Attention Monitor")
    parser.add_argument("--demo", action="store_true", help="Synthetic observations, separate DB, no camera/email")
    parser.add_argument("--smoke-test", action="store_true", help="Open and automatically close the GUI")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    root = tk.Tk()
    app = MainWindow(root, Config.load(), demo=args.demo or args.smoke_test)
    if args.smoke_test:
        root.after(700, app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
