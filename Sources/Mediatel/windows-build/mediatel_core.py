"""
RANDROID — Mediatel Core Utilities
Shared logic for CLI and GUI Windows ports.
RandyTech Solutions © 2024-2026
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# ─── Constants & Shell Helpers ───────────────────────────────────────────────

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"

TS_REGEX = re.compile(
    r'(?:'
    r'(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})'                    # ISO: YYYY-MM-DD HH:MM
    r'|'
    r'(' + MONTHS + r')\s+(\d{1,2})\s+(\d{1,2}:\d{2}|\d{4})'  # Trad: Month DD HH:MM|YYYY
    r'|'
    r'(\d{2}-\d{2})\s+(\d{1,2}:\d{2})'                         # Short: MM-DD HH:MM
    r')\s+(.+)$'
)


def find_tool(name: str) -> str | None:
    """Find a binary in PATH, next to executable, or standard Windows locations."""
    # Check standard PATH first
    p = shutil.which(name)
    if p:
        return p

    # Extensions to check on Windows
    exts = [".exe", ".bat", ".cmd", ""] if sys.platform == "win32" else [""]

    # Candidate directories
    app_dir = Path(__file__).resolve().parent
    candidates = [
        app_dir,
        app_dir / "tools",
        app_dir.parent / "tools",
        Path(sys.executable).parent if getattr(sys, "frozen", False) else app_dir,
    ]

    if sys.platform == "win32":
        local_app = Path(os.environ.get("LOCALAPPDATA", ""))
        user_prof = Path(os.environ.get("USERPROFILE", ""))
        prog_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        prog_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))

        candidates += [
            local_app / "Android" / "Sdk" / "platform-tools",
            user_prof / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools",
            Path("C:/Android/Sdk/platform-tools"),
            Path("C:/platform-tools"),
            prog_files / "Android" / "platform-tools",
            prog_files / "Heimdall",
            prog_files_x86 / "Heimdall",
            Path("C:/Heimdall"),
        ]

    for cand in candidates:
        for ext in exts:
            target = cand / f"{name}{ext}"
            if target.is_file():
                return str(target)

    return None


def find_adb() -> str:
    """Locate adb executable."""
    found = find_tool("adb")
    return found if found else "adb"


def sh_quote(s: str) -> str:
    """Safely quote a POSIX shell string."""
    return "'" + s.replace("'", "'\\''") + "'"


def run_command(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Run an external command, return (exit_code, stdout, stderr)."""
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout}s: {' '.join(args)}"
    except Exception as e:
        return 1, "", str(e)


def run_adb(*args, serial: str | None = None, adb_bin: str | None = None, timeout: int = 120) -> tuple[int, str, str]:
    """Run an ADB command, optionally targeting a serial."""
    cmd = [adb_bin or find_adb()]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return run_command(cmd, timeout=timeout)


# ─── Data Parsers ─────────────────────────────────────────────────────────────

def parse_devices(output: str) -> list[dict]:
    """
    Parse 'adb devices -l' output into structured device list.
    Handles device, unauthorized, offline, recovery, sideload, fastboot states.
    """
    devices = []
    lines = output.strip().splitlines()
    if not lines:
        return devices

    # Skip header line ("List of devices attached")
    start_idx = 1 if "attached" in lines[0] else 0
    for line in lines[start_idx:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        state = parts[1]
        model = "?"
        product = "?"
        device = "?"
        transport_id = ""

        for tok in parts[2:]:
            if tok.startswith("model:"):
                model = tok[6:]
            elif tok.startswith("product:"):
                product = tok[8:]
            elif tok.startswith("device:"):
                device = tok[7:]
            elif tok.startswith("transport_id:"):
                transport_id = tok[13:]

        # Friendly display name if model is not known
        if model == "?" and device != "?":
            model = device

        devices.append({
            "serial": serial,
            "model": model,
            "state": state,
            "product": product,
            "device": device,
            "transport_id": transport_id,
        })
    return devices


def parse_ls(output: str) -> list[dict]:
    """
    Parse 'ls -AlL' output into sorted file entries.
    Handles Toybox (Android), standard Unix, and legacy Toolbox formats.
    """
    entries = []
    for raw in output.splitlines():
        line = raw.strip().rstrip("\r")
        if not line or line.startswith("total "):
            continue

        # Must start with permission flags (d, l, -, c, b, p, s)
        if not re.match(r"^[bcdlps-][rwxstST-]{9,10}", line):
            continue

        m = TS_REGEX.search(line)
        if not m:
            continue

        prefix = line[:m.start()].strip()
        raw_name = m.group(m.lastindex)

        if m.group(1):
            date_str = f"{m.group(1)} {m.group(2)}"
        elif m.group(3):
            date_str = f"{m.group(3)} {m.group(4)} {m.group(5)}"
        else:
            date_str = f"{m.group(6)} {m.group(7)}"

        cols = prefix.split()
        perm = cols[0]
        is_dir = perm.startswith("d")
        is_link = perm.startswith("l")

        name = raw_name
        if is_link and " -> " in name:
            name = name.split(" -> ")[0]

        # Symlinks in Android are treated as directories so user can navigate into them
        # (e.g., /sdcard -> /storage/emulated/0)
        is_directory = is_dir or is_link

        size = 0
        if not is_directory and len(cols) > 1:
            for col in reversed(cols[1:]):
                clean = col.rstrip(",")
                if clean.isdigit():
                    size = int(clean)
                    break

        entries.append({
            "name": name,
            "is_dir": is_directory,
            "size": size,
            "date": date_str,
        })

    # Sort: directories first, then alphabetical case-insensitive
    entries.sort(key=lambda e: (0 if e["is_dir"] else 1, e["name"].lower()))
    return entries


def human_size(n: int) -> str:
    """Format bytes into human-readable string (B, KB, MB, GB, TB, PB)."""
    if n < 0:
        return "0 B"
    v = float(n)
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if v < 1024:
            return f"{int(v)} {u}" if u == "B" else f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} PB"
