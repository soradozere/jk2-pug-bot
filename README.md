# JK2 PUG Bot

A Discord bot that monitors JK2 CTF servers and pings players when a game is kicking off.

## Features

- Polls configured servers every 5 minutes
- Pings `@pug` role when 3+ players are detected
- Suggests a random team split when 8+ players are present (4v4+)
- `/pug` — self-assign or remove the pug role
- `/servers` — live status of all configured servers

---

## Setup

### 1. Create the Discord bot

1. Go to https://discord.com/developers/applications
2. New Application → give it a name
3. Bot tab → Add Bot → copy the **Token** (you'll need this)
4. Under **Privileged Gateway Intents**, enable:
   - Server Members Intent
5. OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Manage Roles`, `Mention Everyone`
6. Copy the generated URL and use it to invite the bot to your server

### 2. Configure the bot

Open `bot.py` and edit the CONFIG section at the top:

```python
DISCORD_TOKEN = "your token here"
PUG_CHANNEL_ID = 123456789        # Right-click the channel → Copy ID
```

Add your servers to the `SERVERS` list:

```python
SERVERS = [
    {"name": "NA East",  "host": "192.223.24.74", "port": 28070},
    {"name": "EU West",  "host": "x.x.x.x",       "port": 28070},
]
```

To get a channel ID: in Discord, go to Settings → Advanced → enable Developer Mode.
Then right-click any channel and select "Copy Channel ID".

### 3. Install and run locally

```bash
pip install -r requirements.txt
python bot.py
```

### 4. Deploy to Railway (recommended)

1. Push this folder to a GitHub repo
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Add an environment variable: `DISCORD_TOKEN` = your token
4. In `bot.py`, change the last line to read from env:

```python
import os
bot.run(os.environ["DISCORD_TOKEN"])
```

Railway will keep it running 24/7 on the free tier.

---

## Cooldown logic

Once a server triggers a ping, it won't ping again for 30 minutes — even if the player count keeps fluctuating. If the server drops below 3 players, the cooldown resets, so the next time it fills up it'll ping again.

---

## Adding more servers

Just append to the `SERVERS` list in `bot.py`:

```python
{"name": "Your Server Name", "host": "ip.address.here", "port": 28070},
```

---

## No third-party query library needed

The bot uses a raw UDP socket to query JK2 servers directly using the Quake 3 `getstatus` protocol — no extra libraries required beyond `discord.py`.
