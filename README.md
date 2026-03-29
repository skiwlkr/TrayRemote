# TrayRemote

A small desktop app to discover and control Sonos speakers on your local network. Provides playback and volume controls, grouping, and a tray/menubar interface for quick access.

<img src="screenshots/1WdZVQ8RkZ-ezgif.com-crop.gif" alt="drawing" width="400"/>

Features
- **Transparent UI:** New transparent, sleek design with interactive hover effects.
- **Sonos Favorites:** Dedicated tab to quickly access and play your favorite radio stations or music on network drives.
- **Queue functionality** Queue management directly through trayapp. 
- **Enhanced Favorites:** The Favorites tab now supports playback for Spotify and Apple Music (albums/tracks), as well as radio stations and network audio files.
- **Settings & Discovery:** Added a new Settings tab featuring a "Rediscover Sonos Devices" mechanism.
- **Automatic Discovery:** Seamlessly find Sonos devices on your local network.
- **Comprehensive Playback:** Play, pause, next, previous, and seek controls.
- **Multi-room Audio:** Per-room volume control and mute/unmute.
- **Group Management:** Easily create and manage Sonos speaker groups.
- **Tray Access:** Discreet system tray interface for quick, non-intrusive control.
- **Programmatic API:** Core controller functions available in `sonos_controller.py`.

*Note: Currently, playback functionality has been verified for Spotify only.*

Quick start
Requirements
- Python 3.8+
- Network access to Sonos devices (same LAN/subnet)

Install dependencies

```bash
python -m pip install -r requirements.txt
```

Run the app
```
python main.py
```

Key files
- [main.py](main.py): App entry point and system tray initialization.
- [core/sonos_controller.py](core/sonos_controller.py): Core Sonos logic: discovery, group management, and favorites handling.
- [core/tray_app.py](core/tray_app.py): Main UI application and window management.
- [core/favorites_manager.py](core/favorites_manager.py): Handles loading and playback of Sonos favorites.
- [core/constants.py](core/constants.py): Centralized styling (colors, offsets) and configuration constants.
- [config.py](config.py): Persistent configuration (e.g., autostart).
- [requirements.txt](requirements.txt): Python dependencies.
- [tray.spec](tray.spec): PyInstaller configuration for standalone builds.