import soco

def discover():
    print("Discovering Sonos devices...")
    device = soco.discovery.any_soco()
    if not device:
        print("No Sonos devices found.")
        return
    
    print(f"Found speaker: {device.player_name}")
    print("\n--- Sonos Favorites ---")
    favs = device.music_library.get_sonos_favorites()
    for i, fav in enumerate(favs):
        title = getattr(fav, 'title', 'Unknown')
        uri = ""
        try:
            if hasattr(fav, 'get_uri'): uri = fav.get_uri()
            else: uri = getattr(fav, 'uri', "")
        except: pass
        
        print(f"[{i}] Title: {title}")
        print(f"    URI:   {uri}")
        print("-" * 20)

if __name__ == "__main__":
    discover()
