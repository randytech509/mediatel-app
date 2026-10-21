#!/usr/bin/env python3
"""
RANDROID — Mediatel GUI
-----------------------
Windows desktop application for Android device management via ADB.
Built with tkinter (ships with Python — no extra dependencies).

Features:
  • Device listing and selection
  • File browser with table view
  • Push/Pull files with progress bar
  • Rename, Delete, New Folder operations
  • Firmware flash (Heimdall / Odin4)
  • Context menus for all operations

RandyTech Solutions © 2024-2026
"""

import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path


# ─── Shell Helpers ────────────────────────────────────────────────────────────

def find_adb() -> str:
    """Locate adb.exe on Windows."""
    adb = shutil.which("adb")
    if adb:
        return adb
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
    return "adb"


ADB = find_adb()

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def run_cmd(args, timeout=120):
    """Run command, return (code, stdout, stderr)."""
    try:
        p = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"Not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"


def adb_cmd(*args, serial=None, timeout=120):
    """Run ADB command."""
    cmd = [ADB]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return run_cmd(cmd, timeout=timeout)


# ─── Data Helpers ─────────────────────────────────────────────────────────────

def parse_ls(output):
    """Parse ls -AlL output into list of dicts."""
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


def human_size(n):
    v = float(n)
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if v < 1024:
            return f"{int(v)} {u}" if u == "B" else f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} PB"


# ─── Color Theme ──────────────────────────────────────────────────────────────

COLORS = {
    "bg": "#1e1e2e",
    "bg_secondary": "#252538",
    "bg_sidebar": "#181828",
    "fg": "#cdd6f4",
    "fg_dim": "#6c7086",
    "accent": "#89b4fa",
    "accent_hover": "#74c7ec",
    "green": "#a6e3a1",
    "orange": "#fab387",
    "red": "#f38ba8",
    "surface": "#313244",
    "border": "#45475a",
    "selection": "#3a3a5c",
}


# ─── Main Application ────────────────────────────────────────────────────────

class MediatelApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RANDROID — Mediatel")
        self.geometry("1100x680")
        self.minsize(900, 560)
        self.configure(bg=COLORS["bg"])

        # State
        self.devices = []
        self.selected_serial = None
        self.current_path = "/sdcard"
        self.entries = []
        self.busy = False

        # Apply dark theme
        self._setup_styles()
        self._build_ui()
        self._refresh_devices()

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=COLORS["bg"], foreground=COLORS["fg"],
                         borderwidth=0, focusthickness=0)
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Sidebar.TFrame", background=COLORS["bg_sidebar"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["fg"])
        style.configure("Sidebar.TLabel", background=COLORS["bg_sidebar"], foreground=COLORS["fg"])
        style.configure("Dim.TLabel", background=COLORS["bg"], foreground=COLORS["fg_dim"])
        style.configure("SidebarDim.TLabel", background=COLORS["bg_sidebar"], foreground=COLORS["fg_dim"])
        style.configure("Accent.TLabel", background=COLORS["bg"], foreground=COLORS["accent"])
        style.configure("Green.TLabel", foreground=COLORS["green"], background=COLORS["bg_sidebar"])
        style.configure("Orange.TLabel", foreground=COLORS["orange"], background=COLORS["bg_sidebar"])
        style.configure("TButton", background=COLORS["surface"], foreground=COLORS["fg"],
                         padding=(12, 6), borderwidth=1, relief="flat")
        style.map("TButton",
                   background=[("active", COLORS["accent"]), ("pressed", COLORS["accent_hover"])],
                   foreground=[("active", COLORS["bg"]), ("pressed", COLORS["bg"])])
        style.configure("Accent.TButton", background=COLORS["accent"], foreground=COLORS["bg"])
        style.map("Accent.TButton",
                   background=[("active", COLORS["accent_hover"])],
                   foreground=[("active", COLORS["bg"])])
        style.configure("Danger.TButton", background=COLORS["red"], foreground=COLORS["bg"])
        style.configure("TSeparator", background=COLORS["border"])
        style.configure("Treeview", background=COLORS["bg_secondary"], foreground=COLORS["fg"],
                         fieldbackground=COLORS["bg_secondary"], borderwidth=0, rowheight=28)
        style.configure("Treeview.Heading", background=COLORS["surface"], foreground=COLORS["fg"],
                         borderwidth=1, relief="flat", padding=(8, 4))
        style.map("Treeview",
                   background=[("selected", COLORS["selection"])],
                   foreground=[("selected", COLORS["accent"])])
        style.configure("Horizontal.TProgressbar", background=COLORS["accent"],
                         troughcolor=COLORS["surface"], borderwidth=0, thickness=8)

    def _build_ui(self):
        # Main container
        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Sidebar ──
        sidebar = ttk.Frame(main, style="Sidebar.TFrame", width=260)
        main.add(sidebar, weight=0)

        # Sidebar header
        hdr = ttk.Frame(sidebar, style="Sidebar.TFrame")
        hdr.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(hdr, text="📱 Devices", font=("Segoe UI", 13, "bold"),
                  style="Sidebar.TLabel").pack(side=tk.LEFT)
        ttk.Button(hdr, text="⟳", width=3, command=self._refresh_devices).pack(side=tk.RIGHT)

        # Device listbox
        self.device_list = tk.Listbox(
            sidebar, bg=COLORS["bg_sidebar"], fg=COLORS["fg"],
            selectbackground=COLORS["selection"], selectforeground=COLORS["accent"],
            font=("Segoe UI", 10), borderwidth=0, highlightthickness=0,
            activestyle="none",
        )
        self.device_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.device_list.bind("<<ListboxSelect>>", self._on_device_select)

        self.device_hint = ttk.Label(
            sidebar, text="Connect an Android device\nwith USB debugging enabled.",
            style="SidebarDim.TLabel", font=("Segoe UI", 9), justify=tk.CENTER, wraplength=220
        )
        self.device_hint.pack(pady=20)

        # Brand
        ttk.Label(sidebar, text="RANDROID", font=("Segoe UI", 9, "bold"),
                  style="SidebarDim.TLabel").pack(side=tk.BOTTOM, pady=(0, 4))
        ttk.Label(sidebar, text="RandyTech Solutions",
                  font=("Segoe UI", 8), style="SidebarDim.TLabel").pack(side=tk.BOTTOM, pady=(0, 0))

        # ── Detail panel ──
        detail = ttk.Frame(main)
        main.add(detail, weight=1)

        # Toolbar
        toolbar = ttk.Frame(detail)
        toolbar.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Button(toolbar, text="⚡ Flash Firmware", command=self._open_flash_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)
        ttk.Button(toolbar, text="⬆ Push to Device", command=self._push_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="⬇ Pull to PC", command=self._pull_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📁 New Folder", command=self._new_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="⟳", width=3, command=self._list_path).pack(side=tk.LEFT, padx=2)

        # Progress bar (hidden by default)
        self.progress_frame = ttk.Frame(toolbar)
        self.progress_frame.pack(side=tk.RIGHT, padx=4)
        self.progress_bar = ttk.Progressbar(self.progress_frame, style="Horizontal.TProgressbar",
                                             length=140, mode="indeterminate")
        self.progress_label = ttk.Label(self.progress_frame, text="", style="Dim.TLabel",
                                         font=("Segoe UI", 9))

        # Path bar
        path_bar = ttk.Frame(detail)
        path_bar.pack(fill=tk.X, padx=8, pady=2)
        ttk.Button(path_bar, text="⬆", width=3, command=self._go_up).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(path_bar, text="📂", font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(0, 4))
        self.path_var = tk.StringVar(value=self.current_path)
        self.path_entry = ttk.Entry(path_bar, textvariable=self.path_var,
                                     font=("Consolas", 11))
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.path_entry.bind("<Return>", self._on_path_enter)

        ttk.Separator(detail).pack(fill=tk.X, padx=8, pady=4)

        # File table
        tree_frame = ttk.Frame(detail)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        columns = ("type", "name", "size", "date")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("type", text="")
        self.tree.heading("name", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("date", text="Modified")
        self.tree.column("type", width=30, minwidth=30, stretch=False, anchor=tk.CENTER)
        self.tree.column("name", width=350, minwidth=200)
        self.tree.column("size", width=100, minwidth=80, anchor=tk.E)
        self.tree.column("date", width=140, minwidth=120)

        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)  # Windows right-click

        # Notice label (shown when no device connected)
        self.notice_label = ttk.Label(
            detail, text="No device selected.",
            style="Dim.TLabel", font=("Segoe UI", 12), anchor=tk.CENTER
        )

        # Status bar
        status_frame = ttk.Frame(detail)
        status_frame.pack(fill=tk.X, padx=8, pady=(4, 6))
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(status_frame, textvariable=self.status_var, style="Dim.TLabel",
                  font=("Segoe UI", 9)).pack(side=tk.LEFT)
        ttk.Label(status_frame, text="RANDROID · RandyTech Solutions",
                  font=("Segoe UI", 8), style="Dim.TLabel").pack(side=tk.RIGHT)

    # ─── Device Management ────────────────────────────────────────────────

    def _refresh_devices(self):
        def _work():
            code, out, err = adb_cmd("devices", "-l")
            devs = []
            if code == 0:
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
                    devs.append({"serial": serial, "model": model, "state": state})
            self.after(0, lambda: self._update_devices(devs))

        threading.Thread(target=_work, daemon=True).start()

    def _update_devices(self, devs):
        self.devices = devs
        self.device_list.delete(0, tk.END)
        for d in devs:
            state_icon = "🟢" if d["state"] == "device" else ("🟠" if d["state"] == "unauthorized" else "⚪")
            self.device_list.insert(tk.END, f"{state_icon} {d['model']}  ({d['serial'][:16]})")
        if devs:
            self.device_hint.pack_forget()
            if not self.selected_serial or not any(d["serial"] == self.selected_serial for d in devs):
                self.selected_serial = devs[0]["serial"]
                self.device_list.select_set(0)
                self._list_path()
            self.status_var.set(f"{len(devs)} device(s) connected.")
        else:
            self.device_hint.pack(pady=20)
            self.selected_serial = None
            self.entries = []
            self._clear_tree()
            self.status_var.set("No devices detected (adb).")

    def _on_device_select(self, event):
        sel = self.device_list.curselection()
        if sel:
            idx = sel[0]
            self.selected_serial = self.devices[idx]["serial"]
            self.current_path = "/sdcard"
            self.path_var.set(self.current_path)
            self._list_path()

    def _current_device(self):
        if not self.selected_serial:
            return None
        return next((d for d in self.devices if d["serial"] == self.selected_serial), None)

    # ─── File Browser ─────────────────────────────────────────────────────

    def _list_path(self):
        dev = self._current_device()
        if not dev or dev["state"] != "device":
            self._clear_tree()
            self._show_notice("Device not authorized or not connected.")
            return
        self._hide_notice()
        self._set_busy(True)
        serial = dev["serial"]
        path = self.current_path if self.current_path.endswith("/") else self.current_path + "/"

        def _work():
            code, out, err = adb_cmd("shell", f"ls -AlL --color=never '{path}' 2>/dev/null", serial=serial)
            entries = parse_ls(out) if code == 0 else []
            self.after(0, lambda: self._update_tree(entries))

        threading.Thread(target=_work, daemon=True).start()

    def _update_tree(self, entries):
        self.entries = entries
        self._clear_tree()
        for e in entries:
            icon = "📁" if e["is_dir"] else "📄"
            size = "—" if e["is_dir"] else human_size(e["size"])
            self.tree.insert("", tk.END, iid=e["name"],
                             values=(icon, e["name"], size, e["date"]))
        self._set_busy(False)

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _show_notice(self, msg):
        self.notice_label.configure(text=msg)
        self.notice_label.pack(fill=tk.BOTH, expand=True, pady=60)

    def _hide_notice(self):
        self.notice_label.pack_forget()

    def _on_path_enter(self, event):
        self.current_path = self.path_var.get().strip() or "/sdcard"
        self._list_path()

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        name = sel[0]
        entry = next((e for e in self.entries if e["name"] == name), None)
        if entry and entry["is_dir"]:
            self._open_dir(entry)

    def _open_dir(self, entry):
        self.current_path = self.current_path.rstrip("/") + "/" + entry["name"]
        self.path_var.set(self.current_path)
        self._list_path()

    def _go_up(self):
        if self.current_path == "/":
            return
        trimmed = self.current_path.rstrip("/")
        idx = trimmed.rfind("/")
        self.current_path = trimmed[:idx] if idx > 0 else "/"
        self.path_var.set(self.current_path)
        self._list_path()

    # ─── File Operations ──────────────────────────────────────────────────

    def _push_file(self):
        dev = self._current_device()
        if not dev or dev["state"] != "device":
            return
        filepath = filedialog.askopenfilename(title="Select file to push to device")
        if not filepath:
            return
        serial = dev["serial"]
        dest = self.current_path if self.current_path.endswith("/") else self.current_path + "/"
        basename = os.path.basename(filepath)
        self.status_var.set(f"Pushing {basename}...")
        self._set_busy(True, indeterminate=True)

        def _work():
            code, out, err = adb_cmd("push", filepath, dest, serial=serial, timeout=600)
            ok = code == 0
            self.after(0, lambda: self._on_transfer_done(
                f"Pushed {basename} to device." if ok else f"Push failed: {err.strip()}"
            ))

        threading.Thread(target=_work, daemon=True).start()

    def _pull_file(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Pull", "Select a file first.")
            return
        name = sel[0]
        entry = next((e for e in self.entries if e["name"] == name), None)
        if not entry:
            return
        dest_dir = filedialog.askdirectory(title="Select destination folder")
        if not dest_dir:
            return
        dev = self._current_device()
        if not dev:
            return
        serial = dev["serial"]
        remote = self.current_path.rstrip("/") + "/" + entry["name"]
        self.status_var.set(f"Pulling {entry['name']}...")
        self._set_busy(True, indeterminate=True)

        def _work():
            code, out, err = adb_cmd("pull", remote, dest_dir, serial=serial, timeout=600)
            ok = code == 0
            self.after(0, lambda: self._on_transfer_done(
                f"Pulled to {dest_dir}." if ok else f"Pull failed: {err.strip()}"
            ))

        threading.Thread(target=_work, daemon=True).start()

    def _on_transfer_done(self, msg):
        self.status_var.set(msg)
        self._set_busy(False)
        self._list_path()

    def _new_folder(self):
        dev = self._current_device()
        if not dev or dev["state"] != "device":
            return
        name = simpledialog.askstring("New Folder", "Folder name:", parent=self)
        if not name:
            return
        serial = dev["serial"]
        target = self.current_path.rstrip("/") + "/" + name

        def _work():
            code, _, err = adb_cmd("shell", f"mkdir -p '{target}'", serial=serial)
            self.after(0, lambda: self._on_op_done(
                "Folder created." if code == 0 else f"Failed: {err.strip()}"
            ))

        threading.Thread(target=_work, daemon=True).start()

    def _delete_entry(self, entry):
        if not messagebox.askyesno("Delete",
                f"Delete '{entry['name']}'?\nThis is permanent and irreversible.", icon="warning"):
            return
        dev = self._current_device()
        if not dev:
            return
        serial = dev["serial"]
        target = self.current_path.rstrip("/") + "/" + entry["name"]

        def _work():
            code, _, err = adb_cmd("shell", f"rm -rf '{target}'", serial=serial)
            self.after(0, lambda: self._on_op_done(
                "Deleted." if code == 0 else f"Delete failed: {err.strip()}"
            ))

        threading.Thread(target=_work, daemon=True).start()

    def _rename_entry(self, entry):
        new_name = simpledialog.askstring("Rename", f"Rename '{entry['name']}' to:",
                                           initialvalue=entry["name"], parent=self)
        if not new_name or new_name == entry["name"]:
            return
        dev = self._current_device()
        if not dev:
            return
        serial = dev["serial"]
        src = self.current_path.rstrip("/") + "/" + entry["name"]
        dst = self.current_path.rstrip("/") + "/" + new_name

        def _work():
            code, _, err = adb_cmd("shell", f"mv '{src}' '{dst}'", serial=serial)
            self.after(0, lambda: self._on_op_done(
                "Renamed." if code == 0 else f"Rename failed: {err.strip()}"
            ))

        threading.Thread(target=_work, daemon=True).start()

    def _on_op_done(self, msg):
        self.status_var.set(msg)
        self._list_path()

    # ─── Context Menu ─────────────────────────────────────────────────────

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        entry = next((e for e in self.entries if e["name"] == item), None)
        if not entry:
            return

        menu = tk.Menu(self, tearoff=0, bg=COLORS["surface"], fg=COLORS["fg"],
                       activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
                       font=("Segoe UI", 10))
        if entry["is_dir"]:
            menu.add_command(label="📂 Open", command=lambda: self._open_dir(entry))
        menu.add_command(label="⬇ Pull to PC...", command=lambda: self._pull_single(entry))
        menu.add_command(label="✏️ Rename...", command=lambda: self._rename_entry(entry))
        menu.add_separator()
        menu.add_command(label="🗑️ Delete", command=lambda: self._delete_entry(entry))
        menu.tk_popup(event.x_root, event.y_root)

    def _pull_single(self, entry):
        dest_dir = filedialog.askdirectory(title="Select destination folder")
        if not dest_dir:
            return
        dev = self._current_device()
        if not dev:
            return
        serial = dev["serial"]
        remote = self.current_path.rstrip("/") + "/" + entry["name"]
        self.status_var.set(f"Pulling {entry['name']}...")
        self._set_busy(True, indeterminate=True)

        def _work():
            code, out, err = adb_cmd("pull", remote, dest_dir, serial=serial, timeout=600)
            ok = code == 0
            self.after(0, lambda: self._on_transfer_done(
                f"Pulled to {dest_dir}." if ok else f"Pull failed: {err.strip()}"
            ))

        threading.Thread(target=_work, daemon=True).start()

    # ─── Flash Dialog ─────────────────────────────────────────────────────

    def _open_flash_dialog(self):
        FlashDialog(self)

    # ─── Busy / Progress ──────────────────────────────────────────────────

    def _set_busy(self, busy, indeterminate=False):
        self.busy = busy
        if busy:
            self.progress_bar.pack(side=tk.LEFT, padx=(0, 4))
            if indeterminate:
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start(15)
            else:
                self.progress_bar.configure(mode="determinate")
        else:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.progress_label.pack_forget()


# ─── Flash Firmware Dialog ────────────────────────────────────────────────────

class FlashDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("⚡ Flash Firmware — RANDROID")
        self.geometry("640x520")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.has_heimdall = shutil.which("heimdall") is not None
        self.has_odin = shutil.which("odin4") is not None
        self.bl_path = tk.StringVar()
        self.ap_path = tk.StringVar()
        self.cp_path = tk.StringVar()
        self.csc_path = tk.StringVar()
        self.log_text = ""

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Header
        ttk.Label(main, text="⚡ Flash Firmware", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(main, text="Restore signed firmware only. No FRP/lock bypass.",
                  style="Dim.TLabel", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(2, 8))

        # Tool badges
        badge_frame = ttk.Frame(main)
        badge_frame.pack(fill=tk.X, pady=(0, 8))
        h_color = "Green.TLabel" if self.has_heimdall else "Dim.TLabel"
        o_color = "Green.TLabel" if self.has_odin else "Dim.TLabel"
        ttk.Label(badge_frame, text=f"{'✅' if self.has_heimdall else '❌'} Heimdall",
                  style=h_color, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(badge_frame, text=f"{'✅' if self.has_odin else '❌'} Odin4",
                  style=o_color, font=("Segoe UI", 10)).pack(side=tk.LEFT)

        ttk.Separator(main).pack(fill=tk.X, pady=8)

        # Action buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(btn_frame, text="⬇ Reboot to Download", command=self._reboot_download).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🔍 Detect (Download)", command=self._detect).pack(side=tk.LEFT, padx=2)

        ttk.Separator(main).pack(fill=tk.X, pady=8)

        # Odin4 section
        if self.has_odin:
            ttk.Label(main, text="Odin4 — Samsung firmware (.tar.md5)",
                      font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, pady=(0, 4))
            self._file_row(main, "BL (bootloader)", self.bl_path)
            self._file_row(main, "AP (system)", self.ap_path)
            self._file_row(main, "CP (modem)", self.cp_path)
            self._file_row(main, "CSC (region)", self.csc_path)
            ttk.Label(main, text="⚠️ Wrong firmware can brick the device — model must match exactly!",
                      style="Orange.TLabel", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=2)
            ttk.Button(main, text="⚡ Flash with Odin4", style="Accent.TButton",
                       command=self._flash_odin).pack(anchor=tk.W, pady=(4, 8))

        # Heimdall section
        if self.has_heimdall and not self.has_odin:
            ttk.Label(main, text="Heimdall — partition images (.img)",
                      font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, pady=(0, 4))
            ttk.Label(main, text="Use command line for Heimdall partitions:\n"
                      "mediatel flash heimdall --partition RECOVERY:recovery.img",
                      style="Dim.TLabel", font=("Consolas", 9)).pack(anchor=tk.W, pady=4)

        if not self.has_heimdall and not self.has_odin:
            ttk.Label(main, text="No flash tools installed.", style="Orange.TLabel",
                      font=("Segoe UI", 11)).pack(anchor=tk.W, pady=8)
            ttk.Label(main, text="• Heimdall (open source): choco install heimdall\n"
                      "• Odin4 (Samsung CLI): add odin4.exe to PATH",
                      style="Dim.TLabel", font=("Consolas", 9)).pack(anchor=tk.W)

        ttk.Separator(main).pack(fill=tk.X, pady=8)

        # Log area
        self.log_widget = tk.Text(main, bg=COLORS["bg_secondary"], fg=COLORS["fg_dim"],
                                   font=("Consolas", 9), height=5, borderwidth=0,
                                   insertbackground=COLORS["fg"])
        self.log_widget.pack(fill=tk.BOTH, expand=True)
        self.log_widget.insert("1.0", "Ready.")
        self.log_widget.configure(state=tk.DISABLED)

    def _file_row(self, parent, label, var):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text=label, font=("Consolas", 10), width=16).pack(side=tk.LEFT)
        ttk.Label(row, textvariable=var, style="Dim.TLabel", font=("Segoe UI", 9),
                  width=30).pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        ttk.Button(row, text="Browse", command=lambda: self._choose_file(var)).pack(side=tk.RIGHT)

    def _choose_file(self, var):
        f = filedialog.askopenfilename(
            title="Select firmware file",
            filetypes=[("Firmware", "*.tar.md5 *.tar *.img *.bin *.lz4"), ("All files", "*.*")]
        )
        if f:
            var.set(os.path.basename(f))
            var._full_path = f

    def _log(self, msg):
        self.log_widget.configure(state=tk.NORMAL)
        self.log_widget.delete("1.0", tk.END)
        self.log_widget.insert("1.0", msg)
        self.log_widget.configure(state=tk.DISABLED)

    def _reboot_download(self):
        dev = self.parent._current_device()
        if not dev:
            self._log("No device connected.")
            return
        self._log("Sending reboot download...")

        def _work():
            code, out, err = adb_cmd("reboot", "download", serial=dev["serial"])
            msg = "Reboot command sent." if code == 0 else f"Failed: {err.strip()}"
            self.after(0, lambda: self._log(msg))

        threading.Thread(target=_work, daemon=True).start()

    def _detect(self):
        self._log("Detecting...")

        def _work():
            msgs = []
            if self.has_heimdall:
                code, out, err = run_cmd(["heimdall", "detect"])
                msgs.append(f"Heimdall: {'✅ Device detected' if code == 0 else '❌ No device'}")
            if self.has_odin:
                code, out, err = run_cmd(["odin4", "-l"])
                detected = code == 0 and out.strip()
                msgs.append(f"Odin4: {'✅ Device detected' if detected else '❌ No device'}")
            if not msgs:
                msgs.append("No flash tools installed.")
            self.after(0, lambda: self._log("\n".join(msgs)))

        threading.Thread(target=_work, daemon=True).start()

    def _flash_odin(self):
        args = ["odin4"]
        paths = {"-b": self.bl_path, "-a": self.ap_path, "-c": self.cp_path, "-s": self.csc_path}
        for flag, var in paths.items():
            full = getattr(var, "_full_path", None)
            if full:
                args += [flag, full]
        if len(args) == 1:
            self._log("No firmware files selected.")
            return
        if not messagebox.askyesno("Flash", "Flash firmware with Odin4?\n\nWrong firmware can brick the device!",
                                    icon="warning", parent=self):
            return
        self._log("Flashing with Odin4...")

        def _work():
            code, out, err = run_cmd(args, timeout=1200)
            result = ("✅ Flash complete.\n" if code == 0 else f"❌ Failed (code {code}).\n") + out + err
            self.after(0, lambda: self._log(result))

        threading.Thread(target=_work, daemon=True).start()


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    app = MediatelApp()
    # Set window icon if available
    try:
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            app.iconbitmap(str(icon_path))
    except Exception:
        pass
    app.mainloop()


if __name__ == "__main__":
    main()
