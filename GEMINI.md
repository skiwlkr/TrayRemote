# GEMINI.md - TrayRemote Context

## Project Overview
**TrayRemote** is a Windows-optimized desktop application designed to control Sonos speakers directly from the system tray. It provides quick access to playback controls, volume mixing, room grouping, and Sonos favorites through a modern, dark-themed interface.

### Main Technologies
- **Language:** Python 3.8+
- **Sonos Integration:** [SoCo](https://github.com/SoCo/SoCo) (Sonos Controller)
- **UI Framework:** [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (for the popup window)
- **Tray Management:** [pystray](https://github.com/moses-palmer/pystray)
- **Image Processing:** [Pillow](https://python-pillow.org/) (album art and icons)

## Architecture
- **`main.py`**: The entry point that initializes the tray application.
- **`sonos_controller.py`**: Encapsulates the core logic for device discovery, group management, and Sonos-specific UPNP interactions (including robust handling for radio streams).
- **`tray.py`**: Contains the `SonosTrayApp` class (a `ctk.CTk` subclass) and handles the system tray icon. It manages the dynamic UI updates, threading for network calls, and Windows-specific features (DPI awareness, registry-based autostart).
- **`config.py`**: A small utility for persisting user configurations (like autostart) to `config.json`.

## Building and Running

### Development
1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Run Application:**
   ```bash
   python main.py
   ```

### Packaging
The project uses **PyInstaller** for distribution. A `tray.spec` file is included in the root directory to define the build process.

## Development Conventions

### Non-Blocking UI
All network operations involving Sonos devices (via `soco`) **MUST** be executed in background threads to prevent the UI from freezing. Use `threading.Thread(target=..., daemon=True).start()` or similar patterns.

### Windows Integration
- **DPI Awareness:** The app explicitly sets process DPI awareness in `tray.py` to ensure sharp UI rendering on high-resolution displays.
- **Autostart:** Implemented via the Windows Registry (`HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`).

### UI Styling
- **Theme:** "Dark" appearance mode with a custom color palette defined in `tray.py` (e.g., `BG_APP_OUTER`, `CARD_BG`, `ACTIVE_BLUE`).
- **Layout:** Uses a fixed-width popup window (`WINDOW_WIDTH = 380`) that calculates its height dynamically based on the active tab and number of visible rooms.

### Sonos Specifics
- **Discovery:** Relies on `soco.discover()`. If discovery fails, the app may need a manual refresh or network check.
- **Album Art:** Handles both local Sonos art paths (prefixed with speaker IP) and external URIs (e.g., for radio favorites), including custom headers to bypass anti-scraping measures on certain radio providers.

## Key Files
- `main.py`: Entry point.
- `sonos_controller.py`: Core Sonos logic.
- `tray.py`: UI and Tray lifecycle.
- `config.py`: Config management.
- `assets/icon.png`: Application icon.
