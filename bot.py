"""
JK2 PUG Bot
-----------
- Polls configured JK2 servers every 5 minutes
- Pings @pug role when 3+ players are detected on any server
- Suggests random team split when 8+ players are present (4v4)
- /pug command to self-assign/remove the pug role
- /servers command to check live server status
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import socket
import struct
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# CONFIG — edit these before deploying
# ---------------------------------------------------------------------------

DISCORD_TOKEN = "HERE"
PUG_CHANNEL_ID = 1495028158137762033      # Channel ID to post notifications in
PUG_ROLE_NAME = "pug"                    # Role name to ping (bot will create if missing)
PLAYER_THRESHOLD = 3                     # Min players to trigger a ping
POLL_INTERVAL_SECONDS = 300             # 5 minutes
COOLDOWN_MINUTES = 30                    # Don't re-ping same server for this long

SERVERS = [
    {"name": "NA East",  "host": "192.223.24.74",  "port": 28070},
    {"name": ":: DOZER NY NWH ::", "host": "199.19.72.85", "port": 28070},
    {"name": "THE HUB | Reborn", "host": "74.91.116.180", "port": 28070},
    {"name": "The American NWH", "host": "74.91.115.117", "port": 28070},
    {"name": "POMMESBUDE [CTF]", "host": "141.144.226.30", "port": 28070},
    {"name": "NWH Tokyo", "host": "54.238.175.102", "port": 28070},

]

# ---------------------------------------------------------------------------
# SERVER QUERY (Quake 3 / JK2 UDP protocol)
# ---------------------------------------------------------------------------

def query_jk2_server(host: str, port: int, timeout: float = 3.0) -> dict:
    """
    Queries a JK2/Q3-protocol server via UDP.
    Returns player names, count, map, and online status.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        # Quake 3 getstatus query
        packet = b"\xff\xff\xff\xffgetstatus\x00"
        sock.sendto(packet, (host, port))
        data, _ = sock.recvfrom(4096)
        sock.close()

        # Response starts with \xff\xff\xff\xffstatusResponse\n
        decoded = data[4:].decode("utf-8", errors="replace")
        if not decoded.startswith("statusResponse"):
            return {"online": False}

        lines = decoded.split("\n")

        # Parse key-value pairs from line 1
        info_str = lines[1] if len(lines) > 1 else ""
        info_parts = info_str.strip("\\").split("\\")
        info = {}
        for i in range(0, len(info_parts) - 1, 2):
            info[info_parts[i]] = info_parts[i + 1]

        # Parse player lines (score ping "name")
        players = []
        for line in lines[2:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                name = parts[2].strip('"')
                # Strip Q3 colour codes (^0-^9)
                clean_name = ""
                i = 0
                while i < len(name):
                    if name[i] == "^" and i + 1 < len(name):
                        i += 2
                    else:
                        clean_name += name[i]
                        i += 1
                players.append(clean_name)

        return {
            "online": True,
            "player_count": len(players),
            "players": players,
            "map": info.get("mapname", info.get("sv_mapname", "unknown")),
            "max_players": int(info.get("sv_maxclients", 32)),
        }

    except Exception:
        return {"online": False, "player_count": 0, "players": [], "map": "unknown", "max_players": 32}


# ---------------------------------------------------------------------------
# BOT SETUP
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
last_pinged: dict[str, datetime] = {}


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    poll_servers.start()


# ---------------------------------------------------------------------------
# POLLING LOOP
# ---------------------------------------------------------------------------

@tasks.loop(seconds=POLL_INTERVAL_SECONDS)
async def poll_servers():
    await bot.wait_until_ready()

    guild = bot.guilds[0] if bot.guilds else None
    if not guild:
        return

    channel = guild.get_channel(PUG_CHANNEL_ID)
    if not channel:
        print(f"⚠️  Channel {PUG_CHANNEL_ID} not found")
        return

    pug_role = discord.utils.get(guild.roles, name=PUG_ROLE_NAME)

    for server in SERVERS:
        key = f"{server['host']}:{server['port']}"
        data = await asyncio.to_thread(query_jk2_server, server["host"], server["port"])

        count = data.get("player_count", 0)

        # If below threshold, reset cooldown so next surge triggers a ping
        if not data.get("online") or count < PLAYER_THRESHOLD:
            last_pinged.pop(key, None)
            continue

        # Respect cooldown
        now = datetime.utcnow()
        if key in last_pinged and (now - last_pinged[key]) < timedelta(minutes=COOLDOWN_MINUTES):
            continue

        last_pinged[key] = now

        # Build the notification message
        role_mention = pug_role.mention if pug_role else f"@{PUG_ROLE_NAME}"
        player_list = ", ".join(data["players"]) if data["players"] else "players unknown"

        msg = (
            f"{role_mention} **{count} players on {server['name']}** — join up!\n"
            f"🗺️  Map: `{data['map']}` | 👥 {player_list}\n"
            f"```connect {server['host']}:{server['port']}```"
        )


        await channel.send(msg)
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Pinged for {server['name']} ({count} players)")


# ---------------------------------------------------------------------------
# SLASH COMMANDS
# ---------------------------------------------------------------------------

@bot.tree.command(name="pug", description="Toggle your PUG role — get pinged when games are kicking off")
async def pug_command(interaction: discord.Interaction):
    guild = interaction.guild
    pug_role = discord.utils.get(guild.roles, name=PUG_ROLE_NAME)

    # Create the role if it doesn't exist yet
    if not pug_role:
        pug_role = await guild.create_role(
            name=PUG_ROLE_NAME,
            mentionable=True,
            reason="Created by PUG bot"
        )

    member = interaction.user
    if pug_role in member.roles:
        await member.remove_roles(pug_role)
        await interaction.response.send_message(
            "✅ Removed. You won't be pinged for PUGs.", ephemeral=True
        )
    else:
        await member.add_roles(pug_role)
        await interaction.response.send_message(
            "✅ You're in! You'll get pinged when 3+ players are on a server.", ephemeral=True
        )


@bot.tree.command(name="servers", description="Live status of all JK2 PUG servers")
async def servers_command(interaction: discord.Interaction):
    await interaction.response.defer()

    lines = ["**JK2 Server Status**\n"]

    for server in SERVERS:
        data = await asyncio.to_thread(query_jk2_server, server["host"], server["port"])

        if not data.get("online"):
            lines.append(f"🔴 **{server['name']}** — Offline or unreachable")
            continue

        count = data["player_count"]
        indicator = "🟢" if count >= PLAYER_THRESHOLD else "🟡"
        status = (
            f"{indicator} **{server['name']}** — "
            f"{count}/{data['max_players']} players | "
            f"Map: `{data['map']}`"
        )
        if data["players"]:
            status += f"\n> {', '.join(data['players'])}"

        lines.append(status)

    await interaction.followup.send("\n".join(lines))


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------

bot.run(DISCORD_TOKEN)
