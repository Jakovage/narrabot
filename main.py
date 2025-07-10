import os
import discord
import logging
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from gtts import gTTS
import re

import asyncio

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

GUILD_ID = discord.Object(id=823035947083890709)

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"Started NarraBot")

    # syncs slash commands with discord
    try:
        guild = discord.Object(id=823035947083890709)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} command(s) to guild {guild.id}")

    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.event
async def on_message(message):
    # prevents infinite loop of bot responding to itself
    if message.author == bot.user:
        return

    vc = message.guild.voice_client

    if vc is not None:
        await generate_audio(vc, message)

    await bot.process_commands(message)

async def generate_audio(vc, message):
    # if the bot is already playing a sound, cancel it
    if vc.is_playing():
        vc.stop()

    # create sound file from text
    text = await fix_text(message)
    print(text)
    sound = gTTS(text=text, lang='en')
    sound.save("tts-audio.mp3")

    # if the text is empty, don't play the audio
    if text.isspace():
        return

    vc.play(discord.FFmpegPCMAudio(executable="C:/ffmpeg/bin/ffmpeg.exe", source="tts-audio.mp3"))

async def fix_text(message):
    text = message.content
    # turns the long string of numbers from a mention into the actual display name
    for user in message.mentions:
        mention_pattern = f"<@!?{user.id}>"
        text = re.sub(mention_pattern, f"@ {user.display_name}", text)
    return text

@bot.command(name="start")
async def start(ctx):
    user = ctx.author

    # if user is not in voice chat, do nothing
    if user.voice is None:
        await ctx.send("please join a vc")
        return

    voice_channel = user.voice.channel

    # reuse existing voice client if already connected
    vc = ctx.voice_client

    # if bot hasn't joined a vc yet, join the user's vc.
    # if the bot is in a vc but not the same as the calling user, move calls.
    if vc is None:
        vc = await voice_channel.connect()
    elif vc.channel != voice_channel:
        await vc.move_to(voice_channel)

@bot.command(name="stop")
async def stop(ctx):
    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()

@bot.tree.command(name="join", description="uhh", guild=GUILD_ID)
async def join(interaction: discord.Interaction):
    user = interaction.user

    voice_channel = user.voice.channel

    if voice_channel is None:
        print("bro aint in a vc")
        await user.send("Please enter a vc.")
        return

@bot.tree.command(name="test", description="test i guess", guild=GUILD_ID)
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("test message")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)