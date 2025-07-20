import json
from pathlib import Path

STATE_FILE = Path(__file__).parent / 'guild_state.json'
DEFAULT_VOICE = "Joanna"  # or wherever your project defines this

def save_guilds(guilds: dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(list(guilds.keys()), f)

def load_guilds():
    if not STATE_FILE.exists():
        return {}

    with open(STATE_FILE, "r") as f:
        guild_ids = json.load(f)

    from guild_state import Guild  # avoid circular imports
    import asyncio
    return {
        int(gid): Guild(
            guild_id=int(gid),
            message_queue=asyncio.Queue(),
            curr_channel=None,
            curr_voice=DEFAULT_VOICE # joanna is default voice
        )
        for gid in guild_ids
    }
