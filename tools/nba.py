from nba_api.stats.static import players

def get_player_id(player_name: str):
    # Get all players
    all_players = players.get_players()
    
    # Find player by name (case-insensitive)
    player = next((p for p in all_players if p['full_name'].lower() == player_name.lower()), None)
    
    if player:
        return player['id']
    else:
        return None