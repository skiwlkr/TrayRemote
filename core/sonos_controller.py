import soco
import xml.etree.ElementTree as ET
from soco.plugins.sharelink import ShareLinkPlugin
import urllib.parse

class SonosController:
    def __init__(self):
        self.players = []
        self.device = None
        self.discover_players()

    def discover_players(self):
        """Discovers Sonos devices on the network."""
        try:
            found = soco.discover()
            if found:
                self.players = list(found)
                # Find the first coordinator or just take the first found player
                self.device = next((p for p in self.players if p.is_coordinator), self.players[0])
                return True
            self.players = []
            self.device = None
            return False
        except Exception as e:
            print(f"Discovery Error: {e}")
            self.players = []
            self.device = None
            return False

    def refresh_device(self):
        return self.discover_players()

    def get_all_players(self):
        return self.players

    def get_current_coordinator(self):
        return self.players[0] if self.players else None

    def get_all_groups(self):
        anchor = self.get_current_coordinator()
        return list(anchor.zone_group_state.groups) if anchor else []

    def toggle_mute_player(self, player):
        player.mute = not player.mute

    def get_favorites(self):
        """Loads favorites including metadata and album art URLs."""
        if not self.device and not self.refresh_device():
            return []
        
        try:
            favs = self.device.music_library.get_sonos_favorites()
            favorite_list = []
            
            for fav in favs:
                try:
                    title = getattr(fav, 'title', 'Unknown')
                    album_art = None
                    
                    # IMPORTANT: Check direct album_art_uri attribute first (for radio stations)
                    if hasattr(fav, 'album_art_uri'):
                        album_art = fav.album_art_uri
                        print(f"[FAV] {title} - Album Art (direct): {album_art}")
                    
                    # Fallback: Try to get it from metadata (for other favorites)
                    if not album_art:
                        meta = getattr(fav, 'metadata', "")
                        if meta:
                            try:
                                root = ET.fromstring(meta)
                                ns = {'upnp': 'urn:schemas-upnp-org:metadata-1-0/upnp/'}
                                art_tag = root.find('.//upnp:albumArtURI', ns)
                                
                                if art_tag is None:
                                    art_tag = root.find('.//upnp:albumArtURI')
                                
                                if art_tag is not None:
                                    album_art = art_tag.text
                                    print(f"[FAV] {title} - Album Art (from Metadata): {album_art}")
                            except:
                                pass
                    
                    if not album_art:
                        print(f"[FAV] {title} - No album art found")

                    # Get URI safely
                    uri = ""
                    try:
                        if hasattr(fav, 'get_uri'):
                            uri = fav.get_uri()
                        else:
                            uri = getattr(fav, 'uri', "")
                    except Exception as uri_err:
                        # Fallback for objects that crash on get_uri() due to missing resources
                        if hasattr(fav, 'resources') and len(fav.resources) > 0:
                            uri = fav.resources[0].uri
                        else:
                            print(f"[FAV] {title} - Could not extract URI: {uri_err}")
                            continue # Skip if we can't play it anyway

                    favorite_list.append({
                        "title": title,
                        "uri": uri,
                        "meta": getattr(fav, 'metadata', ""),
                        "album_art": album_art
                    })
                except Exception as item_e:
                    print(f"Error processing favorite item: {item_e}")
                    continue
            
            return favorite_list
            
        except Exception as e:
            print(f"Error loading favorites: {e}")
            return []

    def get_queue(self, group_uid=None):
        """Retrieves the current play queue for the specified group."""
        target = self.device
        if group_uid:
            for p in self.players:
                if p.group.coordinator.uid == group_uid:
                    target = p.group.coordinator
                    break
        if not target: return []
        try:
            # We fetch up to 50 items for performance. 
            # SoCo's SearchResult doesn't always support slicing, so we convert to list.
            queue = target.get_queue(max_items=50)
            return list(queue)
        except Exception as e:
            print(f"Error getting queue: {e}")
            return []

    def play_from_queue(self, index, group_uid=None):
        """Plays a track from the queue at the specified index."""
        target = self.device
        if group_uid:
            for p in self.players:
                if p.group.coordinator.uid == group_uid:
                    target = p.group.coordinator
                    break
        if not target: return
        try:
            target.play_from_queue(index)
        except Exception as e:
            print(f"Error playing from queue: {e}")

    def clear_queue(self, group_uid=None):
        """Clears the current play queue for the specified group."""
        target = self.device
        if group_uid:
            for p in self.players:
                if p.group.coordinator.uid == group_uid:
                    target = p.group.coordinator
                    break
        if not target: return
        try:
            target.clear_queue()
        except Exception as e:
            print(f"Error clearing queue: {e}")

    def get_current_track_info(self, group_uid=None):
        """Returns information about the currently playing track, including its queue position."""
        target = self.device
        if group_uid:
            for p in self.players:
                if p.group.coordinator.uid == group_uid:
                    target = p.group.coordinator
                    break
        if not target: return {}
        try:
            return target.get_current_track_info()
        except Exception as e:
            print(f"Error getting track info: {e}")
            return {}

    def play_favorite(self, fav_data, group_uid=None):
        """Plays favorites using robust methods for radio streams and music services."""
        target = self.device
        if group_uid:
            for p in self.players:
                if p.group.coordinator.uid == group_uid:
                    target = p.group.coordinator
                    break
        if not target: return

        try:
            title = fav_data.get('title') if isinstance(fav_data, dict) else fav_data
            favs = target.music_library.get_sonos_favorites()

            for fav in favs:
                if getattr(fav, 'title', '') == title:
                    uri = fav.get_uri() if hasattr(fav, 'get_uri') else getattr(fav, 'uri', "")
                    meta = getattr(fav, 'metadata', "")

                    print(f"Attempting playback of: {title}")

                    # --- SPECIAL HANDLING FOR SERVICES (Spotify, Apple Music) ---
                    is_spotify = "spotify" in uri.lower()
                    is_apple = "apple" in uri.lower() and "music" in uri.lower()
                    
                    if is_spotify or is_apple:
                        try:
                            service_name = "Spotify" if is_spotify else "Apple Music"
                            print(f"{service_name} favorite detected, using ShareLinkPlugin for: {title}")
                            plugin = ShareLinkPlugin(target)
                            
                            clean_uri = uri
                            # Extract clean URI (spotify:xxx or applemusic:xxx)
                            # Sonos URIs often look like: x-rincon-cpcontainer:1004206caspotify%3aalbum%3a...
                            # or x-rincon-cpcontainer:1004206caapplemusic%3aalbum%3a...
                            
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
                                # Stop at common delimiters
                                for char in ['?', '&', '"', ' ']:
                                    if char in encoded_part:
                                        encoded_part = encoded_part.split(char)[0]
                                clean_uri = urllib.parse.unquote(encoded_part)
                                print(f"Extracted service URI: {clean_uri}")
                            
                            # Get queue length before adding to know where the first new track will be
                            queue_before = target.get_queue()
                            start_index = len(queue_before)
                            
                            # Add to queue
                            plugin.add_share_link_to_queue(clean_uri)
                            
                            # Play from the start_index
                            target.play_from_queue(start_index)
                            print(f"Successfully started {service_name} favorite (at index {start_index}): {title}")
                            return
                        except Exception as service_err:
                            print(f"ShareLinkPlugin failed for {service_name}: {service_err}, falling back to standard play_uri...")

                    try:
                        # For radio favorites (x-sonosapi-stream), providing metadata is mandatory.
                        if "x-sonosapi-stream" in uri or "tunein" in uri.lower():
                            # Specialized handling for Radio
                            target.play_uri(uri, meta, title=title)
                        else:
                            # Standard Handling
                            target.play_uri(uri, meta)

                        print(f"Successfully started: {title}")

                    except soco.exceptions.SoCoUPnPException as e:
                        if "402" in str(e):
                            print(f"402 Error received. Attempting fallback via AVTransport...")
                            # Manual method via Transport Service to resolve UPnP 402
                            target.avTransport.SetAVTransportURI([
                                ('InstanceID', 0),
                                ('CurrentURI', uri),
                                ('CurrentURIMetaData', meta)
                            ])
                            target.play()
                        else:
                            raise e
                    return
        except Exception as e:
            print(f"Final error playing {title}: {e}")
