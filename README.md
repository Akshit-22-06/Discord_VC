# VC Camera Enforcement Bot (Python)

This Discord bot monitors users with the `ASH's` role in the voice channel `THE REDEMPTION !`.

## Rules
- Only `ASH's` role members are tracked.
- When they join `THE REDEMPTION !`, they receive a DM:
  `Turn on camera within 5 minutes or you’ll be moved`
- After 5 minutes, if `self_video` is still off, they are moved to `CAMS OFF` and receive a second DM.
- Non-`ASH's` users are ignored.

## Setup
1. Create a `.env` file with your bot token:

```env
DISCORD_TOKEN=your-token-here
```

2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Run the bot:

```bash
python bot.py
```

## Notes
- The bot requires `Guild Members` and `Guild Voice States` intents in the Discord developer portal.
- It also needs permission to move members between voice channels.
