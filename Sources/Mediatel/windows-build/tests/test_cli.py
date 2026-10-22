"""
Unit tests for mediatel_cli commands and argument parsing
"""

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add paths
base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir))
sys.path.insert(0, str(base_dir / "mediatel-cli"))

from mediatel_cli import (
    cmd_delete,
    cmd_devices,
    cmd_ls,
    cmd_mkdir,
    cmd_reboot,
    cmd_rename,
    get_parser,
    main,
)


class TestMediatelCLI(unittest.TestCase):

    def test_parser_subcommands(self):
        parser = get_parser()

        # devices
        args = parser.parse_args(["devices"])
        self.assertEqual(args.command, "devices")

        # ls
        args = parser.parse_args(["ls", "/sdcard/Downloads"])
        self.assertEqual(args.command, "ls")
        self.assertEqual(args.path, "/sdcard/Downloads")

        # push
        args = parser.parse_args(["push", "my_file.txt", "/sdcard/"])
        self.assertEqual(args.command, "push")
        self.assertEqual(args.local, "my_file.txt")
        self.assertEqual(args.dest, "/sdcard/")

        # pull
        args = parser.parse_args(["pull", "/sdcard/my_file.txt", "C:/Users"])
        self.assertEqual(args.command, "pull")
        self.assertEqual(args.remote, "/sdcard/my_file.txt")
        self.assertEqual(args.dest, "C:/Users")

        # delete
        args = parser.parse_args(["delete", "/sdcard/old.txt", "-y"])
        self.assertEqual(args.command, "delete")
        self.assertEqual(args.path, "/sdcard/old.txt")
        self.assertTrue(args.yes)

        # rename
        args = parser.parse_args(["rename", "/sdcard/old.txt", "new.txt"])
        self.assertEqual(args.command, "rename")
        self.assertEqual(args.path, "/sdcard/old.txt")
        self.assertEqual(args.new_name, "new.txt")

        # mkdir
        args = parser.parse_args(["mkdir", "/sdcard/NewFolder"])
        self.assertEqual(args.command, "mkdir")
        self.assertEqual(args.path, "/sdcard/NewFolder")

        # reboot
        args = parser.parse_args(["reboot", "recovery"])
        self.assertEqual(args.command, "reboot")
        self.assertEqual(args.mode, "recovery")

        # flash odin4
        args = parser.parse_args(["flash", "odin4", "--bl", "BL.tar", "--ap", "AP.tar", "-y"])
        self.assertEqual(args.command, "flash")
        self.assertEqual(args.tool, "odin4")
        self.assertEqual(args.bl, "BL.tar")
        self.assertEqual(args.ap, "AP.tar")
        self.assertTrue(args.yes)

        # flash heimdall
        args = parser.parse_args(["flash", "heimdall", "--partition", "BOOT:boot.img", "--partition", "RECOVERY:rec.img"])
        self.assertEqual(args.command, "flash")
        self.assertEqual(args.tool, "heimdall")
        self.assertEqual(args.partitions, ["BOOT:boot.img", "RECOVERY:rec.img"])

        # target serial flag
        args = parser.parse_args(["-s", "SERIAL_TEST", "ls"])
        self.assertEqual(args.serial, "SERIAL_TEST")
        self.assertEqual(args.command, "ls")

    @patch("mediatel_cli.run_adb")
    def test_cmd_devices(self, mock_adb):
        mock_adb.return_value = (0, "List of devices attached\nRF8M10XYZAB device model:SM_G960F\n", "")
        parser = get_parser()
        args = parser.parse_args(["devices"])

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = cmd_devices(args)
            self.assertEqual(code, 0)
            output = mock_out.getvalue()
            self.assertIn("RF8M10XYZAB", output)
            self.assertIn("SM_G960F", output)
            self.assertIn("1 device(s) connected", output)

    @patch("mediatel_cli.list_devices")
    @patch("mediatel_cli.run_adb")
    def test_cmd_ls(self, mock_adb, mock_devices):
        mock_devices.return_value = [{"serial": "SER123", "model": "Galaxy", "state": "device"}]
        mock_adb.return_value = (0, "-rw-rw---- 1 root sdcard_rw 5000 2024-01-01 12:00 sample.txt\n", "")

        parser = get_parser()
        args = parser.parse_args(["ls", "/sdcard/test"])

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = cmd_ls(args)
            self.assertEqual(code, 0)
            output = mock_out.getvalue()
            self.assertIn("sample.txt", output)
            self.assertIn("4.9 KB", output)

    @patch("mediatel_cli.list_devices")
    @patch("mediatel_cli.run_adb")
    def test_cmd_mkdir(self, mock_adb, mock_devices):
        mock_devices.return_value = [{"serial": "SER123", "model": "Galaxy", "state": "device"}]
        mock_adb.return_value = (0, "", "")

        parser = get_parser()
        args = parser.parse_args(["mkdir", "/sdcard/NewDir"])

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = cmd_mkdir(args)
            self.assertEqual(code, 0)
            output = mock_out.getvalue()
            self.assertIn("Directory created", output)

        mock_adb.assert_called_with("shell", "mkdir -p '/sdcard/NewDir'", serial="SER123")

    @patch("mediatel_cli.list_devices")
    @patch("mediatel_cli.run_adb")
    def test_cmd_delete_yes(self, mock_adb, mock_devices):
        mock_devices.return_value = [{"serial": "SER123", "model": "Galaxy", "state": "device"}]
        mock_adb.return_value = (0, "", "")

        parser = get_parser()
        args = parser.parse_args(["delete", "/sdcard/junk.tmp", "-y"])

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = cmd_delete(args)
            self.assertEqual(code, 0)
            output = mock_out.getvalue()
            self.assertIn("Deleted", output)

        mock_adb.assert_called_with("shell", "rm -rf '/sdcard/junk.tmp'", serial="SER123")

    @patch("mediatel_cli.list_devices")
    @patch("mediatel_cli.run_adb")
    def test_cmd_rename(self, mock_adb, mock_devices):
        mock_devices.return_value = [{"serial": "SER123", "model": "Galaxy", "state": "device"}]
        mock_adb.return_value = (0, "", "")

        parser = get_parser()
        args = parser.parse_args(["rename", "/sdcard/old.txt", "renamed.txt"])

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = cmd_rename(args)
            self.assertEqual(code, 0)
            output = mock_out.getvalue()
            self.assertIn("Renamed to renamed.txt", output)

        mock_adb.assert_called_with("shell", "mv '/sdcard/old.txt' '/sdcard/renamed.txt'", serial="SER123")

    @patch("mediatel_cli.list_devices")
    @patch("mediatel_cli.run_adb")
    def test_cmd_reboot(self, mock_adb, mock_devices):
        mock_devices.return_value = [{"serial": "SER123", "model": "Galaxy", "state": "device"}]
        mock_adb.return_value = (0, "", "")

        parser = get_parser()
        args = parser.parse_args(["reboot", "download"])

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = cmd_reboot(args)
            self.assertEqual(code, 0)
            output = mock_out.getvalue()
            self.assertIn("Reboot command sent", output)

        mock_adb.assert_called_with("reboot", "download", serial="SER123")


if __name__ == "__main__":
    unittest.main()
