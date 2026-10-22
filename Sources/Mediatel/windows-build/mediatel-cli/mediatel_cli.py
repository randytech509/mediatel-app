#!/usr/bin/env python3
"""
RANDROID — Mediatel CLI
-----------------------
Windows command-line interface for Android device management via ADB.
Features: device listing, file browsing, push/pull, rename, delete, mkdir,
          firmware flash (Heimdall, Odin4), and interactive shell.

RandyTech Solutions © 2024-2026
"""

import argparse
import os
import shutil
import sys
import textwrap
from pathlib import Path

# Add parent directory to sys.path to load mediatel_core
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from mediatel_core import (
    find_adb,
    find_tool,
    human_size,
    parse_devices,
    parse_ls,
    run_adb,
    run_command,
    sh_quote,
)


# ─── Device management ───────────────────────────────────────────────────────

def list_devices() -> list[dict]:
    """Return list of connected ADB devices."""
    code, out, _ = run_adb("devices", "-l")
    if code != 0:
        return []
    return parse_devices(out)


def pick_device(devices: list[dict], serial: str | None = None) -> dict | None:
    """Select a device — by serial if given, or interactively if multiple."""
    if not devices:
        print("❌ No devices detected. Make sure USB debugging is enabled.")
        return None
    if serial:
        for d in devices:
            if d["serial"] == serial:
                return d
        print(f"❌ Device '{serial}' not found.")
        return None
    if len(devices) == 1:
        return devices[0]
    print("\nMultiple devices connected:")
    for i, d in enumerate(devices, 1):
        print(f"  [{i}] {d['model']} ({d['serial']}) — {d['state']}")
    while True:
        try:
            choice = int(input("Select device number: "))
            if 1 <= choice <= len(devices):
                return devices[choice - 1]
        except (ValueError, EOFError):
            pass
        print("Invalid selection.")


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_devices(args) -> int:
    """List connected devices."""
    devices = list_devices()
    if not devices:
        print("No devices detected.")
        return 0
    print(f"\n{'Serial':<25} {'Model':<20} {'State':<15}")
    print("─" * 60)
    for d in devices:
        print(f"{d['serial']:<25} {d['model']:<20} {d['state']:<15}")
    print(f"\n{len(devices)} device(s) connected.")
    return 0


def cmd_ls(args) -> int:
    """List files on device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return 1
    path = args.path or "/sdcard"
    if not path.endswith("/"):
        path += "/"
    quoted_path = sh_quote(path)
    code, out, err = run_adb("shell", f"ls -AlL --color=never {quoted_path} 2>/dev/null", serial=dev["serial"])
    if code != 0:
        print(f"❌ Failed to list {path}: {err.strip()}")
        return code
    entries = parse_ls(out)
    if not entries:
        print(f"📂 {path} is empty.")
        return 0
    print(f"\n📂 {path}")
    print(f"{'Type':<6} {'Size':>10}  {'Date':<16}  {'Name'}")
    print("─" * 70)
    for e in entries:
        t = "📁" if e["is_dir"] else "📄"
        s = "—" if e["is_dir"] else human_size(e["size"])
        print(f" {t}    {s:>10}  {e['date']:<16}  {e['name']}")
    print(f"\n{len(entries)} item(s).")
    return 0


def cmd_push(args) -> int:
    """Push file from PC to device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return 1
    local = args.local
    dest = args.dest or "/sdcard/"
    if not os.path.exists(local):
        print(f"❌ Local file not found: {local}")
        return 1
    basename = os.path.basename(local)
    size = os.path.getsize(local) if os.path.isfile(local) else 0
    size_label = human_size(size) if size else "directory"
    print(f"⬆️  Pushing {basename} ({size_label}) to {dest}...")
    code, out, err = run_adb("push", local, dest, serial=dev["serial"], timeout=600)
    if code == 0:
        print("✅ Successfully pushed to device.")
        return 0
    else:
        print(f"❌ Push failed: {err.strip()}")
        return code


def cmd_pull(args) -> int:
    """Pull file from device to PC."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return 1
    remote = args.remote
    local_dir = args.dest or "."
    basename = remote.rstrip("/").split("/")[-1]
    print(f"⬇️  Pulling {basename} to {local_dir}...")
    code, out, err = run_adb("pull", remote, local_dir, serial=dev["serial"], timeout=600)
    if code == 0:
        print(f"✅ Successfully pulled to {local_dir}.")
        return 0
    else:
        print(f"❌ Pull failed: {err.strip()}")
        return code


def cmd_delete(args) -> int:
    """Delete file/folder on device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return 1
    target = args.path
    if not args.yes:
        confirm = input(f"⚠️  Delete '{target}' on device? This is irreversible. (y/N): ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return 0
    quoted = sh_quote(target)
    code, out, err = run_adb("shell", f"rm -rf {quoted}", serial=dev["serial"])
    if code == 0:
        print("✅ Deleted.")
        return 0
    else:
        print(f"❌ Failed to delete: {err.strip()}")
        return code


def cmd_rename(args) -> int:
    """Rename file/folder on device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return 1
    src = args.path
    parts = src.rstrip("/").split("/")
    dst_dir = "/".join(parts[:-1]) if len(parts) > 1 else ""
    dst = f"{dst_dir}/{args.new_name}" if dst_dir else args.new_name
    quoted_src = sh_quote(src)
    quoted_dst = sh_quote(dst)
    code, out, err = run_adb("shell", f"mv {quoted_src} {quoted_dst}", serial=dev["serial"])
    if code == 0:
        print(f"✅ Renamed to {args.new_name}.")
        return 0
    else:
        print(f"❌ Failed to rename: {err.strip()}")
        return code


def cmd_mkdir(args) -> int:
    """Create directory on device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return 1
    quoted = sh_quote(args.path)
    code, out, err = run_adb("shell", f"mkdir -p {quoted}", serial=dev["serial"])
    if code == 0:
        print(f"✅ Directory created: {args.path}")
        return 0
    else:
        print(f"❌ Failed to create directory: {err.strip()}")
        return code


def cmd_shell(args) -> int:
    """Run a shell command on device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return 1
    command = " ".join(args.command)
    code, out, err = run_adb("shell", command, serial=dev["serial"])
    if out:
        print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    return code


def cmd_reboot(args) -> int:
    """Reboot device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return 1
    mode = args.mode or ""
    target = f" to {mode}" if mode else ""
    print(f"🔄 Rebooting device{target}...")
    adb_args = ["reboot"]
    if mode:
        adb_args.append(mode)
    code, out, err = run_adb(*adb_args, serial=dev["serial"])
    if code == 0:
        print("✅ Reboot command sent.")
        return 0
    else:
        print(f"❌ Reboot failed: {err.strip()}")
        return code


def cmd_flash(args) -> int:
    """Flash firmware using Heimdall or Odin4."""
    tool = args.tool.lower()
    if tool == "odin4":
        return flash_odin(args)
    elif tool == "heimdall":
        return flash_heimdall(args)
    else:
        print(f"❌ Unknown flash tool: {tool}. Use 'odin4' or 'heimdall'.")
        return 1


def flash_odin(args) -> int:
    """Flash Samsung firmware with Odin4."""
    odin = find_tool("odin4") or find_tool("odin")
    if not odin:
        print("❌ odin4 binary not found. Place odin4.exe in PATH or application directory.")
        return 1
    cmd = [odin]
    if args.bl:
        cmd += ["-b", args.bl]
    if args.ap:
        cmd += ["-a", args.ap]
    if args.cp:
        cmd += ["-c", args.cp]
    if args.csc:
        cmd += ["-s", args.csc]
    if all(not x for x in [args.bl, args.ap, args.cp, args.csc]):
        print("❌ No firmware files specified. Use --bl, --ap, --cp, --csc.")
        return 1
    print("⚡ Flashing with Odin4...")
    print("⚠️  A wrong firmware can brick the device — make sure the model matches exactly!")
    if not args.yes:
        confirm = input("Proceed? (y/N): ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return 0
    code, out, err = run_command(cmd, timeout=1200)
    print(out)
    if err:
        print(err, file=sys.stderr)
    if code == 0:
        print("✅ Flash complete.")
        return 0
    else:
        print(f"❌ Flash failed (exit code {code}).")
        return code


def flash_heimdall(args) -> int:
    """Flash partitions with Heimdall."""
    heimdall = find_tool("heimdall")
    if not heimdall:
        print("❌ heimdall binary not found. Place heimdall.exe in PATH or application directory.")
        return 1
    if not args.partitions:
        print("❌ No partitions specified. Use --partition PART:file.img format.")
        return 1
    cmd = [heimdall, "flash", "--no-reboot"]
    for p in args.partitions:
        if ":" not in p:
            print(f"❌ Invalid partition format: '{p}'. Use PARTITION:file.img")
            return 1
        name, filepath = p.split(":", 1)
        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            return 1
        cmd += [f"--{name.upper()}", filepath]

    print("⚡ Flashing with Heimdall...")
    if not args.yes:
        confirm = input("Proceed? (y/N): ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return 0
    code, out, err = run_command(cmd, timeout=1200)
    print(out)
    if err:
        print(err, file=sys.stderr)
    if code == 0:
        print("✅ Flash complete.")
        return 0
    else:
        print(f"❌ Flash failed (exit code {code}).")
        return code


def cmd_detect(args) -> int:
    """Detect device in Download mode."""
    heimdall = find_tool("heimdall")
    odin = find_tool("odin4") or find_tool("odin")
    found = False
    if heimdall:
        code, out, err = run_command([heimdall, "detect"])
        if code == 0:
            print("✅ Heimdall: device detected in Download mode.")
            found = True
        else:
            print("ℹ️  Heimdall: no device in Download mode.")
    if odin:
        code, out, err = run_command([odin, "-l"])
        if code == 0 and out.strip():
            print("✅ Odin4: device detected in Download mode.")
            found = True
        else:
            print("ℹ️  Odin4: no device in Download mode.")
    if not heimdall and not odin:
        print("❌ Neither heimdall nor odin4 found in PATH.")
        return 1
    elif not found:
        print("❌ No device detected in Download mode.")
        return 1
    return 0


def cmd_interactive(args) -> int:
    """Start an interactive file browser session."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return 1
    if dev["state"] != "device":
        print(f"❌ Device state is '{dev['state']}'. Requires 'device' state for file browsing.")
        return 1
    serial = dev["serial"]
    path = "/sdcard"

    print(f"\n🔌 Connected to {dev['model']} ({serial})")
    print("Type 'help' for commands.\n")

    while True:
        try:
            cmd_input = input(f"mediatel:{path}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not cmd_input:
            continue
        parts = cmd_input.split(None, 1)
        c = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if c in ("exit", "quit", "q"):
            print("Bye!")
            break
        elif c == "help":
            print(textwrap.dedent("""
                Commands:
                  ls              — List current directory
                  cd <dir>        — Change directory
                  cd ..           — Go up one level
                  push <local>    — Copy file from PC to current directory
                  pull <name>     — Copy file to current working directory on PC
                  mkdir <name>    — Create new directory
                  rm <name>       — Delete file/directory
                  rename <old> <new> — Rename file
                  pwd             — Print current path
                  devices         — List connected devices
                  shell <cmd>     — Run arbitrary shell command
                  exit / quit     — Exit interactive mode
            """))
        elif c == "ls":
            p = path if path.endswith("/") else path + "/"
            quoted = sh_quote(p)
            code, out, err = run_adb("shell", f"ls -AlL --color=never {quoted} 2>/dev/null", serial=serial)
            entries = parse_ls(out) if code == 0 else []
            if not entries:
                print("  (empty)")
            for e in entries:
                t = "📁" if e["is_dir"] else "📄"
                s = "" if e["is_dir"] else f"  {human_size(e['size']):>10}"
                print(f"  {t}  {e['name']}{s}")
        elif c == "cd":
            if not arg:
                path = "/sdcard"
            elif arg == "..":
                if path != "/":
                    trimmed = path.rstrip("/")
                    idx = trimmed.rfind("/")
                    path = trimmed[:idx] if idx > 0 else "/"
            else:
                new_path = arg if arg.startswith("/") else f"{path.rstrip('/')}/{arg}"
                quoted = sh_quote(new_path)
                code, _, _ = run_adb("shell", f"test -d {quoted} && echo ok", serial=serial)
                if code == 0:
                    path = new_path
                else:
                    print(f"  ❌ Not a directory: {new_path}")
        elif c == "push":
            if not arg:
                print("  Usage: push <local_file_path>")
            elif not os.path.exists(arg):
                print(f"  ❌ File not found: {arg}")
            else:
                dest = path if path.endswith("/") else path + "/"
                print(f"  Pushing {os.path.basename(arg)}...")
                code, out, err = run_adb("push", arg, dest, serial=serial, timeout=600)
                print(f"  {'✅ Done.' if code == 0 else '❌ Failed: ' + err.strip()}")
        elif c == "pull":
            if not arg:
                print("  Usage: pull <filename>")
            else:
                remote = f"{path.rstrip('/')}/{arg}"
                print(f"  Pulling {arg}...")
                code, out, err = run_adb("pull", remote, ".", serial=serial, timeout=600)
                print(f"  {'✅ Done.' if code == 0 else '❌ Failed: ' + err.strip()}")
        elif c == "mkdir":
            if not arg:
                print("  Usage: mkdir <dirname>")
            else:
                target = f"{path.rstrip('/')}/{arg}"
                quoted = sh_quote(target)
                code, _, err = run_adb("shell", f"mkdir -p {quoted}", serial=serial)
                print(f"  {'✅ Created.' if code == 0 else '❌ Failed: ' + err.strip()}")
        elif c == "rm":
            if not arg:
                print("  Usage: rm <name>")
            else:
                target = f"{path.rstrip('/')}/{arg}"
                confirm = input(f"  ⚠️  Delete '{arg}'? (y/N): ")
                if confirm.lower() == "y":
                    quoted = sh_quote(target)
                    code, _, err = run_adb("shell", f"rm -rf {quoted}", serial=serial)
                    print(f"  {'✅ Deleted.' if code == 0 else '❌ Failed: ' + err.strip()}")
                else:
                    print("  Cancelled.")
        elif c == "rename":
            rp = arg.split(None, 1)
            if len(rp) < 2:
                print("  Usage: rename <old_name> <new_name>")
            else:
                src = f"{path.rstrip('/')}/{rp[0]}"
                dst = f"{path.rstrip('/')}/{rp[1]}"
                quoted_src = sh_quote(src)
                quoted_dst = sh_quote(dst)
                code, _, err = run_adb("shell", f"mv {quoted_src} {quoted_dst}", serial=serial)
                print(f"  {'✅ Renamed.' if code == 0 else '❌ Failed: ' + err.strip()}")
        elif c == "pwd":
            print(f"  {path}")
        elif c == "devices":
            for d in list_devices():
                print(f"  {d['serial']}  {d['model']}  ({d['state']})")
        elif c == "shell":
            if not arg:
                print("  Usage: shell <command>")
            else:
                code, out, err = run_adb("shell", arg, serial=serial)
                if out:
                    print(out, end="")
                if err:
                    print(err, end="")
        else:
            print(f"  Unknown command: {c}. Type 'help' for commands.")
    return 0


# ─── Argument Parser ─────────────────────────────────────────────────────────

BANNER = r"""
  ╔══════════════════════════════════════════════════╗
  ║  ██████   █████  ███    ██ ██████  ██████   ██  ║
  ║  ██   ██ ██   ██ ████   ██ ██   ██ ██   ██ ██   ║
  ║  ██████  ███████ ██ ██  ██ ██   ██ ██████  ██   ║
  ║  ██   ██ ██   ██ ██  ██ ██ ██   ██ ██   ██ ██   ║
  ║  ██   ██ ██   ██ ██   ████ ██████  ██   ██ ██   ║
  ║                                                  ║
  ║        MEDIATEL CLI — RandyTech Solutions         ║
  ╚══════════════════════════════════════════════════╝
"""


def get_parser() -> argparse.ArgumentParser:
    """Build and return argument parser."""
    parser = argparse.ArgumentParser(
        prog="mediatel",
        description="RANDROID — Mediatel CLI: Android device management via ADB",
        epilog="RandyTech Solutions © 2024-2026",
    )
    parser.add_argument("-s", "--serial", help="Target device serial number")
    parser.add_argument("--version", action="version", version="Mediatel CLI 1.0.0")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # devices
    sub.add_parser("devices", help="List connected devices")

    # ls
    p_ls = sub.add_parser("ls", help="List files on device")
    p_ls.add_argument("path", nargs="?", default="/sdcard", help="Path to list (default: /sdcard)")

    # push
    p_push = sub.add_parser("push", help="Push file to device")
    p_push.add_argument("local", help="Local file/folder path")
    p_push.add_argument("dest", nargs="?", default="/sdcard/", help="Destination on device")

    # pull
    p_pull = sub.add_parser("pull", help="Pull file from device")
    p_pull.add_argument("remote", help="Remote file/folder path")
    p_pull.add_argument("dest", nargs="?", default=".", help="Local destination directory")

    # delete
    p_del = sub.add_parser("delete", help="Delete file/folder on device")
    p_del.add_argument("path", help="Path to delete")
    p_del.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")

    # rename
    p_ren = sub.add_parser("rename", help="Rename file/folder on device")
    p_ren.add_argument("path", help="Full path of file to rename")
    p_ren.add_argument("new_name", help="New filename")

    # mkdir
    p_mk = sub.add_parser("mkdir", help="Create directory on device")
    p_mk.add_argument("path", help="Directory path to create")

    # shell
    p_sh = sub.add_parser("shell", help="Run shell command on device")
    p_sh.add_argument("command", nargs="+", help="Command to run")

    # reboot
    p_rb = sub.add_parser("reboot", help="Reboot device")
    p_rb.add_argument("mode", nargs="?", choices=["bootloader", "recovery", "download"],
                       help="Reboot mode (default: normal)")

    # flash
    p_fl = sub.add_parser("flash", help="Flash firmware")
    p_fl.add_argument("tool", choices=["odin4", "heimdall"], help="Flash tool to use")
    p_fl.add_argument("--bl", help="Odin4: bootloader archive")
    p_fl.add_argument("--ap", help="Odin4: system archive")
    p_fl.add_argument("--cp", help="Odin4: modem archive")
    p_fl.add_argument("--csc", help="Odin4: CSC/region archive")
    p_fl.add_argument("--partition", dest="partitions", action="append",
                       help="Heimdall: PARTITION:file.img (repeatable)")
    p_fl.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")

    # detect
    sub.add_parser("detect", help="Detect device in Download mode")

    # interactive
    sub.add_parser("interactive", aliases=["i"], help="Interactive file browser")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = get_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        print(BANNER)
        parser.print_help()
        return 0

    dispatch = {
        "devices": cmd_devices,
        "ls": cmd_ls,
        "push": cmd_push,
        "pull": cmd_pull,
        "delete": cmd_delete,
        "rename": cmd_rename,
        "mkdir": cmd_mkdir,
        "shell": cmd_shell,
        "reboot": cmd_reboot,
        "flash": cmd_flash,
        "detect": cmd_detect,
        "interactive": cmd_interactive,
        "i": cmd_interactive,
    }

    handler = dispatch.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
