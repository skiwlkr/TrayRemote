# tray.py
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
import re
import xml.etree.ElementTree as ET

# --- CTk Konfiguration ---
ctk.set_appearance_mode("Dark")    
ctk.set_default_color_theme("blue") 

# --- Konstanten ---
WINDOW_WIDTH = 380        # 10% schmaler (vorher 420)
RIGHT_EDGE_OFFSET = 15   
BOTTOM_EDGE_OFFSET = 55  
BG_APP_OUTER = '#121212' 
CARD_BG = '#252527'      
CARD_BORDER = '#3a3a3b'
MUTE_RED = '#b71c1c'
CORNER_RADIUS_OUTER = 20  # Äußere Hülle bleibt schick rund
CORNER_RADIUS_INNER = 12  # Innere Kästen etwas weniger stark gerundet

class SonosTrayApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.room_vol_widgets = {}
        self.room_select_widgets = {}
        self.current_album_url = ""
        
        try:
            self.controller = SonosController()
        except RuntimeError as e:
            print(f"Kritischer Startfehler: {e}")
            sys.exit(1)

        self.overrideredirect(True) 
        self.attributes('-topmost', True)
        self.wm_attributes("-transparentcolor", "#000001") 
        self.configure(fg_color="#000001")
        
        self.withdraw() 
        self.bind("<FocusOut>", self.on_focus_out)

        # --- ÄUSSERER KASTEN ---
        self.outer_frame = ctk.CTkFrame(self, fg_color=BG_APP_OUTER, corner_radius=CORNER_RADIUS_OUTER, 
                                        border_width=1, border_color=CARD_BORDER)
        self.outer_frame.pack(side="top", fill="x", padx=2, pady=2)
        
        self.main_container = ctk.CTkFrame(self.outer_frame, fg_color="transparent") 
        self.main_container.pack(side="top", fill="x", padx=12, pady=12)
        
        # 1. Box: Aktueller Song
        self.song_card = self.create_card()
        self.song_card.pack(side="top", fill="x", pady=(0, 8))
        
        inner_song = ctk.CTkFrame(self.song_card, fg_color="transparent")
        inner_song.pack(fill="x", padx=12, pady=12)
        
        # Album Art: corner_radius=0 für quadratische Form ohne Ränder
        self.cover_label = ctk.CTkLabel(inner_song, text="", width=80, height=80, 
                                        fg_color="#0a0a0a", corner_radius=0)
        self.cover_label.pack(side="left", padx=(0, 12))
        
        text_container = ctk.CTkFrame(inner_song, fg_color="transparent")
        text_container.pack(side="left", fill="both", expand=True)
        self.track_label = ctk.CTkLabel(text_container, text="Lade...", font=ctk.CTkFont(size=14, weight="bold"), 
                                        anchor="w", justify="left", wraplength=220)
        self.track_label.pack(fill="x")
        self.artist_label = ctk.CTkLabel(text_container, text="Lade...", font=ctk.CTkFont(size=12), 
                                         anchor="w", justify="left", wraplength=220, text_color="#999999")
        self.artist_label.pack(fill="x")

        # 2. Box: Steuerung
        self.control_card = self.create_card()
        self.control_card.pack(side="top", fill="x", pady=(0, 8))
        self.setup_controls(self.control_card)

        # 3. Box: Mixer
        self.mixer_card = self.create_card()
        self.mixer_card.pack(side="top", fill="x", pady=(0, 8))
        self.mixer_container = ctk.CTkFrame(self.mixer_card, fg_color="transparent")
        self.mixer_container.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(self.mixer_container, text="ROOM MIXER", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w")

        # 4. Box: Grouping
        self.group_card = self.create_card()
        self.group_card.pack(side="top", fill="x")
        self.group_container = ctk.CTkFrame(self.group_card, fg_color="transparent")
        self.group_container.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(self.group_container, text="GROUPING", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w")

        self.build_rest_of_ui()
        self.after(100, self.update_status)

    def create_card(self):
        return ctk.CTkFrame(self.main_container, fg_color=CARD_BG, corner_radius=CORNER_RADIUS_INNER, 
                            border_width=1, border_color=CARD_BORDER)

    def setup_controls(self, parent):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(pady=8)
        btn_cfg = {"width": 45, "height": 38, "font": ctk.CTkFont(size=16), "corner_radius": 10, "fg_color": "#333335"}
        ctk.CTkButton(box, text="⏮", command=lambda: self.control_action("previous"), **btn_cfg).pack(side="left", padx=4)
        ctk.CTkButton(box, text="▶", command=lambda: self.control_action("play"), **btn_cfg).pack(side="left", padx=4)
        ctk.CTkButton(box, text="⏸", command=lambda: self.control_action("pause"), **btn_cfg).pack(side="left", padx=4)
        ctk.CTkButton(box, text="⏭", command=lambda: self.control_action("next"), **btn_cfg).pack(side="left", padx=4)

    def build_rest_of_ui(self):
        for p in self.controller.get_all_players():
            row = ctk.CTkFrame(self.mixer_container, fg_color="transparent")
            row.pack(fill='x', pady=2)
            ctk.CTkLabel(row, text=p.player_name, width=90, anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
            m_btn = ctk.CTkButton(row, text="🔇", width=28, height=26, fg_color="#333335", command=lambda pl=p: self.toggle_mute_action(pl))
            m_btn.pack(side="left", padx=5)
            sld = ctk.CTkSlider(row, from_=0, to=100, height=14, command=lambda v, pl=p: self.set_single_volume_threaded(pl, v))
            sld.pack(side="left", fill="x", expand=True)
            self.room_vol_widgets[p.player_name] = {"slider": sld, "mute_btn": m_btn, "player": p}

            var = ctk.BooleanVar()
            chk = ctk.CTkCheckBox(self.group_container, text=p.player_name, variable=var, 
                                  command=lambda pl=p: self.toggle_room_action(pl), 
                                  font=ctk.CTkFont(size=12), checkbox_width=18, checkbox_height=18)
            chk.pack(anchor='w', pady=2)
            self.room_select_widgets[p.player_name] = {"var": var}

    def update_window_height(self):
        self.update_idletasks()
        needed_h = self.outer_frame.winfo_reqheight() + 4
        self.geometry(f"{WINDOW_WIDTH}x{int(needed_h)}")
        return int(needed_h)

    def get_all_artists(self, track_info):
        artists = []
        if track_info.get('artist'):
            artists.append(track_info['artist'])
        
        metadata = track_info.get('metadata')
        if metadata:
            try:
                ns = {'dc': 'http://purl.org/dc/elements/1.1/'}
                root_xml = ET.fromstring(metadata)
                for creator in root_xml.findall('.//dc:creator', ns):
                    if creator.text and creator.text not in artists:
                        artists.append(creator.text)
            except: pass

        full_str = ", ".join(artists)
        parts = re.split(r'\s*[/;&,]\s*|\s+feat\.\s+|\s+ft\.\s+', full_str, flags=re.IGNORECASE)
        return ", ".join(dict.fromkeys([p.strip() for p in parts if p.strip()]))

    def update_status(self):
        try:
            coord = self.controller.get_current_coordinator()
            track = coord.get_current_track_info()
            self.track_label.configure(text=track.get('title', 'Unbekannt'))
            self.artist_label.configure(text=self.get_all_artists(track))
            
            art_url = track.get('album_art')
            if art_url and art_url != self.current_album_url:
                self.current_album_url = art_url
                threading.Thread(target=self.load_album_art, args=(art_url,), daemon=True).start()

            for name, w in self.room_vol_widgets.items():
                p = w["player"]
                w["slider"].set(p.volume)
                w["mute_btn"].configure(fg_color=MUTE_RED if p.mute else "#333335")
                self.room_select_widgets[name]["var"].set(p.group.coordinator.uid == coord.uid)
        except: pass
        self.after(2000, self.update_status)

    def load_album_art(self, url):
        try:
            if url.startswith('/'):
                url = f"http://{self.controller.get_current_coordinator().ip_address}:1400{url}"
            resp = requests.get(url, timeout=3)
            # Resize auf exakt 80x80
            img = Image.open(io.BytesIO(resp.content)).resize((80, 80), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 80))
            self.after(0, lambda: self.cover_label.configure(image=ctk_img))
        except: pass

    def on_focus_out(self, event=None):
        if self.focus_get() is None: self.withdraw()

    def control_action(self, a):
        def t():
            c = self.controller.get_current_coordinator()
            if a=="play": c.play()
            elif a=="pause": c.pause()
            elif a=="next": c.next()
            elif a=="previous": c.previous()
        threading.Thread(target=t, daemon=True).start()

    def toggle_mute_action(self, p): threading.Thread(target=lambda: self.controller.toggle_mute_player(p), daemon=True).start()
    def set_single_volume_threaded(self, p, v): threading.Thread(target=lambda: setattr(p, 'volume', int(float(v))), daemon=True).start()
    def toggle_room_action(self, p): threading.Thread(target=lambda: self.controller.toggle_player(p), daemon=True).start()

# --- Hilfsfunktionen für den Start ---
def position_window(window):
    window.update_idletasks()
    h = window.update_window_height()
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    x = sw - WINDOW_WIDTH - RIGHT_EDGE_OFFSET
    y = sh - h - BOTTOM_EDGE_OFFSET
    window.geometry(f'{WINDOW_WIDTH}x{h}+{int(x)}+{int(y)}')

def toggle_app_window_threadsafe(icon=None, item=None):
    global root
    if root:
        def show():
            root.deiconify()
            position_window(root)
            root.lift()
            root.focus_force()
        root.after(0, show if root.state() != 'normal' else root.withdraw)

def run_pystray():
    global tray_icon
    menu = pystray.Menu(item("Öffnen", toggle_app_window_threadsafe, default=True), 
                        item("Beenden", lambda i, m: (i.stop(), root.after(0, root.quit))))
    # Falls vorhanden, icon.png laden, sonst Standard
    try:
        img = Image.open("assets/icon.png")
    except:
        img = Image.new('RGB', (64, 64), (0, 120, 212))
        
    tray_icon = pystray.Icon("SonosTray", img, "Sonos", menu, action=toggle_app_window_threadsafe)
    tray_icon.run()

def start_tray():
    global root
    root = SonosTrayApp()
    threading.Thread(target=run_pystray, daemon=True).start()
    root.mainloop()

if __name__ == '__main__':
    start_tray()