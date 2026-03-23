# core/favorites_manager.py
import threading
import requests
import io
import time
from PIL import Image
import customtkinter as ctk
from .constants import CARD_BG, ACTIVE_BLUE, CARD_BORDER

class FavoritesManager:
    def __init__(self, app):
        self.app = app

    def trigger_refresh(self):
        if not self.app._loading_favs:
            # Use the app's transition animation to fade out before starting
            self.app.animate_transition(lambda: threading.Thread(target=self.load_favorites_ui, args=(0, True), daemon=True).start())

    def load_favorites_ui(self, retry_count=0, animate=False):
        """Fetches favorites, pre-loads images, and then refreshes the UI with optional animation."""
        if self.app._loading_favs and retry_count == 0:
            return
            
        self.app._loading_favs = True
        
        def show_loading_state():
            self.app.refresh_btn.configure(text="loading...", state="disabled")
            # Clear previous widgets and show loading label
            for widget in self.app.fav_list_frame.winfo_children():
                widget.destroy()
            
            l_container = ctk.CTkFrame(self.app.fav_list_frame, fg_color="transparent")
            l_container.pack(pady=80, fill="both", expand=True)
            
            ctk.CTkLabel(l_container, text="Updating Favorites", 
                        font=ctk.CTkFont(size=16, weight="bold")).pack()
            ctk.CTkLabel(l_container, text="fetching latest covers...", 
                        font=ctk.CTkFont(size=13), text_color="gray").pack(pady=(5, 0))
            self.app.update_window_height()

        # If we are already in the "invisible" part of an animation, just run it
        # Otherwise, if we want animation, this should have been triggered by animate_transition
        self.app.after(0, show_loading_state)
        
        try:
            # 1. Get favorites data from Sonos
            favs = self.app.controller.get_favorites()
            
            # If no favorites found and we haven't retried much, try again after a short delay
            if not favs and retry_count < 2:
                print(f"[FAV] No favorites found, retrying... ({retry_count + 1}/2)")
                time.sleep(1.5)
                return self.load_favorites_ui(retry_count + 1, animate)

            # 2. Pre-load images in background
            if favs:
                threads = []
                for fav in favs:
                    title = fav.get('title')
                    art_url = fav.get('album_art')
                    
                    if art_url and title not in self.app._img_cache:
                        t = threading.Thread(target=self._preload_image_only, args=(title, art_url), daemon=True)
                        t.start()
                        threads.append(t)
                
                # Wait for images to load (max 2.5 seconds)
                start_wait = time.time()
                while any(t.is_alive() for t in threads) and (time.time() - start_wait < 2.5):
                    time.sleep(0.1)

            # 3. Update the UI
            def update_ui():
                try:
                    for widget in self.app.fav_list_frame.winfo_children():
                        widget.destroy()
                    
                    if not favs:
                        ctk.CTkLabel(self.app.fav_list_frame, text="No favorites found.", text_color="gray").pack(pady=20)
                    else:
                        print(f"[FAV] Rebuilding UI with {len(favs)} favorites")
                        for fav in favs:
                            title = fav.get('title', 'Unknown')
                            f_frame = ctk.CTkFrame(self.app.fav_list_frame, fg_color="transparent")
                            f_frame.pack(fill="x", pady=2)
                            
                            display_img = self.app._img_cache.get(title)
                            
                            btn = ctk.CTkButton(
                                f_frame, text=title, anchor="w",
                                fg_color=CARD_BG, hover_color=ACTIVE_BLUE, height=45,
                                border_width=1, border_color=CARD_BORDER,
                                compound="left", image=display_img,
                                command=lambda f=fav: self.app.play_favorite_action(f)
                            )
                            btn.pack(fill="x", padx=10)
                            
                            if not display_img:
                                art_url = fav.get('album_art') or self.app.favorite_covers.get(title)
                                if art_url:
                                    threading.Thread(target=self.load_fav_art, args=(btn, art_url, title), daemon=True).start()
                    
                    self.app.update_window_height()
                finally:
                    self.app._loading_favs = False
                    self.app.refresh_btn.configure(text="refresh", state="normal")

            # Final transition back to the list
            if animate:
                # If we're animating, fade out the "Loading..." state before showing the list
                self.app.after(500, lambda: self.app.animate_transition(update_ui))
            else:
                self.app.after(100, update_ui)
                
        except Exception as e:
            print(f"Error loading UI favs: {e}")
            self.app._loading_favs = False
            self.app.after(0, lambda: self.app.refresh_btn.configure(text="refresh", state="normal"))

        except Exception as e:
            print(f"Error loading UI favs: {e}")
            self.app._loading_favs = False
            self.app.after(0, lambda: self.app.refresh_btn.configure(text="refresh", state="normal"))

    def _preload_image_only(self, title, url):
        """Helper to load image into cache without touching UI."""
        try:
            # Construct full URL for relative paths
            if url.startswith('/'):
                coord = self.app.controller.get_current_coordinator()
                if coord:
                    url = f"http://{coord.ip_address}:1400{url}"
                else: return

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Referer': 'https://mytuner-radio.com/',
                'Connection': 'keep-alive'
            }
            
            resp = requests.get(url, timeout=4, headers=headers)
            if resp.status_code == 200 and len(resp.content) > 100:
                img = Image.open(io.BytesIO(resp.content))
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                
                img = img.resize((35, 35), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(35, 35))
                self.app._img_cache[title] = ctk_img
        except:
            pass


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
