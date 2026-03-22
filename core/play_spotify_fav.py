import soco
from soco.plugins.sharelink import ShareLinkPlugin
import sys

def play_spotify_favorite(favorite_title):
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

    # Check if it's a Spotify URI (common for Spotify favorites)
    # Often looks like: x-rincon-cpcontainer:1004206caspotify%3aalbum%3a...
    # The ShareLinkPlugin likes cleaner URIs or Spotify links, 
    # but we can extract the Spotify ID if needed.
    
    plugin = ShareLinkPlugin(device)
    
    print(f"Adding to queue via ShareLinkPlugin...")
    try:
        # The ShareLinkPlugin.add_share_link_to_queue handles Spotify URIs/links
        # If the URI from favorites is already a 'spotify:album:...' it works.
        # If it's a 'x-rincon-cpcontainer...', we might need to extract the 'spotify:album:...' part.
        
        clean_uri = uri
        if "spotify%3a" in uri.lower():
            import urllib.parse
            # Extract the part starting with spotify:
            start_idx = uri.lower().find("spotify%3a")
            encoded_part = uri[start_idx:]
            # Stop at the first '?' if present
            if "?" in encoded_part:
                encoded_part = encoded_part.split("?")[0]
            clean_uri = urllib.parse.unquote(encoded_part)
            print(f"Extracted clean Spotify URI: {clean_uri}")

        # Add to queue
        plugin.add_share_link_to_queue(clean_uri)
        
        # Play the last added item in the queue
        queue = device.get_queue()
        print(f"Queue size now: {len(queue)}")
        device.play_from_queue(len(queue) - 1)
        print("Playback started!")
        
    except Exception as e:
        print(f"Error using ShareLinkPlugin: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        play_spotify_favorite(sys.argv[1])
    else:
        print("Usage: python play_spotify_fav.py 'Favorite Name'")
