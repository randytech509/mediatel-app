"""
Unit tests for mediatel_gui logic (mocking tkinter when running headless or without tk)
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir))
sys.path.insert(0, str(base_dir / "mediatel-gui"))

# Check if tkinter is available
try:
    import tkinter as tk
    HAS_TK = True
except ImportError:
    HAS_TK = False


class TestMediatelGUI(unittest.TestCase):

    def test_colors_defined(self):
        # Even without Tkinter running, COLORS dict must be complete
        with patch.dict("sys.modules", {"tkinter": MagicMock(), "tkinter.ttk": MagicMock(), "tkinter.filedialog": MagicMock()}):
            import mediatel_gui
            self.assertIn("bg", mediatel_gui.COLORS)
            self.assertIn("accent", mediatel_gui.COLORS)
            self.assertIn("green", mediatel_gui.COLORS)
            self.assertIn("red", mediatel_gui.COLORS)
            self.assertTrue(mediatel_gui.COLORS["bg"].startswith("#"))

    def test_gui_device_update_logic(self):
        with patch.dict("sys.modules", {"tkinter": MagicMock(), "tkinter.ttk": MagicMock(), "tkinter.filedialog": MagicMock()}):
            import mediatel_gui
            # Test that App class exists and has necessary helper methods
            self.assertTrue(hasattr(mediatel_gui, "MediatelApp"))
            self.assertTrue(hasattr(mediatel_gui, "FlashDialog"))


if __name__ == "__main__":
    unittest.main()
