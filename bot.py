import asyncio
import logging
import os
from threading import Thread

from dotenv import load_dotenv
from discord import Intents, Client, VoiceState
from flask import Flask

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise SystemExit('Missing DISCORD_TOKEN in .env')

WATCH_CHANNEL_NAME = 'THE REDEMPTION !'
FALLBACK_CHANNEL_NAME = 'CAMS OFF/ SS'
ASH_ROLE_NAME = "ASH's"
CHECK_DELAY_SECONDS = 2*60

pending_checks = {}
warned_users = set()
in_watch_members = set()

# logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

intents = Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True

client = Client(intents=intents)
app = Flask(__name__)


@app.route('/', methods=['GET'])
def health_check():
    return 'Bot is online'


def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)


def is_ash_member(member):
    return any(role.name == ASH_ROLE_NAME for role in member.roles)


def find_voice_channel(guild, name):
    return next(
        (channel for channel in guild.voice_channels if channel.name == name),
        None,
    )


async def send_dm(user, message):
    try:
        await user.send(message)
    except Exception:
        logging.exception('Warning: could not send DM to %s', user)


async def camera_check(member_id, guild_id):
    await asyncio.sleep(CHECK_DELAY_SECONDS)

    pending_checks.pop(member_id, None)

    guild = client.get_guild(guild_id)
    if guild is None:
        return

    member = guild.get_member(member_id)
    if member is None or member.voice is None:
        return

    if member.voice.channel and member.voice.channel.name == WATCH_CHANNEL_NAME and not member.voice.self_video:
        fallback = find_voice_channel(guild, FALLBACK_CHANNEL_NAME)
        if fallback is not None:
            try:
                await member.move_to(fallback, reason='Camera not enabled after 5 minutes')
                logging.info('Moved member %s (%s) to fallback %s because camera remained off', member.display_name, member.id, FALLBACK_CHANNEL_NAME)
                await send_dm(
                    member,
                    f'WELCOME!  CHAMP {member.display_name} to CAMS OFF/SS room !\n\n'
                    'CAM CHECK FAILED 😔💔\n'
                    'Omfoo you got yeeted straight into the CAMS OFF zone! Your camera decided to play hide and seek and showed up fashionably late... like, too late.\n\n'
                    'Sorry buddy but around here it\'s simple: NO CAM = NO REDEMPTION! 😈',
                )
            except Exception as exc:
                logging.exception('Error moving %s: %s', member, exc)
        else:
            logging.warning('Fallback channel not found: %s', FALLBACK_CHANNEL_NAME)


def schedule_check(member: 'discord.Member'):
    if member.id in pending_checks:
        return

    pending_checks[member.id] = asyncio.create_task(
        camera_check(member.id, member.guild.id)
    )


def cancel_check(member_id):
    task = pending_checks.pop(member_id, None)
    if task is not None:
        task.cancel()
    logging.debug('Cancelled check for member id %s', member_id)


@client.event
async def on_ready():
    print(f'Logged in as {client.user}')


@client.event
async def on_voice_state_update(member, before: VoiceState, after: VoiceState):
    # Normalize channel names
    before_name = before.channel.name if before.channel else None
    after_name = after.channel.name if after.channel else None

    logging.debug('Voice state update: user=%s id=%s before=%s after=%s camera_on=%s pending_exists=%s warned=%s in_watch=%s',
                  member.display_name, member.id, before_name, after_name, getattr(after, 'self_video', False),
                  member.id in pending_checks, member.id in warned_users, member.id in in_watch_members)

    # Only monitor members with the ASH role
    if not is_ash_member(member):
        if member.id in in_watch_members:
            in_watch_members.discard(member.id)
            warned_users.discard(member.id)
            cancel_check(member.id)
            logging.debug('Removed non-ASH member %s from watch tracking', member.id)
        return

    was_in_redeem = member.id in in_watch_members
    is_in_redeem = after.channel is not None and after.channel.name == WATCH_CHANNEL_NAME

    # Member just entered the watched channel
    if is_in_redeem and not was_in_redeem:
        in_watch_members.add(member.id)
        logging.info('Member %s (%s) entered %s', member.display_name, member.id, WATCH_CHANNEL_NAME)

        if not after.self_video:
            # Only send one warning per session (while in channel)
            if member.id not in warned_users:
                warned_users.add(member.id)
                logging.debug('Sending one-time warning DM to %s (%s)', member.display_name, member.id)
                await send_dm(
                    member,
                    """WHAT HAPPENS IN THE NEXT 2 MINUTES IF YOU DON’T TURN ON YOUR CAM?🤡

02:00 – Benefit of doubt activated 😌
“Maybe they’re fixing the camera…” (we’re trying very hard to stay delusional)

01:30 – Suspicion begins… 🤨
Are you attending the session or just farming attendance from another galaxy? 👽

01:00 – Reality check 💀
The admins have officially started whispering:
“Yeah… this one’s getting shifted.”

00:45 – Emergency phase 🚨
Your name slowly starts glowing on the “Potential Victims List''

00:30 – Final warning 😈
The Shift Button is being stared at aggressively.

00:15 – No cam? No mercy 💔
At this point, even your WIFi is begging you to stop embarrassing it.

00:10 – Admins cracking knuckles 💀
A relocation package to the CAMS OFF ZONE is being prepared.

00:05 – Last chance, champion 🫡
Open that camera or accept your cinematic downfall.

00:03 – Sad violin music plays 🎻

00:02 – The shifting finger is hovering…

00:01 – Congratulations! 🎉
You are now eligible for the “Invisible Participant of the Year” Award 👻

🚪 00:00 – AUTO SHIFTED 😈
Because here, NO CAM = NO REDEMPTION 💀""",
                )
            schedule_check(member)
        else:
            # Camera already on — ensure no pending checks
            cancel_check(member.id)
        return

    # Member left the watched channel
    if was_in_redeem and not is_in_redeem:
        in_watch_members.discard(member.id)
        warned_users.discard(member.id)
        cancel_check(member.id)
        logging.info('Member %s (%s) left %s — cleared session state', member.display_name, member.id, WATCH_CHANNEL_NAME)
        return

    # Member stayed in the watched channel (e.g., toggled camera)
    if is_in_redeem and was_in_redeem:
        if after.self_video:
            # Camera enabled — stop pending check but keep warned flag for session prevention
            cancel_check(member.id)
            logging.debug('Member %s enabled camera — cancelled pending check', member.id)
        elif not after.self_video and member.id not in pending_checks:
            # Camera turned off while staying in channel — do NOT re-warn, but ensure a check is scheduled
            logging.debug('Member %s remains without camera — scheduling check if none exists', member.id)
            schedule_check(member)


if __name__ == '__main__':
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    client.run(TOKEN)
