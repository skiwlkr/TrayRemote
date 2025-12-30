import soco

class SonosController:
    def __init__(self):
        self.players = []
        self.discover_players()

    def discover_players(self):
        self.players = list(soco.discover())
        if not self.players:
            raise RuntimeError("No Sonos players found on the network.")

    def get_all_players(self):
        return self.players

    def get_current_coordinator(self):
        if not self.players: self.discover_players()
        return self.players[0]

    def get_all_groups(self):
        anchor = self.get_current_coordinator()
        return list(anchor.zone_group_state.groups)

    def toggle_mute_player(self, player):
        player.mute = not player.mute