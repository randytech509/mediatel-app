# RANDROID — Mediatel for Windows

> Android device management: file browser, push/pull, flash firmware.
> **RandyTech Solutions © 2024-2026**

---

## 📦 Downloads

| File | Type | Description |
|------|------|-------------|
| `Mediatel.exe` | GUI App | Desktop app with file browser, device sidebar, flash dialog |
| `mediatel-cli.exe` | CLI Tool | Command-line interface with all features + interactive mode |

## 🖥️ Requirements

- **Windows 10/11** (64-bit)
- **ADB** (Android Debug Bridge) — comes with [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)
- **USB debugging** enabled on your Android device
- *(Optional)* **Heimdall** or **Odin4** for firmware flashing

## 🚀 Quick Start

### GUI App
```
Double-click Mediatel.exe
```

### CLI Tool
```bash
# List connected devices
mediatel-cli devices

# Browse files on device
mediatel-cli ls /sdcard/Download

# Push file to device
mediatel-cli push "C:\Users\you\photo.jpg" /sdcard/Download/

# Pull file from device
mediatel-cli pull /sdcard/Download/photo.jpg "C:\Users\you\Desktop"

# Interactive file browser
mediatel-cli interactive
```

## 📋 CLI Commands

| Command | Description |
|---------|-------------|
| `devices` | List connected Android devices |
| `ls [path]` | List files (default: /sdcard) |
| `push <local> [dest]` | Copy file from PC to device |
| `pull <remote> [dest]` | Copy file from device to PC |
| `delete <path>` | Delete file/folder on device |
| `rename <path> <new>` | Rename file/folder |
| `mkdir <path>` | Create directory on device |
| `shell <cmd>` | Run shell command on device |
| `reboot [mode]` | Reboot (normal/bootloader/recovery/download) |
| `flash odin4` | Flash Samsung firmware (Odin4) |
| `flash heimdall` | Flash partitions (Heimdall) |
| `detect` | Detect device in Download mode |
| `interactive` / `i` | Interactive file browser session |

### Examples

```bash
# Target a specific device
mediatel-cli -s SERIAL_NUMBER ls /sdcard

# Flash Samsung firmware
mediatel-cli flash odin4 --bl BL.tar.md5 --ap AP.tar.md5 --cp CP.tar.md5 --csc CSC.tar.md5

# Flash with Heimdall
mediatel-cli flash heimdall --partition RECOVERY:recovery.img --partition BOOT:boot.img

# Delete without confirmation
mediatel-cli delete /sdcard/old_folder -y

# Reboot to recovery
mediatel-cli reboot recovery
```

---

## 🔨 Building from Source

### Option A: Local Build (on a Windows machine)

**Prerequisites:** Python 3.10+ installed with "Add to PATH" checked.

```bash
# Clone the repo
git clone <your-repo-url>
cd mediatel-app/Sources/Mediatel/windows-build

# Run the build script
build.bat
```

Output: `dist\Mediatel.exe` and `dist\mediatel-cli.exe`

### Option B: GitHub Actions (automated, recommended)

1. Push the repo to GitHub
2. The workflow at `.github/workflows/build-windows.yml` runs automatically
3. Download the `.exe` files from **Actions → Artifacts**
4. For releases: create a tag `git tag v1.0.0 && git push --tags` — a GitHub Release is created automatically

### Option C: Manual PyInstaller

```bash
# Install PyInstaller
pip install pyinstaller

# Build GUI (windowed, no console)
cd mediatel-gui
pyinstaller --onefile --windowed --name Mediatel mediatel_gui.py

# Build CLI (console)
cd ../mediatel-cli
pyinstaller --onefile --console --name mediatel-cli mediatel_cli.py
```

---

## 📁 Project Structure

```
windows-build/
├── build.bat                  # One-click Windows build script
├── README.md                  # This file
├── mediatel-gui/
│   ├── mediatel_gui.py        # GUI application (tkinter)
│   └── mediatel_gui.spec      # PyInstaller spec
├── mediatel-cli/
│   ├── mediatel_cli.py        # CLI application
│   └── mediatel_cli.spec      # PyInstaller spec
└── dist/                      # Built executables (after build)
    ├── Mediatel.exe
    └── mediatel-cli.exe
```

## ⚡ Firmware Flashing

The app supports two open-source flashing tools:

| Tool | Use Case | Install |
|------|----------|---------|
| **Heimdall** | Flash partition images (.img) | `choco install heimdall` or download from GitHub |
| **Odin4** | Flash Samsung archives (.tar.md5) | Place `odin4.exe` in PATH |

> ⚠️ **Warning:** Flashing wrong firmware can brick your device. Always verify the model matches exactly.

> ℹ️ This tool only performs **legitimate firmware restore** (signed partitions). It does **not** bypass FRP, screen locks, or any security measures.

---

*RANDROID · RandyTech Solutions*
