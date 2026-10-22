"""
Unit tests for mediatel_core
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mediatel_core import (
    find_adb,
    find_tool,
    human_size,
    parse_devices,
    parse_ls,
    sh_quote,
)


class TestMediatelCore(unittest.TestCase):

    def test_sh_quote(self):
        self.assertEqual(sh_quote("test"), "'test'")
        self.assertEqual(sh_quote("/sdcard/My Folder"), "'/sdcard/My Folder'")
        self.assertEqual(sh_quote("file'name.txt"), "'file'\\''name.txt'")
        self.assertEqual(sh_quote("$VAR && `cmd`"), "'$VAR && `cmd`'")
        self.assertEqual(sh_quote(""), "''")

    def test_human_size(self):
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(-5), "0 B")
        self.assertEqual(human_size(500), "500 B")
        self.assertEqual(human_size(1023), "1023 B")
        self.assertEqual(human_size(1024), "1.0 KB")
        self.assertEqual(human_size(1536), "1.5 KB")
        self.assertEqual(human_size(1048576), "1.0 MB")
        self.assertEqual(human_size(1073741824), "1.0 GB")
        self.assertEqual(human_size(1099511627776), "1.0 TB")

    def test_parse_devices(self):
        # Empty input
        self.assertEqual(parse_devices(""), [])

        # Header only
        self.assertEqual(parse_devices("List of devices attached\n"), [])

        # Typical device output
        raw = """List of devices attached
RF8M10XYZAB            device product:starqltexx model:SM_G960F device:starqlte transport_id:1
192.168.1.50:5555      unauthorized transport_id:2
emulator-5554          offline transport_id:3
NO_MODEL_DEV           device product:generic device:generic_x86 transport_id:4
"""
        devs = parse_devices(raw)
        self.assertEqual(len(devs), 4)

        self.assertEqual(devs[0]["serial"], "RF8M10XYZAB")
        self.assertEqual(devs[0]["model"], "SM_G960F")
        self.assertEqual(devs[0]["state"], "device")
        self.assertEqual(devs[0]["transport_id"], "1")

        self.assertEqual(devs[1]["serial"], "192.168.1.50:5555")
        self.assertEqual(devs[1]["state"], "unauthorized")
        self.assertEqual(devs[1]["model"], "?")

        self.assertEqual(devs[2]["serial"], "emulator-5554")
        self.assertEqual(devs[2]["state"], "offline")

        # Fallback to device name when model tag is missing
        self.assertEqual(devs[3]["serial"], "NO_MODEL_DEV")
        self.assertEqual(devs[3]["model"], "generic_x86")

    def test_parse_ls_toybox(self):
        raw = """total 80
drwxrwx--x  4 root sdcard_rw     4096 2024-05-10 09:15 DCIM
drwxrwx--x  3 root sdcard_rw     4096 2024-01-01 12:00 Download
-rw-rw----  1 root sdcard_rw    12345 2023-08-15 14:30 my document.pdf
-rw-rw----  1 root sdcard_rw        0 2023-08-15 14:31 empty.txt
lrwxrwxrwx  1 root root            11 2023-08-15 14:30 sdcard -> /data/media/0
"""
        entries = parse_ls(raw)
        self.assertEqual(len(entries), 5)

        # Dirs and symlinks sorted first
        self.assertTrue(entries[0]["is_dir"])
        self.assertEqual(entries[0]["name"], "DCIM")
        self.assertEqual(entries[0]["size"], 0)

        self.assertTrue(entries[1]["is_dir"])
        self.assertEqual(entries[1]["name"], "Download")

        self.assertTrue(entries[2]["is_dir"])
        self.assertEqual(entries[2]["name"], "sdcard")  # symlink target stripped
        self.assertEqual(entries[2]["size"], 0)

        # Files sorted next
        self.assertFalse(entries[3]["is_dir"])
        self.assertEqual(entries[3]["name"], "empty.txt")
        self.assertEqual(entries[3]["size"], 0)

        self.assertFalse(entries[4]["is_dir"])
        self.assertEqual(entries[4]["name"], "my document.pdf")
        self.assertEqual(entries[4]["size"], 12345)
        self.assertEqual(entries[4]["date"], "2023-08-15 14:30")

    def test_parse_ls_standard_unix(self):
        raw = """total 128
drwxr-xr-x 2 root root 4096 Jan  5 12:34 Photos
-rw-r--r-- 1 root root 8888 Aug 15 14:30 summer.jpg
-rw-r--r-- 1 root root 9999 Aug 15  2022 archive.zip
"""
        entries = parse_ls(raw)
        self.assertEqual(len(entries), 3)

        self.assertTrue(entries[0]["is_dir"])
        self.assertEqual(entries[0]["name"], "Photos")

        self.assertFalse(entries[1]["is_dir"])
        self.assertEqual(entries[1]["name"], "archive.zip")
        self.assertEqual(entries[1]["size"], 9999)
        self.assertEqual(entries[1]["date"], "Aug 15 2022")

        self.assertFalse(entries[2]["is_dir"])
        self.assertEqual(entries[2]["name"], "summer.jpg")
        self.assertEqual(entries[2]["size"], 8888)
        self.assertEqual(entries[2]["date"], "Aug 15 14:30")

    def test_parse_ls_complex_names(self):
        raw = """
-rw-rw---- 1 root sdcard_rw 100 2024-01-01 00:00 [2024] Song - Track 01 (feat. Artist).mp3
-rw-rw---- 1 root sdcard_rw 200 2024-01-01 00:00 File_With_Multiple_Spaces    And_Symbols#1!.dat
"""
        entries = parse_ls(raw)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["name"], "[2024] Song - Track 01 (feat. Artist).mp3")
        self.assertEqual(entries[1]["name"], "File_With_Multiple_Spaces    And_Symbols#1!.dat")


if __name__ == "__main__":
    unittest.main()
