# core/favorites_manager.py
import threading
import requests
import io
from PIL import Image
import customtkinter as ctk
from .constants import CARD_BG, ACTIVE_BLUE, CARD_BORDER

class FavoritesManager:
    def __init__(self, app):
        self.app = app

    def trigger_refresh(self):
        if not self.app._loading_favs:
            threading.Thread(target=self.load_favorites_ui, daemon=True).start()

    def load_favorites_ui(self, retry_count=0):
        """Fetches favorites and refreshes the UI."""
        if self.app._loading_favs and retry_count == 0:
            return
            
        self.app._loading_favs = True
        self.app.after(0, lambda: self.app.refresh_btn.configure(text="loading...", state="disabled"))
        
        try:
            # Get favorites in background
            favs = self.app.controller.get_favorites()
            
            # If no favorites found and we haven't retried much, try again after a short delay
            if not favs and retry_count < 2:
                print(f"[FAV] No favorites found, retrying... ({retry_count + 1}/2)")
                self.app.after(2000, lambda: threading.Thread(target=self.load_favorites_ui, args=(retry_count + 1,), daemon=True).start())
                return

            # Merge cover URLs for fallback with radio stations
            if favs:
                new_covers = {fav['title']: fav['album_art'] for fav in favs if fav.get('album_art')}
                self.app.favorite_covers.update(new_covers)
                print(f"[FAV CACHE] Total {len(self.app.favorite_covers)} covers in cache")
            
            def update_ui():
                try:
                    # Clear previous widgets
                    for widget in self.app.fav_list_frame.winfo_children():
                        widget.destroy()
                    
                    if not favs:
                        ctk.CTkLabel(self.app.fav_list_frame, text="No favorites found.", text_color="gray").pack(pady=10)
                    else:
                        print(f"[FAV] Rebuilding UI with {len(favs)} favorites")
                        for fav in favs:
                            title = fav.get('title', 'Unknown')
                            f_frame = ctk.CTkFrame(self.app.fav_list_frame, fg_color="transparent")
                            f_frame.pack(fill="x", pady=2)
                            
                            btn = ctk.CTkButton(
                                f_frame, text=title, anchor="w",
                                fg_color=CARD_BG, hover_color=ACTIVE_BLUE, height=45,
                                border_width=1, border_color=CARD_BORDER,
                                compound="left",
                                command=lambda f=fav: self.app.play_favorite_action(f)
                            )
                            btn.pack(fill="x", padx=10)
                            
                            # 1. Check if we have the actual Image object in memory for instant display
                            if title in self.app._img_cache:
                                print(f"[FAV] Instant load from memory: {title}")
                                btn.configure(image=self.app._img_cache[title])
                            else:
                                # 2. Determine cover URL (favor fresh data, fallback to URL cache)
                                art_url = fav.get('album_art')
                                if not art_url and title in self.app.favorite_covers:
                                    art_url = self.app.favorite_covers[title]
                                    
                                if art_url:
                                    threading.Thread(target=self.load_fav_art, args=(btn, art_url, title), daemon=True).start()
                                else:
                                    print(f"[FAV] No cover URL for {title}")
                    
                    self.app.after(200, self.app.update_window_height)
                finally:
                    self.app._loading_favs = False
                    self.app.refresh_btn.configure(text="refresh", state="normal")

            self.app.after(0, update_ui)
        except Exception as e:
            print(f"Error loading UI favs: {e}")
            self.app._loading_favs = False
            self.app.after(0, lambda: self.app.refresh_btn.configure(text="refresh", state="normal"))

    def load_fav_art(self, button_widget, url, title):
        if not url:
            return
        
        try:
            # Construct full URL for relative paths
            if url.startswith('/'):
                coord = self.app.controller.get_current_coordinator()
                if coord:
                    url = f"http://{coord.ip_address}:1400{url}"
                else:
                    print(f"[COVER] {title} - Coordinator not found for relative URL")
                    return
            
            print(f"[COVER] {title} - Loading: {url}")
            
            # Headers to appear as a normal browser
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
            
            resp = requests.get(url, timeout=5, allow_redirects=True, headers=headers)
            
            if resp.status_code != 200:
                print(f"[COVER] {title} - ✗ HTTP Error: {resp.status_code}")
                return
            
            if len(resp.content) < 100:
                print(f"[COVER] {title} - ✗ Content too small")
                return
            
            try:
                img = Image.open(io.BytesIO(resp.content))
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                
                img = img.resize((35, 35), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(35, 35))
                
                self.app._img_cache[title] = ctk_img
                
                def apply():
                    if button_widget.winfo_exists():
                        button_widget.configure(image=ctk_img)
                        button_widget._image_ref = ctk_img
                
                self.app.after(0, apply)
                print(f"[COVER] {title} - ✓ Successfully loaded and cached!")
                
            except Exception as img_error:
                print(f"[COVER] {title} - ✗ Image parse error: {img_error}")
            
        except requests.exceptions.RequestException as e:
            print(f"[COVER] {title} - ✗ Request error: {e}")
        except Exception as e:
            print(f"[COVER] {title} - ✗ General error: {type(e).__name__} - {e}")

    def load_art(self, url, coord):
        try:
            if not url:
                return
                
            if url.startswith('/'):
                url = f"http://{coord.ip_address}:1400{url}"
            
            print(f"[MAIN COVER] Loading: {url}")
            
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
            
            if resp.status_code != 200:
                print(f"[MAIN COVER] ✗ HTTP Error: {resp.status_code}")
                return
            
            img = Image.open(io.BytesIO(resp.content))
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
            
            img = img.resize((90, 90), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(90, 90))
            
            self.app.after(0, lambda: self.app.cover_label.configure(image=ctk_img))
            self.app._current_cover = ctk_img  # Hold reference
            
            print(f"[MAIN COVER] ✓ Successfully loaded!")
            
        except Exception as e:
            print(f"[MAIN COVER] ✗ Error: {type(e).__name__} - {e}")
