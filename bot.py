import asyncio
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
CHECK_DELAY_SECONDS = 5 * 60

pending_checks = {}

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
        print(f'Warning: could not send DM to {user}')


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
                await send_dm(
                    member,
                    f'WELCOME!  CHAMP {member.display_name}  to THE REDEMPTION !\n\n'
                    'CAM CHECK FAILED 😔💔\n'
                    'Omfoo you got yeeted straight into the CAMS OFF zone! Your camera decided to play hide and seek and showed up fashionably late... like, too late.\n\n'
                    'Sorry buddy but around here it\'s simple: NO CAM = NO REDEMPTION! 😈',
                )
            except Exception as exc:
                print(f'Error moving {member}: {exc}')
        else:
            print(f'Fallback channel not found: {FALLBACK_CHANNEL_NAME}')


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


@client.event
async def on_ready():
    print(f'Logged in as {client.user}')


@client.event
async def on_voice_state_update(member, before: VoiceState, after: VoiceState):
    was_in_redeem = before.channel is not None and before.channel.name == WATCH_CHANNEL_NAME
    is_in_redeem = after.channel is not None and after.channel.name == WATCH_CHANNEL_NAME

    if not is_ash_member(member):
        if was_in_redeem or is_in_redeem:
            cancel_check(member.id)
        return

    if is_in_redeem and not was_in_redeem:
        if not after.self_video:
            schedule_check(member)
        else:
            cancel_check(member.id)
        return

    if was_in_redeem and not is_in_redeem:
        cancel_check(member.id)
        return

    if is_in_redeem and was_in_redeem:
        if after.self_video:
            cancel_check(member.id)
        elif not after.self_video and member.id not in pending_checks:
            schedule_check(member)


if __name__ == '__main__':
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    client.run(TOKEN)
