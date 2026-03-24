# core/sonos_queue.py
import threading
import requests
import io
import time
from PIL import Image
import customtkinter as ctk
from .constants import CARD_BG, ACTIVE_BLUE, CARD_BORDER

class QueueManager:
    def __init__(self, app):
        self.app = app
        self._loading_queue = False
        self.is_ui_ready = False
        self.last_group_uid = None
        self._queue_img_cache = {} # art_url -> CTkImage
        self._loading_urls = set() # Track URLs currently being fetched
        
        # Create a transparent placeholder to keep alignment consistent
        placeholder = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
        self.placeholder_img = ctk.CTkImage(light_image=placeholder, dark_image=placeholder, size=(40, 40))

    def trigger_refresh(self):
        if not self._loading_queue:
            self.is_ui_ready = False
            self.app.animate_transition(lambda: threading.Thread(target=self.load_queue_ui, daemon=True).start())

    def _get_track_info(self, track):
        title = getattr(track, 'title', 'Unknown') or 'Unknown'
        artist = getattr(track, 'creator', 'Unknown') or getattr(track, 'artist', 'Unknown') or 'Unknown'
        return title, artist

    def _truncate(self, text, max_chars=35):
        if len(text) > max_chars:
            return text[:max_chars-3] + "..."
        return text

    def load_queue_ui(self):
        """Fetches the current queue, pre-loads images, and refreshes the UI."""
        if self._loading_queue:
            return
            
        self._loading_queue = True
        self.last_group_uid = self.app.selected_group_uid
        
        def show_loading_state():
            self.app.queue_refresh_btn.configure(text="loading...", state="disabled")
            if hasattr(self.app, 'queue_list_frame'):
                for widget in self.app.queue_list_frame.winfo_children():
                    try: widget.destroy()
                    except: pass
            
            l_container = ctk.CTkFrame(self.app.queue_list_frame, fg_color="transparent")
            l_container.pack(pady=80, fill="both", expand=True)
            
            ctk.CTkLabel(l_container, text="Updating Queue", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack()
            ctk.CTkLabel(l_container, text="fetching tracks & covers...", 
                        font=ctk.CTkFont(size=13), text_color="gray").pack(pady=(5, 0))
            self.app.update_window_height()

        self.app.after(0, show_loading_state)
        
        try:
            queue = self.app.controller.get_queue(self.app.selected_group_uid)
            track_info = self.app.controller.get_current_track_info(self.app.selected_group_uid)
            # playlist_position is 1-based in Sonos, but 0-based in our queue list
            current_pos = int(track_info.get('playlist_position', 0)) - 1
            
            if queue:
                threads = []
                for track in queue[:50]:
                    art_url = getattr(track, 'album_art_uri', None)
                    
                    if art_url and art_url not in self._queue_img_cache and art_url not in self._loading_urls:
                        self._loading_urls.add(art_url)
                        t = threading.Thread(target=self._preload_image_only, args=(art_url,), daemon=True)
                        t.start()
                        threads.append(t)
                
                # Wait for images to load (max 2 seconds for initial snappy feel)
                start_wait = time.time()
                while any(t.is_alive() for t in threads) and (time.time() - start_wait < 2.0):
                    time.sleep(0.1)

            def update_ui():
                try:
                    if hasattr(self.app, 'queue_list_frame'):
                        for widget in self.app.queue_list_frame.winfo_children():
                            try: widget.destroy()
                            except: pass
                    
                    if not queue:
                        ctk.CTkLabel(self.app.queue_list_frame, text="Queue is empty.", text_color="gray").pack(pady=20)
                    else:
                        for i, track in enumerate(queue):
                            raw_title, raw_artist = self._get_track_info(track)
                            title = self._truncate(raw_title)
                            artist = self._truncate(raw_artist)
                            art_url = getattr(track, 'album_art_uri', None)
                            
                            is_playing = (i == current_pos)
                            bg_color = ACTIVE_BLUE if is_playing else CARD_BG
                            
                            f_frame = ctk.CTkFrame(self.app.queue_list_frame, fg_color=bg_color, height=60, corner_radius=8, border_width=1, border_color=CARD_BORDER)
                            f_frame._queue_index = i # Store index for highlighting
                            f_frame.pack(fill="x", pady=3, padx=2)
                            f_frame.pack_propagate(False)
                            
                            display_img = self._queue_img_cache.get(art_url) if art_url else self.placeholder_img
                            if not display_img:
                                display_img = self.placeholder_img
                            
                            img_label = ctk.CTkLabel(f_frame, text="", image=display_img, fg_color="transparent")
                            img_label.place(relx=0, rely=0.5, x=10, anchor="w")
                            
                            t_label = ctk.CTkLabel(f_frame, text=title, font=ctk.CTkFont(size=12, weight="bold"), anchor="w", fg_color="transparent")
                            t_label.place(relx=0, rely=0.35, x=60, anchor="w")
                            
                            a_label = ctk.CTkLabel(f_frame, text=artist, font=ctk.CTkFont(size=11), text_color="#bbbbbb", anchor="w", fg_color="transparent")
                            a_label.place(relx=0, rely=0.65, x=60, anchor="w")

                            def on_enter(e, f=f_frame, idx=i): 
                                # Use current_pos logic here too
                                track_info = self.app.controller.get_current_track_info(self.app.selected_group_uid)
                                curr = int(track_info.get('playlist_position', 0)) - 1
                                if idx != curr: f.configure(fg_color=ACTIVE_BLUE)
                            def on_leave(e, f=f_frame, idx=i): 
                                track_info = self.app.controller.get_current_track_info(self.app.selected_group_uid)
                                curr = int(track_info.get('playlist_position', 0)) - 1
                                if idx != curr: f.configure(fg_color=CARD_BG)
                            def on_click(e, idx=i): self.play_index(idx)

                            for w in [f_frame, img_label, t_label, a_label]:
                                w.bind("<Enter>", lambda e, f=f_frame, idx=i: on_enter(e, f, idx))
                                w.bind("<Leave>", lambda e, f=f_frame, idx=i: on_leave(e, f, idx))
                                w.bind("<Button-1>", on_click)

                            # If it's still a placeholder but has a URL, start a background update
                            if display_img == self.placeholder_img and art_url:
                                threading.Thread(target=self._load_and_update_label, args=(img_label, art_url), daemon=True).start()
                    
                    if len(queue) >= 50:
                         ctk.CTkLabel(self.app.queue_list_frame, text="Showing first 50 tracks", text_color="gray").pack(pady=5)

                    self.app.update_window_height()
                finally:
                    self._loading_queue = False
                    self.is_ui_ready = True
                    self.app.queue_refresh_btn.configure(text="refresh", state="normal")

            self.app.after(100, update_ui)
                
        except Exception as e:
            print(f"Error loading UI queue: {e}")
            self._loading_queue = False
            self.app.after(0, lambda: self.app.queue_refresh_btn.configure(text="refresh", state="normal"))

    def update_active_highlight(self):
        """Quickly updates which track is highlighted as playing without a full reload."""
        if not self.is_ui_ready or not hasattr(self.app, 'queue_list_frame'):
            return

        def update():
            try:
                track_info = self.app.controller.get_current_track_info(self.app.selected_group_uid)
                current_pos = int(track_info.get('playlist_position', 0)) - 1
                
                for widget in self.app.queue_list_frame.winfo_children():
                    if isinstance(widget, ctk.CTkFrame) and hasattr(widget, '_queue_index'):
                        is_playing = (widget._queue_index == current_pos)
                        new_color = ACTIVE_BLUE if is_playing else CARD_BG
                        if widget.cget("fg_color") != new_color:
                            widget.configure(fg_color=new_color)
            except: pass

        threading.Thread(target=update, daemon=True).start()

    def _get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://mytuner-radio.com/',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site'
        }

    def _preload_image_only(self, url):
        try:
            full_url = url
            if full_url.startswith('/'):
                coord = self.app.controller.get_current_coordinator()
                if coord: full_url = f"http://{coord.ip_address}:1400{full_url}"
                else: return
            
            resp = requests.get(full_url, timeout=5, headers=self._get_headers())
            if resp.status_code == 200 and len(resp.content) > 100:
                img = Image.open(io.BytesIO(resp.content))
                if img.mode not in ('RGB', 'RGBA'): img = img.convert('RGB')
                img = img.resize((40, 40), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 40))
                self._queue_img_cache[url] = ctk_img
        except: pass
        finally:
            if url in self._loading_urls:
                self._loading_urls.remove(url)

    def _load_and_update_label(self, label_widget, url):
        """Loads an image and updates a specific label widget directly."""
        try:
            ctk_img = None
            if url in self._queue_img_cache:
                ctk_img = self._queue_img_cache[url]
            else:
                if url in self._loading_urls:
                    # Wait a bit if it's already loading elsewhere, then try cache again
                    for _ in range(20): # max 2 seconds
                        time.sleep(0.1)
                        if url in self._queue_img_cache:
                            ctk_img = self._queue_img_cache[url]
                            break
                
                # If still not in cache and not loading, start a load
                if not ctk_img and url not in self._loading_urls:
                    self._loading_urls.add(url)
                    try:
                        full_url = url
                        if full_url.startswith('/'):
                            coord = self.app.controller.get_current_coordinator()
                            if coord: full_url = f"http://{coord.ip_address}:1400{full_url}"
                            else: return
                        
                        resp = requests.get(full_url, timeout=8, headers=self._get_headers())
                        if resp.status_code == 200 and len(resp.content) > 100:
                            img = Image.open(io.BytesIO(resp.content))
                            if img.mode not in ('RGB', 'RGBA'): img = img.convert('RGB')
                            img = img.resize((40, 40), Image.Resampling.LANCZOS)
                            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 40))
                            self._queue_img_cache[url] = ctk_img
                    finally:
                        if url in self._loading_urls:
                            self._loading_urls.remove(url)
            
            if not ctk_img:
                return

            def apply():
                if label_widget.winfo_exists():
                    label_widget.configure(image=ctk_img)
            self.app.after(0, apply)
        except: pass

    def play_index(self, index):
        threading.Thread(target=lambda: self.app.controller.play_from_queue(index, self.app.selected_group_uid), daemon=True).start()
        self.app.after(500, self.app.show_control)

    def clear_queue(self):
        """Clears the queue and refreshes UI."""
        def t():
            self.app.controller.clear_queue(self.app.selected_group_uid)
            self.trigger_refresh()
        threading.Thread(target=t, daemon=True).start()
