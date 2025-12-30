# sonos_controller.py
import soco
from soco.discovery import by_name

class SonosController:
    def __init__(self, default_room_name=None):
        self.refresh_players()
        if not self.all_players:
            raise RuntimeError("Keine Sonos-Speaker im Netzwerk gefunden.")
        
        # Standard-Koordinator festlegen
        if default_room_name:
            self.current_coordinator = by_name(default_room_name)
        else:
            self.current_coordinator = self.all_players[0]

    def refresh_players(self):
        """Sucht nach allen Speakern im Netzwerk."""
        self.all_players = list(soco.discover())
        return self.all_players

    def get_all_players(self):
        return self.all_players

    def get_current_coordinator(self):
        """Gibt den aktuellen Gruppen-Koordinator zurück."""
        # Sicherstellen, dass wir den tatsächlichen Koordinator der Gruppe haben
        return self.current_coordinator.group.coordinator

    def get_current_track_info(self):
        try:
            return self.get_current_coordinator().get_current_track_info()
        except:
            return {"title": "Unbekannt", "artist": "Unbekannt"}

    # --- Playback Steuerung ---
    def play(self):
        self.get_current_coordinator().play()

    def pause(self):
        self.get_current_coordinator().pause()

    def next_track(self):
        self.get_current_coordinator().next_track()

    # --- Gruppen Logik ---
    def toggle_player(self, player):
        """Fügt einen Player zur Gruppe hinzu oder entfernt ihn."""
        coordinator = self.get_current_coordinator()
        if player.uid == coordinator.uid:
            return # Koordinator kann sich nicht selbst verlassen
        
        if player.group.coordinator.uid == coordinator.uid:
            player.unjoin()
        else:
            player.join(coordinator)

    # --- NEU: Mute Logik ---
    def toggle_mute_player(self, player):
        """Schaltet Mute für einen einzelnen Player um."""
        player.mute = not player.mute
        return player.mute

    def toggle_group_mute(self):
        """Schaltet Mute für die gesamte Gruppe um."""
        coordinator = self.get_current_coordinator()
        new_state = not coordinator.mute
        coordinator.group.mute = new_state
        return new_state

    def get_mute_state(self, player):
        """Gibt True zurück, wenn der Player stummgeschaltet ist."""
        return player.mute