import soco
import xml.etree.ElementTree as ET

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
                self.device = self.players[0]
                return True
            return False
        except Exception as e:
            print(f"Discovery Error: {e}")
            return False

    def refresh_device(self):
        return self.discover_players()

    def get_all_players(self):
        return self.players

    def get_current_coordinator(self):
        if not self.players: self.discover_players()
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
                                art_tag = root.find('.//*[local-name()="albumArtURI"]')
                            
                            if art_tag is not None:
                                album_art = art_tag.text
                                print(f"[FAV] {title} - Album Art (from Metadata): {album_art}")
                        except:
                            pass
                
                if not album_art:
                    print(f"[FAV] {title} - No album art found")

                favorite_list.append({
                    "title": title,
                    "uri": fav.get_uri() if hasattr(fav, 'get_uri') else getattr(fav, 'uri', ""),
                    "meta": getattr(fav, 'metadata', ""),
                    "album_art": album_art
                })
            
            return favorite_list
            
        except Exception as e:
            print(f"Error loading favorites: {e}")
            return []

    def play_favorite(self, fav_data, group_uid=None):
        """Plays favorites using robust methods for radio streams."""
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