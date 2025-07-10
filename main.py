import os
import discord
import logging
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from gtts import gTTS
import re
from pyt2s.services import stream_elements
import asyncio
from datetime import timedelta

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
    # prevents infinite loop of bot responding to itself,
    # accounts for if slash command is used (message becomes None)
    if message.author == bot.user or message is None:
        return

    vc = message.guild.voice_client

    if vc is not None:
        await generate_audio(vc, message, "")

    await bot.process_commands(message)

async def generate_audio(vc, message, voice):
    # if the bot is already playing a sound, cancel it
    #if vc.is_playing():
    #    vc.stop()

    # create sound file from text
    text = await prep_text(message)
    print(text)
    #sound = gTTS(text=text, lang='en-in')
    #sound.save("tts-audio.mp3")
    sound = stream_elements.requestTTS(text)
    with open("tts-audio.mp3", '+wb') as file:
        file.write(sound)

    # if the text is empty, don't play the audio
    if text.isspace():
        return

    vc.play(discord.FFmpegPCMAudio(executable="C:/ffmpeg/bin/ffmpeg.exe", source="tts-audio.mp3"))

async def prep_text(message):
    text = message.content

    # turns the long string of numbers from a mention into the actual display name
    for user in message.mentions:
        mention_pattern = f"<@!?{user.id}>"
        text = re.sub(mention_pattern, f"@ {user.display_name}", text)

    # removes urls
    text = re.sub(r'https?://\S+', '', text)

    # if previous message is sent by a different user, address the new user
    async for msg in message.channel.history(limit=2):
        if msg.id != message.id: # skips the first message
            text = await address_text(text, message, msg)

    return text

async def address_text(text, curr_msg, prev_msg):
    time_difference = curr_msg.created_at - prev_msg.created_at

    print(f"Time diff: {time_difference}")

    print(f"before curr check: {text}")
    # if a new user sends a message or if enough time has passed, address the user.
    if curr_msg.author != prev_msg.author or time_difference > timedelta(seconds=30):
        return f"{curr_msg.author.display_name} says, {text}"

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