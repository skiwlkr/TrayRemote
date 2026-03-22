# core/tray_app.py
import threading
import pystray
from pystray import MenuItem as item
from PIL import Image
import sys
import customtkinter as ctk
import os
import xml.etree.ElementTree as ET
import ctypes 
import winreg

from .sonos_controller import SonosController
from .constants import *
from .ui_components import create_card
from .favorites_manager import FavoritesManager

# --- DPI SCALE FIX ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SonosTrayApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.room_vol_widgets = {}
        self.room_select_widgets = {}
        self.current_album_url = ""
        self.current_favorite_cover = None
        self.current_track_title = ""
        self.favorite_covers = {}
        self._img_cache = {} # title -> CTkImage (Persistent cache to prevent GC)
        self.selected_group_uid = None 
        self._current_cover = None # Reference to prevent garbage collection
        self._loading_favs = False
        
        # Initialize Managers
        self.favorites_mgr = FavoritesManager(self)
        
        # --- ASSETS ---
        # Adjust path to assets since we are now in core/
        base_path = os.path.dirname(os.path.dirname(__file__))
        assets_dir = os.path.join(base_path, "assets", "UI_elements")
        
        self.icons = {
            "backward": ctk.CTkImage(Image.open(os.path.join(assets_dir, "ui_backward.png")), size=(22, 22)),
            "forward": ctk.CTkImage(Image.open(os.path.join(assets_dir, "ui_Forward.png")), size=(22, 22)),
            "play": ctk.CTkImage(Image.open(os.path.join(assets_dir, "ui_play.png")), size=(22, 22)),
            "pause": ctk.CTkImage(Image.open(os.path.join(assets_dir, "ui_pause.png")), size=(22, 22)),
            "repeat": ctk.CTkImage(Image.open(os.path.join(assets_dir, "ui_repeat.png")), size=(18, 18)),
            "shuffle": ctk.CTkImage(Image.open(os.path.join(assets_dir, "ui_shuffle.png")), size=(18, 18))
        }
        
        try:
            self.controller = SonosController()
        except Exception as e:
            print(f"Startup Error: {e}")
            sys.exit(1)

        # --- GLASSMORPHISM & STYLE ---
        self.configure(fg_color=CHROMA_KEY)
        self.wm_attributes("-transparentcolor", CHROMA_KEY)
        self.attributes("-alpha", WINDOW_ALPHA)
        
        self.update()
        self.overrideredirect(True)
        self.attributes('-topmost', True)

        self.withdraw()
        self.bind("<FocusOut>", self.on_focus_out)

        # 3. Outer Frame
        self.outer_frame = ctk.CTkFrame(
            self, 
            fg_color=BG_APP_OUTER, 
            bg_color=CHROMA_KEY,
            corner_radius=CORNER_RADIUS_OUTER, 
            border_width=1, 
            border_color=CARD_BORDER
        )
        self.outer_frame.pack(side="top", fill="x")
        
        # --- HEADER ---
        self.header_container = ctk.CTkFrame(self.outer_frame, fg_color="transparent")
        self.header_container.pack(side="top", fill="x", padx=12, pady=(5, 5))
        
        self.title_label = ctk.CTkLabel(self.header_container, text="TrayRemote", font=ctk.CTkFont(size=18, weight="bold"))
        self.title_label.pack(side="left", padx=(8, 5))

        self.version_label = ctk.CTkLabel(self.header_container, text=APP_VERSION, font=ctk.CTkFont(size=14), text_color="gray")
        self.version_label.pack(side="left", pady=(3, 0))

        self.fav_toggle_btn = ctk.CTkButton(self.header_container, text="⭐", width=32, height=32, 

                                            fg_color="transparent", hover_color="#2a2a2b", 
                                            text_color="#FFFFFF",
                                            font=ctk.CTkFont(size=16), command=self.toggle_favorites)
        self.fav_toggle_btn.pack(side="right", padx=5)

        # --- CONTENT AREA ---
        self.content_area = ctk.CTkFrame(self.outer_frame, fg_color="transparent")
        self.content_area.pack(side="top", fill="both", expand=True, padx=12, pady=(5, 12))
        
        # --- VIEW 1: CONTROL ---
        self.main_container = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.main_container.pack(side="top", fill="both", expand=True)
        
        self.groups_card = create_card(self.main_container)
        self.groups_card.pack(side="top", fill="x", pady=(0, 8))
        g_box = ctk.CTkFrame(self.groups_card, fg_color="transparent")
        g_box.pack(fill="x", padx=12, pady=8)
        self.group_list_frame = ctk.CTkFrame(g_box, fg_color="transparent")
        self.group_list_frame.pack(fill="x")

        self.song_card = create_card(self.main_container)
        self.song_card.pack(side="top", fill="x", pady=(0, 8))
        inner_song = ctk.CTkFrame(self.song_card, fg_color="transparent")
        inner_song.pack(fill="x", padx=12, pady=12)
        self.cover_label = ctk.CTkLabel(inner_song, text="", width=90, height=90, fg_color="#0a0a0a", corner_radius=0)
        self.cover_label.pack(side="left", padx=(0, 12))
        
        txt_box = ctk.CTkFrame(inner_song, fg_color="transparent")
        txt_box.pack(side="left", fill="both", expand=True)
        self.track_label = ctk.CTkLabel(txt_box, text="Loading...", font=ctk.CTkFont(size=16, weight="bold"), anchor="w", wraplength=210, justify="left")
        self.track_label.pack(fill="x")
        self.artist_label = ctk.CTkLabel(txt_box, text="Loading...", font=ctk.CTkFont(size=13), anchor="w", wraplength=210, text_color="#bbbbbb", justify="left")
        self.artist_label.pack(fill="x")

        self.control_card = create_card(self.main_container)
        self.control_card.pack(side="top", fill="x", pady=(0, 8))
        self.setup_controls(self.control_card)

        self.mixer_card = create_card(self.main_container)
        self.mixer_card.pack(side="top", fill="x", pady=(0, 8))
        m_inner = ctk.CTkFrame(self.mixer_card, fg_color="transparent")
        m_inner.pack(fill="x", padx=12, pady=8)
        self.mixer_list_frame = ctk.CTkFrame(m_inner, fg_color="transparent")
        self.mixer_list_frame.pack(fill="x")

        self.group_card = create_card(self.main_container)
        self.group_card.pack(side="top", fill="x", pady=(0, 8))
        ga_inner = ctk.CTkFrame(self.group_card, fg_color="transparent")
        ga_inner.pack(fill="x", padx=12, pady=8)
        self.group_ui_list = ctk.CTkFrame(ga_inner, fg_color="transparent")
        self.group_ui_list.pack(fill="x")

        self.autostart_card = create_card(self.main_container)
        self.autostart_card.pack(side="top", fill="x")
        as_inner = ctk.CTkFrame(self.autostart_card, fg_color="transparent")
        as_inner.pack(fill="x", padx=12, pady=8)
        self.autostart_var = ctk.BooleanVar(value=self.check_autostart_status())
        self.autostart_chk = ctk.CTkCheckBox(as_inner, text="RUN AT STARTUP", variable=self.autostart_var, command=self.toggle_autostart, font=ctk.CTkFont(size=10, weight="bold"), checkbox_width=18, checkbox_height=18)
        self.autostart_chk.pack(anchor='w')

        # --- VIEW 2: FAVORITES ---
        self.fav_container = ctk.CTkFrame(self.content_area, fg_color="transparent")
        
        self.fav_list_frame = ctk.CTkFrame(self.fav_container, fg_color="transparent")
        self.fav_list_frame.pack(fill="x")
        
        self.fav_footer = ctk.CTkFrame(self.fav_container, fg_color="transparent")
        self.fav_footer.pack(fill="x", side="bottom", pady=(10, 0))
        self.refresh_btn = ctk.CTkButton(self.fav_footer, text="refresh", font=ctk.CTkFont(size=12, weight="normal"), 
                      height=20, fg_color="transparent", hover_color="#2a2a2b",
                      text_color=ACTIVE_BLUE,
                      command=self.favorites_mgr.trigger_refresh)
        self.refresh_btn.pack(pady=5)
        
        threading.Thread(target=self.favorites_mgr.load_favorites_ui, daemon=True).start()
        self.after(100, self.update_status)

    def toggle_favorites(self):
        if self.fav_container.winfo_viewable(): self.show_control()
        else: self.show_favorites()

    def show_control(self):
        def change():
            self.fav_container.pack_forget()
            self.main_container.pack(side="top", fill="both", expand=True)
            self.fav_toggle_btn.configure(text_color="#FFFFFF")
            self.update_window_height()
        self.animate_transition(change)

    def show_favorites(self):
        def change():
            self.main_container.pack_forget()
            self.fav_container.pack(side="top", fill="both", expand=True)
            self.fav_toggle_btn.configure(text_color=ACTIVE_BLUE)
            self.update_window_height()
        self.animate_transition(change)

    def animate_transition(self, callback):
        def fade_in(a):
            if a <= WINDOW_ALPHA:
                self.attributes("-alpha", a)
                self.after(10, lambda: fade_in(a + 0.1))
            else:
                self.attributes("-alpha", WINDOW_ALPHA)

        def fade_out(a):
            if a >= 0:
                self.attributes("-alpha", a)
                self.after(10, lambda: fade_out(a - 0.1))
            else:
                callback()
                fade_in(0)
        fade_out(WINDOW_ALPHA)

    def setup_controls(self, parent):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(pady=8)
        btn_cfg = {"width": 38, "height": 38, "corner_radius": 19}
        mode_cfg = {"width": 26, "height": 26, "fg_color": "transparent", "hover_color": "#2a2a2b", "corner_radius": 13}
        nav_cfg = {"width": 38, "height": 38, "fg_color": "transparent", "hover_color": "#2a2a2b"}

        self.shuffle_btn = ctk.CTkButton(box, text="", image=self.icons["shuffle"], command=lambda: self.control_action("shuffle"), **mode_cfg)
        self.shuffle_btn.pack(side="left", padx=12)
        
        ctk.CTkButton(box, text="", image=self.icons["backward"], command=lambda: self.control_action("previous"), **nav_cfg).pack(side="left", padx=3)
        self.play_btn = ctk.CTkButton(box, text="", image=self.icons["play"], command=lambda: self.control_action("play_pause"), fg_color=BTN_DEFAULT, **btn_cfg)
        self.play_btn.pack(side="left", padx=3)
        ctk.CTkButton(box, text="", image=self.icons["forward"], command=lambda: self.control_action("next"), **nav_cfg).pack(side="left", padx=3)
        
        self.repeat_btn = ctk.CTkButton(box, text="", image=self.icons["repeat"], command=lambda: self.control_action("repeat"), **mode_cfg)
        self.repeat_btn.pack(side="left", padx=10)

    def check_autostart_status(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "SonosTrayControl")
            winreg.CloseKey(key)
            return True
        except WindowsError: return False

    def toggle_autostart(self):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_path = f'"{os.path.realpath(sys.argv[0])}"'
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if self.autostart_var.get(): winreg.SetValueEx(key, "SonosTrayControl", 0, winreg.REG_SZ, app_path)
            else:
                try: winreg.DeleteValue(key, "SonosTrayControl")
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception as e: print(f"Autostart Error: {e}")

    def select_group(self, uid):
        self.selected_group_uid = uid
        self.rebuild_dynamic_sections()

    def rebuild_dynamic_sections(self):
        try:
            groups = self.controller.get_all_groups()
            active_g = next((g for g in groups if g.coordinator.uid == self.selected_group_uid), None)
            if not active_g: return
            for w in self.mixer_list_frame.winfo_children(): w.destroy()
            self.room_vol_widgets.clear()
            for p in active_g.members:
                row = ctk.CTkFrame(self.mixer_list_frame, fg_color="transparent")
                row.pack(fill='x', pady=2)
                ctk.CTkLabel(row, text=p.player_name, width=80, anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
                m_btn = ctk.CTkButton(row, text="🔇", width=32, height=32, fg_color="transparent", hover_color="#2a2a2b", font=ctk.CTkFont(size=18), command=lambda pl=p: self.toggle_mute(pl))
                m_btn.pack(side="left", padx=(2, 8))
                sld = ctk.CTkSlider(row, from_=0, to=100, height=14, command=lambda v, pl=p: self.set_vol(pl, v))
                sld.set(p.volume); sld.pack(side="left", fill="x", expand=True)
                self.room_vol_widgets[p.player_name] = {"slider": sld, "mute_btn": m_btn, "player": p}
            for w in self.group_ui_list.winfo_children(): w.destroy()
            all_p = self.controller.get_all_players()
            for p in all_p:
                is_in = any(m.uid == p.uid for m in active_g.members)
                chk = ctk.CTkCheckBox(self.group_ui_list, text=p.player_name, variable=ctk.BooleanVar(value=is_in), command=lambda pl=p: self.toggle_group_membership(pl), font=ctk.CTkFont(size=12), checkbox_width=18, checkbox_height=18)
                chk.pack(anchor='w', pady=2)
            self.update_window_height()
        except: pass

    def update_status(self):
        try:
            groups = self.controller.get_all_groups()
            if not groups: return
            if not self.selected_group_uid:
                self.selected_group_uid = groups[0].coordinator.uid
                self.rebuild_dynamic_sections()
            if len(self.group_list_frame.winfo_children()) != len(groups):
                for w in self.group_list_frame.winfo_children(): w.destroy()
                for g in groups:
                    u_id = g.coordinator.uid
                    btn = ctk.CTkButton(self.group_list_frame, text=g.coordinator.player_name, height=24, fg_color=ACTIVE_BLUE if u_id == self.selected_group_uid else BTN_DEFAULT, corner_radius=6, width=60, command=lambda u=u_id: self.select_group(u))
                    btn._sonos_uid = u_id; btn.pack(side="left", padx=2)
            else:
                for btn in self.group_list_frame.winfo_children():
                    if hasattr(btn, '_sonos_uid'): btn.configure(fg_color=ACTIVE_BLUE if btn._sonos_uid == self.selected_group_uid else BTN_DEFAULT)
            active_g = next((g for g in groups if g.coordinator.uid == self.selected_group_uid), None)
            if active_g:
                state = active_g.coordinator.get_current_transport_info().get('current_transport_state', '')
                self.play_btn.configure(
                    fg_color=ACTIVE_BLUE if state == 'PLAYING' else BTN_DEFAULT,
                    image=self.icons["pause"] if state == 'PLAYING' else self.icons["play"]
                )
                pm = active_g.coordinator.play_mode
                is_shuffled = "SHUFFLE" in pm
                is_repeat = pm in ["REPEAT_ALL", "REPEAT_ONE", "SHUFFLE", "SHUFFLE_REPEAT_ONE"]
                
                self.shuffle_btn.configure(fg_color=ACTIVE_BLUE if is_shuffled else "transparent")
                self.repeat_btn.configure(fg_color=ACTIVE_BLUE if is_repeat else "transparent")
                
                track = active_g.coordinator.get_current_track_info()
                track_title = track.get('title', 'Unknown')
                track_uri = track.get('uri', '')
                
                self.track_label.configure(text=track_title)
                self.artist_label.configure(text=self.get_all_artists(track))
                
                url = track.get('album_art')
                is_radio = 'x-sonosapi-stream' in track_uri or 'x-rincon-mp3radio' in track_uri or 'x-rincon-mp3' in track_uri
                
                if is_radio and not url:
                    if self.current_favorite_cover: url = self.current_favorite_cover
                    elif track_title in self.favorite_covers: url = self.favorite_covers[track_title]
                
                if url != self.current_album_url:
                    self.current_album_url = url
                    if url: threading.Thread(target=self.favorites_mgr.load_art, args=(url, active_g.coordinator), daemon=True).start()
                    else:
                        self.after(0, lambda: self.cover_label.configure(image=None))
                        self._current_cover = None
                
                for name, w in self.room_vol_widgets.items():
                    p_fresh = next((m for m in active_g.members if m.player_name == name), w["player"])
                    w["slider"].set(p_fresh.volume); w["mute_btn"].configure(text_color=MUTE_RED if p_fresh.mute else "#FFFFFF")
                
                # Check if grouping changed (member count mismatch)
                if len(self.room_vol_widgets) != len(active_g.members):
                    self.rebuild_dynamic_sections()
        except: pass
        self.after(2000, self.update_status)

    def get_all_artists(self, track_info):
        artists = [track_info.get('artist', '')]
        metadata = track_info.get('metadata')
        if metadata:
            try:
                ns = {'dc': 'http://purl.org/dc/elements/1.1/'}
                for c in ET.fromstring(metadata).findall('.//dc:creator', ns):
                    if c.text not in artists: artists.append(c.text)
            except: pass
        return ", ".join(dict.fromkeys([a.strip() for a in artists if a.strip()]))

    def control_action(self, a):
        # Immediate UI feedback for common actions
        if a == "play_pause":
            # Toggle based on current icon (fastest way to "predict" next state)
            is_playing = self.play_btn.cget("image") == self.icons["pause"]
            self.play_btn.configure(
                image=self.icons["play"] if is_playing else self.icons["pause"],
                fg_color=BTN_DEFAULT if is_playing else ACTIVE_BLUE
            )
        elif a == "next" or a == "previous":
            # Visual click effect
            self.track_label.configure(text="Switching...")

        def t():
            try:
                groups = self.controller.get_all_groups()
                coord = next((g.coordinator for g in groups if g.coordinator.uid == self.selected_group_uid), None)
                if not coord: return
                
                if a == "next": coord.next()
                elif a == "previous": coord.previous()
                elif a == "play_pause":
                    state = coord.get_current_transport_info().get('current_transport_state', '')
                    if state == 'PLAYING': coord.pause()
                    else: coord.play()
                elif a in ["shuffle", "repeat"]:
                    pm = coord.play_mode
                    s = "SHUFFLE" in pm
                    r = pm in ["REPEAT_ALL", "REPEAT_ONE", "SHUFFLE", "SHUFFLE_REPEAT_ONE"]
                    if a == "shuffle": s = not s
                    else: r = not r
                    if s and r: nm = "SHUFFLE_REPEAT_ONE" if pm in ["REPEAT_ONE", "SHUFFLE_REPEAT_ONE"] else "SHUFFLE"
                    elif s: nm = "SHUFFLE_NOREPEAT"
                    elif r: nm = "REPEAT_ONE" if pm in ["REPEAT_ONE", "SHUFFLE_REPEAT_ONE"] else "REPEAT_ALL"
                    else: nm = "NORMAL"
                    coord.play_mode = nm
                
                # Update UI from network state after a short delay
                self.after(600, self.update_status)
            except Exception as e:
                print(f"Control error: {e}")
        threading.Thread(target=t, daemon=True).start()

    def play_favorite_action(self, fav):
        self.current_favorite_cover = fav.get('album_art')
        threading.Thread(target=lambda: self.controller.play_favorite(fav, self.selected_group_uid), daemon=True).start()
        self.show_control()

    def toggle_mute(self, p):
        threading.Thread(target=lambda: self.controller.toggle_mute_player(p), daemon=True).start()

    def update_window_height(self):
        self.update_idletasks()
        h = self.outer_frame.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = sw - WINDOW_WIDTH - RIGHT_EDGE_OFFSET
        y = sh - h - BOTTOM_EDGE_OFFSET
        self.geometry(f"{WINDOW_WIDTH}x{int(h)}+{int(x)}+{int(y)}")

    def deiconify_with_fade(self):
        self._is_withdrawing = False
        self.attributes("-alpha", 0.0)
        self.deiconify()
        self.update_window_height()
        self.focus_force()
        def fade(a):
            if a <= WINDOW_ALPHA:
                self.attributes("-alpha", a)
                self.after(10, lambda: fade(a + 0.1))
            else: self.attributes("-alpha", WINDOW_ALPHA)
        fade(0.0)

    def withdraw_with_fade(self):
        if getattr(self, "_is_withdrawing", False): return
        self._is_withdrawing = True
        def fade(a):
            if not getattr(self, "_is_withdrawing", False): return
            if a >= 0:
                self.attributes("-alpha", a)
                self.after(10, lambda: fade(a - 0.1))
            else:
                self.withdraw()
                self._is_withdrawing = False
        fade(WINDOW_ALPHA)

    def on_focus_out(self, event=None):
        if self.focus_get() is None: self.withdraw_with_fade()

    def toggle_group_membership(self, p):
        def t():
            groups = self.controller.get_all_groups()
            target = next((g.coordinator for g in groups if g.coordinator.uid == self.selected_group_uid), None)
            if target:
                if p.group.coordinator.uid == target.uid: p.unjoin()
                else: p.join(target)
                # First refresh after a short delay (1.2s)
                self.after(1200, self.rebuild_dynamic_sections)
                # Safety refresh after a longer delay (3s) to ensure Sonos state is updated
                self.after(3000, self.rebuild_dynamic_sections)
        threading.Thread(target=t, daemon=True).start()

    def set_vol(self, p, v): threading.Thread(target=lambda: setattr(p, 'volume', int(float(v))), daemon=True).start()

def start_tray():
    global root
    root = SonosTrayApp()
    base_path = os.path.dirname(os.path.dirname(__file__))
    icon_path = os.path.join(base_path, "assets", "icon.png")
    try: tray_img = Image.open(icon_path)
    except: tray_img = Image.new('RGB', (64, 64), (0, 120, 212))
    def run_tray():
        menu = pystray.Menu(item("Open", lambda: root.after(0, root.deiconify_with_fade), default=True),
                            item("Exit", lambda i, m: (i.stop(), root.after(0, root.quit))))
        pystray.Icon("Sonos", tray_img, "Sonos", menu, action=lambda: root.after(0, root.deiconify_with_fade)).run()
    threading.Thread(target=run_tray, daemon=True).start()
    root.mainloop()
