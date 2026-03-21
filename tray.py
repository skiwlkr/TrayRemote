# tray.py - v1.1.1 (English Translation)
import threading
import pystray
from pystray import MenuItem as item
from PIL import Image
from sonos_controller import SonosController
import sys
import customtkinter as ctk
import requests
import io
import os
import xml.etree.ElementTree as ET
import ctypes 
import winreg
import pywinstyles

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

WINDOW_WIDTH = 380
RIGHT_EDGE_OFFSET = 250
BOTTOM_EDGE_OFFSET = 65
BG_APP_OUTER = '#121212' # Darker base for glass tint
CARD_BG = '#1e1e20'      # Slightly lighter for layered look
CARD_BORDER = '#444444'  # Brighter border for glass edge effect
MUTE_RED = '#ff4444' 
ACTIVE_BLUE = '#3a7ebf' 
BTN_DEFAULT = '#2d2d30'
CORNER_RADIUS_OUTER = 20
CORNER_RADIUS_INNER = 12

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
        self.current_album_url = ""
        self.selected_group_uid = None 
        self._current_cover = None # Reference to prevent garbage collection
        self._loading_favs = False
        
        try:
            self.controller = SonosController()
        except Exception as e:
            print(f"Startup Error: {e}")
            sys.exit(1)

        # --- GLASSMORPHISM & STYLE ---
        # 1. Start with a clean chroma key
        CHROMA_KEY = "#010101"
        self.configure(fg_color=CHROMA_KEY)
        self.wm_attributes("-transparentcolor", CHROMA_KEY)
        
        # 2. Set window-level alpha to make ALL widgets translucent
        # 0.92 provides a good balance of "glass" vs readability
        self.attributes("-alpha", 0.92)
        
        try:
            if sys.getwindowsversion().build >= 22000:
                pywinstyles.apply_style(self, "mica")
            else:
                pywinstyles.apply_style(self, "acrylic")
        except Exception as e:
            print(f"Styling error: {e}")

        self.update()
        self.overrideredirect(True)
        self.attributes('-topmost', True)

        self.withdraw()
        self.bind("<FocusOut>", self.on_focus_out)

        # 3. Outer Frame: Using a tinted dark gray over the chroma background
        self.outer_frame = ctk.CTkFrame(
            self, 
            fg_color=BG_APP_OUTER, 
            bg_color=CHROMA_KEY,
            corner_radius=CORNER_RADIUS_OUTER, 
            border_width=1, 
            border_color=CARD_BORDER
        )
        self.outer_frame.pack(side="top", fill="x")
        
        # --- FLOATING HEADER ELEMENTS ---
        self.header_container = ctk.CTkFrame(self.outer_frame, fg_color="transparent")
        self.header_container.pack(side="top", fill="x", padx=12, pady=(5, 5))
        
        self.title_label = ctk.CTkLabel(self.header_container, text="TrayRemote", font=ctk.CTkFont(size=18, weight="bold"))
        self.title_label.pack(side="left", padx=8)
        
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
        
        self.groups_card = self.create_card(self.main_container)
        self.groups_card.pack(side="top", fill="x", pady=(0, 8))
        g_box = ctk.CTkFrame(self.groups_card, fg_color="transparent")
        g_box.pack(fill="x", padx=12, pady=8)
        self.group_list_frame = ctk.CTkFrame(g_box, fg_color="transparent")
        self.group_list_frame.pack(fill="x")

        self.song_card = self.create_card(self.main_container)
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

        self.control_card = self.create_card(self.main_container)
        self.control_card.pack(side="top", fill="x", pady=(0, 8))
        self.setup_controls(self.control_card)

        self.mixer_card = self.create_card(self.main_container)
        self.mixer_card.pack(side="top", fill="x", pady=(0, 8))
        m_inner = ctk.CTkFrame(self.mixer_card, fg_color="transparent")
        m_inner.pack(fill="x", padx=12, pady=8)
        self.mixer_list_frame = ctk.CTkFrame(m_inner, fg_color="transparent")
        self.mixer_list_frame.pack(fill="x")

        self.group_card = self.create_card(self.main_container)
        self.group_card.pack(side="top", fill="x", pady=(0, 8))
        ga_inner = ctk.CTkFrame(self.group_card, fg_color="transparent")
        ga_inner.pack(fill="x", padx=12, pady=8)
        self.group_ui_list = ctk.CTkFrame(ga_inner, fg_color="transparent")
        self.group_ui_list.pack(fill="x")

        self.autostart_card = self.create_card(self.main_container)
        self.autostart_card.pack(side="top", fill="x")
        as_inner = ctk.CTkFrame(self.autostart_card, fg_color="transparent")
        as_inner.pack(fill="x", padx=12, pady=8)
        self.autostart_var = ctk.BooleanVar(value=self.check_autostart_status())
        self.autostart_chk = ctk.CTkCheckBox(as_inner, text="RUN AT STARTUP", variable=self.autostart_var, command=self.toggle_autostart, font=ctk.CTkFont(size=10, weight="bold"), checkbox_width=18, checkbox_height=18)
        self.autostart_chk.pack(anchor='w')

        # --- VIEW 2: FAVORITES ---
        self.fav_container = ctk.CTkFrame(self.content_area, fg_color="transparent")
        # fav_container is not packed by default
        
        self.fav_list_frame = ctk.CTkFrame(self.fav_container, fg_color="transparent")
        self.fav_list_frame.pack(fill="x")
        
        # Refresh Link at the bottom
        self.fav_footer = ctk.CTkFrame(self.fav_container, fg_color="transparent")
        self.fav_footer.pack(fill="x", side="bottom", pady=(10, 0))
        self.refresh_btn = ctk.CTkButton(self.fav_footer, text="refresh", font=ctk.CTkFont(size=12, weight="normal"), 
                      height=20, fg_color="transparent", hover_color="#2a2a2b",
                      text_color=ACTIVE_BLUE,
                      command=self.trigger_refresh)
        self.refresh_btn.pack(pady=5)
        
        self._loading_favs = False
        threading.Thread(target=self.load_favorites_ui, daemon=True).start()
        self.after(100, self.update_status)

    def trigger_refresh(self):
        if not self._loading_favs:
            threading.Thread(target=self.load_favorites_ui, daemon=True).start()

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
        """Fades the window out, executes the callback, then fades back in."""
        def fade_in(a):
            if a <= 0.92:
                self.attributes("-alpha", a)
                self.after(10, lambda: fade_in(a + 0.1))
            else:
                self.attributes("-alpha", 0.92) # Final snap to target

        def fade_out(a):
            if a >= 0:
                self.attributes("-alpha", a)
                self.after(10, lambda: fade_out(a - 0.1))
            else:
                callback()
                fade_in(0)
        
        fade_out(0.92)

    def create_card(self, parent):
        return ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=CORNER_RADIUS_INNER, border_width=1, border_color=CARD_BORDER)

    def load_favorites_ui(self, retry_count=0):
        """Fetches favorites and refreshes the UI."""
        if self._loading_favs and retry_count == 0:
            return
            
        self._loading_favs = True
        self.after(0, lambda: self.refresh_btn.configure(text="loading...", state="disabled"))
        
        try:
            # Get favorites in background
            favs = self.controller.get_favorites()
            
            # If no favorites found and we haven't retried much, try again after a short delay
            if not favs and retry_count < 2:
                print(f"[FAV] No favorites found, retrying... ({retry_count + 1}/2)")
                self.after(2000, lambda: threading.Thread(target=self.load_favorites_ui, args=(retry_count + 1,), daemon=True).start())
                return

            # Merge cover URLs for fallback with radio stations
            if favs:
                new_covers = {fav['title']: fav['album_art'] for fav in favs if fav.get('album_art')}
                self.favorite_covers.update(new_covers)
                print(f"[FAV CACHE] Total {len(self.favorite_covers)} covers in cache")
            
            def update_ui():
                try:
                    # Clear previous widgets
                    for widget in self.fav_list_frame.winfo_children():
                        widget.destroy()
                    
                    if not favs:
                        ctk.CTkLabel(self.fav_list_frame, text="No favorites found.", text_color="gray").pack(pady=10)
                    else:
                        print(f"[FAV] Rebuilding UI with {len(favs)} favorites")
                        for fav in favs:
                            title = fav.get('title', 'Unknown')
                            f_frame = ctk.CTkFrame(self.fav_list_frame, fg_color="transparent")
                            f_frame.pack(fill="x", pady=2)
                            
                            btn = ctk.CTkButton(
                                f_frame, text=title, anchor="w",
                                fg_color=CARD_BG, hover_color=ACTIVE_BLUE, height=45,
                                border_width=1, border_color=CARD_BORDER,
                                compound="left",
                                command=lambda f=fav: self.play_favorite_action(f)
                            )
                            btn.pack(fill="x", padx=10)
                            
                            # 1. Check if we have the actual Image object in memory for instant display
                            if title in self._img_cache:
                                print(f"[FAV] Instant load from memory: {title}")
                                btn.configure(image=self._img_cache[title])
                            else:
                                # 2. Determine cover URL (favor fresh data, fallback to URL cache)
                                art_url = fav.get('album_art')
                                if not art_url and title in self.favorite_covers:
                                    art_url = self.favorite_covers[title]
                                    
                                if art_url:
                                    threading.Thread(target=self.load_fav_art, args=(btn, art_url, title), daemon=True).start()
                                else:
                                    print(f"[FAV] No cover URL for {title}")
                    
                    self.after(200, self.update_window_height)
                finally:
                    self._loading_favs = False
                    self.refresh_btn.configure(text="refresh", state="normal")

            self.after(0, update_ui)
        except Exception as e:
            print(f"Error loading UI favs: {e}")
            self._loading_favs = False
            self.after(0, lambda: self.refresh_btn.configure(text="refresh", state="normal"))

    def load_fav_art(self, button_widget, url, title):
        if not url:
            return
        
        try:
            # Construct full URL for relative paths
            if url.startswith('/'):
                coord = self.controller.get_current_coordinator()
                if coord:
                    url = f"http://{coord.ip_address}:1400{url}"
                else:
                    print(f"[COVER] {title} - Coordinator not found for relative URL")
                    return
            
            print(f"[COVER] {title} - Loading: {url}")
            
            # Headers to appear as a normal browser (prevents 451 errors)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://mytuner-radio.com/',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'image',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            }
            
            # Follow redirects and load image with browser headers
            resp = requests.get(url, timeout=5, allow_redirects=True, headers=headers)
            
            print(f"[COVER] {title} - Status: {resp.status_code}, Size: {len(resp.content)} bytes")
            
            # Check if we really have image data
            if resp.status_code != 200:
                print(f"[COVER] {title} - ✗ HTTP Error: {resp.status_code}")
                return
            
            if len(resp.content) < 100:
                print(f"[COVER] {title} - ✗ Content too small")
                return
            
            # Attempt to open the image
            try:
                img = Image.open(io.BytesIO(resp.content))
                
                # Convert to RGB if necessary
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                
                img = img.resize((35, 35), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(35, 35))
                
                # IMPORTANT: Save to persistent cache so it survives UI refresh
                self._img_cache[title] = ctk_img
                
                # Apply to current widget if it still exists
                def apply():
                    if button_widget.winfo_exists():
                        button_widget.configure(image=ctk_img)
                        # Reference on widget as extra safety
                        button_widget._image_ref = ctk_img
                
                self.after(0, apply)
                print(f"[COVER] {title} - ✓ Successfully loaded and cached!")
                
            except Exception as img_error:
                print(f"[COVER] {title} - ✗ Image parse error: {img_error}")
            
        except requests.exceptions.RequestException as e:
            print(f"[COVER] {title} - ✗ Request error: {e}")
        except Exception as e:
            print(f"[COVER] {title} - ✗ General error: {type(e).__name__} - {e}")

    def play_favorite_action(self, fav):
        # Save the favorite's cover
        self.current_favorite_cover = fav.get('album_art')
        print(f"[FAV] Playing {fav.get('title')} - Cover saved: {self.current_favorite_cover}")
        
        threading.Thread(target=lambda: self.controller.play_favorite(fav, self.selected_group_uid), daemon=True).start()
        self.show_control()

    def setup_controls(self, parent):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(pady=8)
        btn_cfg = {"width": 38, "height": 38, "font": ctk.CTkFont(size=16), "corner_radius": 19}
        mode_cfg = {"width": 30, "height": 30, "font": ctk.CTkFont(size=18), "fg_color": "transparent", "hover_color": "#2a2a2b", "text_color": "#FFFFFF"}
        nav_cfg = {"width": 38, "height": 38, "font": ctk.CTkFont(size=18), "fg_color": "transparent", "hover_color": "#2a2a2b", "text_color": "#FFFFFF"}

        self.shuffle_btn = ctk.CTkButton(box, text="🔀", command=lambda: self.control_action("shuffle"), **mode_cfg)
        self.shuffle_btn.pack(side="left", padx=10)
        
        ctk.CTkButton(box, text="⏮", command=lambda: self.control_action("previous"), **nav_cfg).pack(side="left", padx=3)
        self.play_btn = ctk.CTkButton(box, text="▶", command=lambda: self.control_action("play_pause"), fg_color=BTN_DEFAULT, **btn_cfg)
        self.play_btn.pack(side="left", padx=3)
        ctk.CTkButton(box, text="⏭", command=lambda: self.control_action("next"), **nav_cfg).pack(side="left", padx=3)
        
        self.repeat_btn = ctk.CTkButton(box, text="🔁", command=lambda: self.control_action("repeat"), **mode_cfg)
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
                    text="⏸" if state == 'PLAYING' else "▶"
                )
                pm = active_g.coordinator.play_mode
                self.shuffle_btn.configure(text_color=ACTIVE_BLUE if "SHUFFLE" in pm else "#FFFFFF")
                self.repeat_btn.configure(text_color=ACTIVE_BLUE if pm in ["SHUFFLE", "REPEAT_ALL", "REPEAT_ONE"] else "#FFFFFF")
                if len(self.room_vol_widgets) != len(active_g.members): self.rebuild_dynamic_sections()
                
                track = active_g.coordinator.get_current_track_info()
                track_title = track.get('title', 'Unknown')
                track_uri = track.get('uri', '')
                
                self.track_label.configure(text=track_title)
                self.artist_label.configure(text=self.get_all_artists(track))
                
                # Get Album Art URL
                url = track.get('album_art')
                
                # Check if it is a radio stream
                is_radio = 'x-sonosapi-stream' in track_uri or 'x-rincon-mp3radio' in track_uri or 'x-rincon-mp3' in track_uri
                
                # For Radio: Use stored favorite cover
                if is_radio and not url:
                    if self.current_favorite_cover:
                        url = self.current_favorite_cover
                    elif track_title in self.favorite_covers:
                        url = self.favorite_covers[track_title]
                
                # Load cover if URL exists and has changed
                if url != self.current_album_url:
                    self.current_album_url = url
                    if url:
                        print(f"[UPDATE] Loading cover: {url}")
                        threading.Thread(target=self.load_art, args=(url, active_g.coordinator), daemon=True).start()
                    else:
                        print(f"[UPDATE] No cover available, clearing")
                        self.after(0, lambda: self.cover_label.configure(image=None))
                        self._current_cover = None
                
                for name, w in self.room_vol_widgets.items():
                    p_fresh = next((m for m in active_g.members if m.player_name == name), w["player"])
                    w["slider"].set(p_fresh.volume); w["mute_btn"].configure(text_color=MUTE_RED if p_fresh.mute else "#FFFFFF")
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

    def load_art(self, url, coord):
        try:
            if not url:
                print("[MAIN COVER] No URL available")
                return
                
            if url.startswith('/'):
                url = f"http://{coord.ip_address}:1400{url}"
            
            print(f"[MAIN COVER] Loading: {url}")
            
            # Browser headers to avoid 451 errors (same as favorites)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://mytuner-radio.com/',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'image',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            }
            
            resp = requests.get(url, timeout=5, headers=headers, allow_redirects=True)
            
            print(f"[MAIN COVER] Status: {resp.status_code}, Size: {len(resp.content)} bytes")
            
            if resp.status_code != 200:
                print(f"[MAIN COVER] ✗ HTTP Error: {resp.status_code}")
                return
            
            img = Image.open(io.BytesIO(resp.content))
            print(f"[MAIN COVER] Image Info: Format={img.format}, Size={img.size}")
            
            # Convert to RGB if necessary
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
            
            img = img.resize((90, 90), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(90, 90))
            
            self.after(0, lambda: self.cover_label.configure(image=ctk_img))
            self._current_cover = ctk_img  # Hold reference
            
            print(f"[MAIN COVER] ✓ Successfully loaded!")
            
        except Exception as e:
            print(f"[MAIN COVER] ✗ Error: {type(e).__name__} - {e}")

    def control_action(self, a):
        def t():
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
                mode = coord.play_mode
                s, r = "SHUFFLE" in mode, mode in ["SHUFFLE", "REPEAT_ALL", "REPEAT_ONE"]
                if a == "shuffle": s = not s
                else: r = not r
                nm = "SHUFFLE" if (s and r) else "SHUFFLE_NOREPEAT" if s else "REPEAT_ALL" if r else "NORMAL"
                coord.play_mode = nm
        threading.Thread(target=t, daemon=True).start()

    def toggle_mute(self, p):
        threading.Thread(target=lambda: self.controller.toggle_mute_player(p), daemon=True).start()

    def update_window_height(self):
        self.update_idletasks()
        # Precise height calculation
        h = self.outer_frame.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = sw - WINDOW_WIDTH - RIGHT_EDGE_OFFSET
        y = sh - h - BOTTOM_EDGE_OFFSET
        self.geometry(f"{WINDOW_WIDTH}x{int(h)}+{int(x)}+{int(y)}")

    def deiconify_with_fade(self):
        """Opens the window with a fade-in animation."""
        self._is_withdrawing = False # Cancel any outgoing fade
        self.attributes("-alpha", 0.0)
        self.deiconify()
        self.update_window_height()
        self.focus_force()
        
        def fade(a):
            if a <= 0.92:
                self.attributes("-alpha", a)
                self.after(10, lambda: fade(a + 0.1))
            else:
                self.attributes("-alpha", 0.92)
        fade(0.0)

    def withdraw_with_fade(self):
        """Fades the window out then withdraws it."""
        if getattr(self, "_is_withdrawing", False): return
        self._is_withdrawing = True
        
        def fade(a):
            if not getattr(self, "_is_withdrawing", False): return # Aborted by deiconify
            if a >= 0:
                self.attributes("-alpha", a)
                self.after(10, lambda: fade(a - 0.1))
            else:
                self.withdraw()
                self._is_withdrawing = False
        fade(0.92)

    def on_focus_out(self, event=None):
        if self.focus_get() is None: 
            self.withdraw_with_fade()

    def toggle_group_membership(self, p):
        def t():
            groups = self.controller.get_all_groups()
            target = next((g.coordinator for g in groups if g.coordinator.uid == self.selected_group_uid), None)
            if target:
                if p.group.coordinator.uid == target.uid: p.unjoin()
                else: p.join(target)
                self.after(800, self.rebuild_dynamic_sections)
        threading.Thread(target=t, daemon=True).start()

    def set_vol(self, p, v): threading.Thread(target=lambda: setattr(p, 'volume', int(float(v))), daemon=True).start()

def position_window(window):
    window.update_window_height()

def start_tray():
    global root
    root = SonosTrayApp()
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    try: tray_img = Image.open(icon_path)
    except: tray_img = Image.new('RGB', (64, 64), (0, 120, 212))
    def run_tray():
        menu = pystray.Menu(item("Open", lambda: root.after(0, root.deiconify_with_fade), default=True),
                            item("Exit", lambda i, m: (i.stop(), root.after(0, root.quit))))
        pystray.Icon("Sonos", tray_img, "Sonos", menu, action=lambda: root.after(0, root.deiconify_with_fade)).run()
    threading.Thread(target=run_tray, daemon=True).start()
    root.mainloop()

if __name__ == '__main__':
    start_tray()