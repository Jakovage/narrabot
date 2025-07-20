import os, re, uuid, glob, json
from os import mkdir

import discord
import logging
import asyncio
import voices

from discord.ext import commands
from discord import app_commands, ClientException
from dotenv import load_dotenv
from pyt2s.services import stream_elements
from datetime import timedelta
from guild_state import Guild, AudioTask
from pathlib import Path
from storage import save_guilds, load_guilds

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w') # generates log file for each run

ROOT_DIR = Path(__file__).resolve().parent # narrabot/
AUDIO_DIR = ROOT_DIR / 'guild_audio' # narrabot/guild_audio
STATE_FILE = Path("guild_config.json")
FFMPEG_DIR = "C:/ffmpeg/bin/ffmpeg.exe"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

guilds = load_guilds() # {guild_id : Guild Object}, loads guild objects from

DEFAULT_VOICE = "Joanna"
voice_choices = [
    app_commands.Choice(name=voice.name, value=voice.value)
    for voice in voices.Voice
]

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_guild_join(guild):
    guilds[guild.id] = Guild(guild.id, asyncio.Queue(), None, DEFAULT_VOICE)
    save_guilds(guilds)
    mkdir(guild_audio_dir(guild.id))

@bot.event
async def on_guild_remove(guild):
    del guilds[guild.id]
    save_guilds(guilds)
    try:
        os.rmdir(guild_audio_dir(guild.id))
        print(f"removed audio directory: {guild_audio_dir(guild.id)}")
    except OSError:
        print(f"Error with deleting audio directory upon removal of NarraBot of guild {guild_audio_dir(guild.id)}")

def guild_audio_dir(guild_id: int) -> Path:
    return AUDIO_DIR / str(guild_id)

@bot.event
async def on_ready():
    print(f"Started NarraBot")

    # syncs slash commands with discord
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} global commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.event
async def on_message(message):
    # prevents infinite loop of bot responding to itself
    if message.author == bot.user or message is None:
        return

    bot_vc = message.guild.voice_client

    guild = guilds[message.guild.id]
    audio_task = AudioTask(bot_vc, message)

    is_right_channel = guild.curr_channel == message.channel

    # if the queue is empty and a message is sent, send it to the queue and begin processing it
    # otherwise, send a consecutive message to the queue (where it will get processed)
    if bot_vc is not None and is_right_channel:
        if guild.message_queue.empty():
            await guild.message_queue.put(audio_task)
            asyncio.create_task(process_audio_queue(guild))
        else:
            await guild.message_queue.put(audio_task)

    await bot.process_commands(message)

@bot.tree.command(name="start", description="Joins the voice channel your in and automatically starts narrating!")
async def start(interaction: discord.Interaction):
    user = interaction.user

    user_vc = user.voice.channel
    bot_vc = interaction.guild.voice_client

    # if user is not in voice chat, do nothing
    current_text_channel = guilds[interaction.guild.id].curr_channel

    # won't start NarraBot if user isn't in a vc
    if user.voice is None:
        await interaction.response.send_message("please join a voice channel")

    # if bot hasn't been started, join the user's vc and narrate the next channel it was called from
    elif bot_vc is None:
        await user_vc.connect()
        await interaction.response.send_message(
            f"Starting narration of text channel: {interaction.channel.name}"
        )

    # if bot is actively narrating user calls start from a different text channel and different vc
    elif interaction.channel != current_text_channel and bot_vc.channel != user_vc:
        await interaction.response.send_message(
            f"Changing narration to text channel: {interaction.channel.name}\n"
            f"moving Narrabot to voice channel: {user_vc.name}"
        )
        await bot_vc.move_to(user_vc)

    # if bot is actively narrating and user calls start from a different text channel
    elif interaction.channel != current_text_channel:
        await interaction.response.send_message(
            f"Changing narration to text channel: {interaction.channel.name}\n"
        )

    # if bot is actively narrating and user calls from a different vc
    elif bot_vc.channel != user_vc:
        await interaction.response.send_message(
            f"Moving NarraBot to voice channel: {user_vc.name}"
        )
        await bot_vc.move_to(user_vc)

    # user_vc == bot_vc.channel and text channel unchanged
    else:
        await interaction.response.send_message(
            f"Already narrating: {interaction.channel.name}"
        )

    # updating the guild object's "current channel" to be the text channel it was
    guilds[interaction.guild.id].curr_channel = interaction.channel

@bot.tree.command(name="stop", description="Stop narration and leave voice channel")
async def stop(interaction: discord.Interaction):
    bot_vc = interaction.guild.voice_client
    await interaction.response.send_message("Stopping narration and leaving voice channel.")

    if bot_vc is None:
        await interaction.response.send_message("I am already stopped!")

    guilds[interaction.guild.id].message_queue._queue.clear() # clears the guild's audio queue, preventing it from finishing

    # waits for current message to finish playing before disconnecting it
    while bot_vc.is_playing():
        await asyncio.sleep(.2)

    await asyncio.sleep(1) # extra second before deleting all mp3 in case there's some sort of latency

    # cleans any remaining mp3 files. if there ARE any remaining, it is due to an error (likely due to spam)
    await delete_all_mp3()

    if bot_vc is not None:
        await bot_vc.disconnect()

    guilds[interaction.guild.id].curr_channel = None

@bot.tree.command(name="voice", description="Change the voice of NarraBot")
@app_commands.describe(voice="Choose the new voice")
@app_commands.choices(voice=voice_choices)
async def voice(interaction: discord.Interaction, voice: app_commands.Choice[str]):
    guilds[interaction.guild.id].curr_voice = voice.value
    await interaction.response.send_message(f"Voice changed to {voice.name}")

async def process_audio_queue(guild):
    while not guild.message_queue.empty():
        audio_task = guild.message_queue._queue[0] # equivalent to a peek() operation to get the next audio task
        await generate_audio(audio_task.bot_vc, audio_task.message, guild.curr_voice)
        await guild.message_queue.get() # removes the audio message object from the queue, then goes to the next one

async def generate_audio(bot_vc, message, voice):
    # create sound file from text
    text = await prep_text(message)
    sound = stream_elements.requestTTS(text, voice)

    # if the text is empty, don't play the audio
    if text.isspace():
        return

    # file: /narrabot/guild_audio/(guild_id)/tts-uuid.mp3
    filename = AUDIO_DIR / str(message.guild.id) / f"tts-{uuid.uuid4()}.mp3"
    with open(filename, '+wb') as file:
        file.write(sound)

    print(filename)

    # waits until nothing is playing, just to be safe
    while bot_vc.is_playing():
        await asyncio.sleep(.2)

    try:
        bot_vc.play(discord.FFmpegPCMAudio(executable=FFMPEG_DIR, source=filename))
    except FileNotFoundError as e:
        print(f"Error with audio file: {e}")
    except ClientException as e:
        print(f"Error with playing audio. likely caused by spam. Error: {e}")

    # waits until playback ends
    while bot_vc.is_playing():
        await asyncio.sleep(.2)

    try:
        os.remove(filename)
    except OSError as e:
        print(f"Something went wrong while deleting temporary file. Likely caused by spam. Error: {e}")

async def prep_text(message):
    text = message.content

    # turns the long string of numbers from a mention into the actual display name
    for user in message.mentions:
        mention_pattern = f"<@!?{user.id}>"
        text = re.sub(mention_pattern, f"@ {user.display_name}", text)

    # removes urls
    text = re.sub(r'https?://\S+', 'Link', text)

    # if previous message is sent by a different user, address the new user
    async for msg in message.channel.history(limit=2):
        if msg.id != message.id: # skips the first message
            text = await address_text(text, message, msg)

    return text

async def address_text(text, curr_msg, prev_msg):
    time_difference = curr_msg.created_at - prev_msg.created_at

    # if a new user sends a message or if enough time has passed, address the user.
    if curr_msg.author != prev_msg.author or time_difference > timedelta(seconds=30):
        return f"{curr_msg.author.display_name} says, {text}"

    return text

# removes any temporary audio files in case one is somehow missed
async def delete_all_mp3():
    for file in glob.glob("*.mp3"):
        try:
            os.remove(file)
        except OSError:
            print("Something went wrong while clearing all leftover temporary audio files. Likely caused by spam.")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)