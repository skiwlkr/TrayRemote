# core/settings_manager.py
import threading
import customtkinter as ctk
from .ui_components import create_card
from .constants import ACTIVE_BLUE

class SettingsManager:
    def __init__(self, app):
        self.app = app
        self.setup_settings_ui()

    def setup_settings_ui(self):
        """Initializes the settings tab UI."""
        # Main Settings Container (managed by tray_app.py)
        container = self.app.settings_container
        
        # 1. Rediscover Devices Card
        self.discovery_card = create_card(container)
        self.discovery_card.pack(side="top", fill="x", pady=(0, 8), padx=12)
        disc_inner = ctk.CTkFrame(self.discovery_card, fg_color="transparent")
        disc_inner.pack(fill="x", padx=12, pady=12)
        
        self.rediscover_btn = ctk.CTkButton(
            disc_inner, 
            text="REDISCOVER DEVICES", 
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            fg_color="#2d2d30",
            hover_color=ACTIVE_BLUE,
            command=self.trigger_rediscovery
        )
        self.rediscover_btn.pack(fill="x")

        # 2. Startup Card
        self.startup_card = create_card(container)
        self.startup_card.pack(side="top", fill="x", pady=(0, 8), padx=12)
        startup_inner = ctk.CTkFrame(self.startup_card, fg_color="transparent")
        startup_inner.pack(fill="x", padx=12, pady=12)
        
        self.autostart_chk = ctk.CTkCheckBox(
            startup_inner, 
            text="RUN AT STARTUP", 
            variable=self.app.autostart_var, 
            command=self.app.toggle_autostart, 
            font=ctk.CTkFont(size=11, weight="bold"), 
            checkbox_width=18, 
            checkbox_height=18
        )
        self.autostart_chk.pack(anchor='w')

    def trigger_rediscovery(self):
        """Manually triggers a Sonos device discovery."""
        self.rediscover_btn.configure(text="SEARCHING...", state="disabled")
        
        def run():
            # Clear existing players to force a fresh scan
            self.app.controller.players = []
            self.app.controller.discover_players()
            
            # Update UI back on main thread
            def done():
                self.rediscover_btn.configure(text="REDISCOVER DEVICES", state="normal")
                self.app.update_status() # Force status update
                self.app.show_control()  # Switch back to main view after discovery
                
            self.app.after(0, done)
            
        threading.Thread(target=run, daemon=True).start()
