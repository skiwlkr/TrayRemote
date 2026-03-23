import soco
from soco.plugins.sharelink import ShareLinkPlugin
import sys
import urllib.parse

def play_sonos_favorite(favorite_title):
    print(f"Searching for speaker...")
    device = soco.discovery.any_soco()
    if not device:
        print("No Sonos devices found.")
        return

    print(f"Found speaker: {device.player_name}")
    
    print(f"Searching for favorite: '{favorite_title}'")
    favs = device.music_library.get_sonos_favorites()
    
    target_fav = None
    for fav in favs:
        if getattr(fav, 'title', '').lower() == favorite_title.lower():
            target_fav = fav
            break
            
    if not target_fav:
        print(f"Favorite '{favorite_title}' not found.")
        return

    # Get URI
    uri = ""
    try:
        if hasattr(target_fav, 'get_uri'): uri = target_fav.get_uri()
        else: uri = getattr(target_fav, 'uri', "")
    except Exception as e:
        print(f"Could not get URI: {e}")
        return

    print(f"Found URI: {uri}")

    # --- SPECIAL HANDLING FOR SERVICES (Spotify, Apple Music) ---
    is_spotify = "spotify" in uri.lower()
    is_apple = "apple" in uri.lower() and "music" in uri.lower()
    
    if is_spotify or is_apple:
        try:
            service_name = "Spotify" if is_spotify else "Apple Music"
            print(f"{service_name} favorite detected, using ShareLinkPlugin...")
            plugin = ShareLinkPlugin(device)
            
            clean_uri = uri
            # Extract clean URI (spotify:xxx or applemusic:xxx)
            search_terms = ["spotify%3a", "spotify:", "applemusic%3a", "applemusic:"]
            lower_uri = uri.lower()
            
            found_term = None
            for term in search_terms:
                if term in lower_uri:
                    found_term = term
                    break
            
            if found_term:
                start_idx = lower_uri.find(found_term)
                encoded_part = uri[start_idx:]
                for char in ['?', '&', '"', ' ']:
                    if char in encoded_part:
                        encoded_part = encoded_part.split(char)[0]
                clean_uri = urllib.parse.unquote(encoded_part)
                print(f"Extracted service URI: {clean_uri}")

            # Get queue length before adding
            queue_before = device.get_queue()
            start_index = len(queue_before)
            
            # Add to queue
            plugin.add_share_link_to_queue(clean_uri)
            
            # Play from the start_index
            device.play_from_queue(start_index)
            print(f"Playback started at queue index {start_index}!")
            return
            
        except Exception as e:
            print(f"Error using ShareLinkPlugin: {e}, falling back to standard play...")

    # Standard playback fallback
    meta = getattr(target_fav, 'metadata', "")
    try:
        if "x-sonosapi-stream" in uri or "tunein" in uri.lower():
            device.play_uri(uri, meta, title=favorite_title)
        else:
            device.play_uri(uri, meta)
        print("Playback started via standard URI!")
    except Exception as e:
        print(f"Standard playback failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        play_sonos_favorite(sys.argv[1])
    else:
        print("Usage: python play_sonos_favorite.py 'Favorite Name'")
