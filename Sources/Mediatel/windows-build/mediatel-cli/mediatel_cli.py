#!/usr/bin/env python3
"""
RANDROID — Mediatel CLI
-----------------------
Windows command-line interface for Android device management via ADB.
Features: device listing, file browsing, push/pull, rename, delete, mkdir,
          firmware flash (Heimdall, Odin4).

RandyTech Solutions © 2024-2026
"""

import argparse
import os
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path


# ─── Shell helpers ────────────────────────────────────────────────────────────

def find_adb() -> str:
    """Locate adb.exe on Windows, checking common SDK locations."""
    adb = shutil.which("adb")
    if adb:
        return adb
    # Common Windows Android SDK paths
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        Path(os.environ.get("USERPROFILE", "")) / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        Path("C:/Android/Sdk/platform-tools/adb.exe"),
        Path("C:/Program Files/Android/platform-tools/adb.exe"),
        Path("C:/platform-tools/adb.exe"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "adb"  # fallback – let OS try to find it


ADB = find_adb()


def run(args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """Run a command and return (code, stdout, stderr)."""
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"Not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"


def adb(*args, serial: str | None = None, timeout: int = 120) -> tuple[int, str, str]:
    """Run an ADB command, optionally targeting a specific device."""
    cmd = [ADB]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return run(cmd, timeout=timeout)


# ─── Device management ───────────────────────────────────────────────────────

def list_devices() -> list[dict]:
    """Return list of connected ADB devices."""
    code, out, _ = adb("devices", "-l")
    if code != 0:
        return []
    devices = []
    for line in out.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        state = parts[1]
        model = "?"
        for tok in parts:
            if tok.startswith("model:"):
                model = tok[6:]
        devices.append({"serial": serial, "model": model, "state": state})
    return devices


def pick_device(devices: list[dict], serial: str | None = None) -> dict | None:
    """Select a device — by serial if given, or interactively if multiple."""
    if not devices:
        print("❌ No devices detected. Make sure USB debugging is enabled.")
        return None
    if serial:
        for d in devices:
            if d["serial"] == serial:
                return d
        print(f"❌ Device {serial} not found.")
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


# ─── File browser helpers ────────────────────────────────────────────────────

def parse_ls(output: str) -> list[dict]:
    """Parse `ls -AlL` output into file entries."""
    entries = []
    for raw in output.split("\n"):
        line = raw.strip()
        if not line or line.startswith("total "):
            continue
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        perm, _, _, _, size_str, date_part, time_part, name = parts
        is_dir = perm.startswith("d")
        is_link = perm.startswith("l")
        if is_link and " -> " in name:
            name = name.split(" -> ")[0]
        size = 0 if (is_dir or is_link) else int(size_str or "0")
        entries.append({
            "name": name,
            "is_dir": is_dir or is_link,
            "size": size,
            "date": f"{date_part} {time_part}",
        })
    entries.sort(key=lambda e: (0 if e["is_dir"] else 1, e["name"].lower()))
    return entries


def human_size(n: int) -> str:
    """Human readable file size."""
    v = float(n)
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if v < 1024:
            return f"{int(v)}{u}" if u == "B" else f"{v:.1f}{u}"
        v /= 1024
    return f"{v:.1f}PB"


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_devices(args):
    """List connected devices."""
    devices = list_devices()
    if not devices:
        print("No devices detected.")
        return
    print(f"\n{'Serial':<25} {'Model':<20} {'State':<15}")
    print("─" * 60)
    for d in devices:
        print(f"{d['serial']:<25} {d['model']:<20} {d['state']:<15}")
    print(f"\n{len(devices)} device(s) connected.")


def cmd_ls(args):
    """List files on device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return
    path = args.path or "/sdcard"
    if not path.endswith("/"):
        path += "/"
    code, out, err = adb("shell", f"ls -AlL --color=never '{path}' 2>/dev/null", serial=dev["serial"])
    if code != 0:
        print(f"❌ Failed to list {path}: {err.strip()}")
        return
    entries = parse_ls(out)
    if not entries:
        print(f"📂 {path} is empty.")
        return
    print(f"\n📂 {path}")
    print(f"{'Type':<6} {'Size':>10}  {'Date':<16}  {'Name'}")
    print("─" * 70)
    for e in entries:
        t = "📁" if e["is_dir"] else "📄"
        s = "—" if e["is_dir"] else human_size(e["size"])
        print(f" {t}    {s:>10}  {e['date']:<16}  {e['name']}")
    print(f"\n{len(entries)} item(s).")


def cmd_push(args):
    """Push file from PC to device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return
    local = args.local
    dest = args.dest or "/sdcard/"
    if not os.path.exists(local):
        print(f"❌ Local file not found: {local}")
        return
    basename = os.path.basename(local)
    size = os.path.getsize(local) if os.path.isfile(local) else 0
    print(f"⬆️  Pushing {basename} ({human_size(size) if size else 'directory'}) to {dest}...")
    code, out, err = adb("push", local, dest, serial=dev["serial"], timeout=600)
    if code == 0:
        print(f"✅ Successfully pushed to device.")
    else:
        print(f"❌ Push failed: {err.strip()}")


def cmd_pull(args):
    """Pull file from device to PC."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return
    remote = args.remote
    local_dir = args.dest or "."
    basename = remote.rstrip("/").split("/")[-1]
    print(f"⬇️  Pulling {basename} to {local_dir}...")
    code, out, err = adb("pull", remote, local_dir, serial=dev["serial"], timeout=600)
    if code == 0:
        print(f"✅ Successfully pulled to {local_dir}.")
    else:
        print(f"❌ Pull failed: {err.strip()}")


def cmd_delete(args):
    """Delete file/folder on device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return
    target = args.path
    if not args.yes:
        confirm = input(f"⚠️  Delete '{target}' on device? This is irreversible. (y/N): ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return
    code, out, err = adb("shell", f"rm -rf '{target}'", serial=dev["serial"])
    if code == 0:
        print(f"✅ Deleted.")
    else:
        print(f"❌ Failed to delete: {err.strip()}")


def cmd_rename(args):
    """Rename file/folder on device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return
    src = args.path
    dst_dir = "/".join(src.rstrip("/").split("/")[:-1])
    dst = f"{dst_dir}/{args.new_name}"
    code, out, err = adb("shell", f"mv '{src}' '{dst}'", serial=dev["serial"])
    if code == 0:
        print(f"✅ Renamed to {args.new_name}.")
    else:
        print(f"❌ Failed to rename: {err.strip()}")


def cmd_mkdir(args):
    """Create directory on device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return
    code, out, err = adb("shell", f"mkdir -p '{args.path}'", serial=dev["serial"])
    if code == 0:
        print(f"✅ Directory created: {args.path}")
    else:
        print(f"❌ Failed to create directory: {err.strip()}")


def cmd_shell(args):
    """Run a shell command on device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return
    command = " ".join(args.command)
    code, out, err = adb("shell", command, serial=dev["serial"])
    if out:
        print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    sys.exit(code)


def cmd_reboot(args):
    """Reboot device."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return
    mode = args.mode or ""
    target = f" to {mode}" if mode else ""
    print(f"🔄 Rebooting device{target}...")
    adb_args = ["reboot"]
    if mode:
        adb_args.append(mode)
    code, out, err = adb(*adb_args, serial=dev["serial"])
    if code == 0:
        print("✅ Reboot command sent.")
    else:
        print(f"❌ Reboot failed: {err.strip()}")


def cmd_flash(args):
    """Flash firmware using Heimdall or Odin4."""
    devices = list_devices()

    tool = args.tool.lower()
    if tool == "odin4":
        flash_odin(args)
    elif tool == "heimdall":
        flash_heimdall(args)
    else:
        print(f"❌ Unknown flash tool: {tool}. Use 'odin4' or 'heimdall'.")


def flash_odin(args):
    """Flash Samsung firmware with Odin4."""
    odin = shutil.which("odin4")
    if not odin:
        print("❌ odin4 not found in PATH. Install it first.")
        return
    cmd = ["odin4"]
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
        return
    print("⚡ Flashing with Odin4...")
    print("⚠️  A wrong firmware can brick the device — make sure the model matches exactly!")
    if not args.yes:
        confirm = input("Proceed? (y/N): ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return
    code, out, err = run(cmd, timeout=1200)
    print(out)
    if err:
        print(err, file=sys.stderr)
    if code == 0:
        print("✅ Flash complete.")
    else:
        print(f"❌ Flash failed (exit code {code}).")


def flash_heimdall(args):
    """Flash partitions with Heimdall."""
    heimdall = shutil.which("heimdall")
    if not heimdall:
        print("❌ heimdall not found in PATH. Install it first.")
        return
    if not args.partitions:
        print("❌ No partitions specified. Use --partition PART:file.img format.")
        return
    cmd = ["heimdall", "flash", "--no-reboot"]
    for p in args.partitions:
        if ":" not in p:
            print(f"❌ Invalid partition format: {p}. Use PARTITION:file.img")
            return
        name, filepath = p.split(":", 1)
        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            return
        cmd += [f"--{name.upper()}", filepath]

    print("⚡ Flashing with Heimdall...")
    if not args.yes:
        confirm = input("Proceed? (y/N): ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return
    code, out, err = run(cmd, timeout=1200)
    print(out)
    if err:
        print(err, file=sys.stderr)
    if code == 0:
        print("✅ Flash complete.")
    else:
        print(f"❌ Flash failed (exit code {code}).")


def cmd_detect(args):
    """Detect device in Download mode."""
    heimdall = shutil.which("heimdall")
    odin = shutil.which("odin4")
    found = False
    if heimdall:
        code, out, err = run(["heimdall", "detect"])
        if code == 0:
            print("✅ Heimdall detected device in Download mode.")
            found = True
        else:
            print("ℹ️  Heimdall: no device in Download mode.")
    if odin:
        code, out, err = run(["odin4", "-l"])
        if code == 0 and out.strip():
            print("✅ Odin4 detected device in Download mode.")
            found = True
        else:
            print("ℹ️  Odin4: no device in Download mode.")
    if not heimdall and not odin:
        print("❌ Neither heimdall nor odin4 found in PATH.")
    elif not found:
        print("❌ No device detected in Download mode.")


def cmd_interactive(args):
    """Start an interactive file browser session."""
    devices = list_devices()
    dev = pick_device(devices, args.serial)
    if not dev:
        return
    if dev["state"] != "device":
        print(f"❌ Device is {dev['state']}. Need 'device' state for file browsing.")
        return
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
            code, out, err = adb("shell", f"ls -AlL --color=never '{p}' 2>/dev/null", serial=serial)
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
                # Check if directory exists
                code, _, _ = adb("shell", f"test -d '{new_path}' && echo ok", serial=serial)
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
                code, out, err = adb("push", arg, dest, serial=serial, timeout=600)
                print(f"  {'✅ Done.' if code == 0 else '❌ Failed: ' + err.strip()}")
        elif c == "pull":
            if not arg:
                print("  Usage: pull <filename>")
            else:
                remote = f"{path.rstrip('/')}/{arg}"
                print(f"  Pulling {arg}...")
                code, out, err = adb("pull", remote, ".", serial=serial, timeout=600)
                print(f"  {'✅ Done.' if code == 0 else '❌ Failed: ' + err.strip()}")
        elif c == "mkdir":
            if not arg:
                print("  Usage: mkdir <dirname>")
            else:
                target = f"{path.rstrip('/')}/{arg}"
                code, _, err = adb("shell", f"mkdir -p '{target}'", serial=serial)
                print(f"  {'✅ Created.' if code == 0 else '❌ Failed: ' + err.strip()}")
        elif c == "rm":
            if not arg:
                print("  Usage: rm <name>")
            else:
                target = f"{path.rstrip('/')}/{arg}"
                confirm = input(f"  ⚠️  Delete '{arg}'? (y/N): ")
                if confirm.lower() == "y":
                    code, _, err = adb("shell", f"rm -rf '{target}'", serial=serial)
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
                code, _, err = adb("shell", f"mv '{src}' '{dst}'", serial=serial)
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
                code, out, err = adb("shell", arg, serial=serial)
                if out:
                    print(out, end="")
                if err:
                    print(err, end="")
        else:
            print(f"  Unknown command: {c}. Type 'help' for commands.")


# ─── Main ────────────────────────────────────────────────────────────────────

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


def main():
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
    p_int = sub.add_parser("interactive", aliases=["i"], help="Interactive file browser")

    args = parser.parse_args()

    if args.command is None:
        print(BANNER)
        parser.print_help()
        return

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
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
