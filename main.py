import os, re, uuid, glob
import discord
import logging
import asyncio

from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from pyt2s.services import stream_elements
from datetime import timedelta

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w') # generates log file for each run

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

GUILD_ID = discord.Object(id=823035947083890709)

bot = commands.Bot(command_prefix='!', intents=intents)

message_queue = asyncio.Queue()
playback_task = None
in_generate_audio = False

commands_as_strs = ["!start", "!stop", "!voice",]

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

    msg_is_command = message.content in commands_as_strs

    if vc is not None and not msg_is_command:
        if message_queue.empty():
            await message_queue.put((vc, message, ""))
            asyncio.create_task(process_audio_queue())
        else:
            await message_queue.put((vc, message, ""))

    await bot.process_commands(message)

async def process_audio_queue():
    while not message_queue.empty():
        message_obj = message_queue._queue[0]
        await generate_audio(message_obj[0], message_obj[1], message_obj[2])
        await message_queue.get()

async def generate_audio(vc, message, voice):
    # create sound file from text
    global in_generate_audio
    in_generate_audio = True
    text = await prep_text(message)
    sound = stream_elements.requestTTS(text)

    # if the text is empty, don't play the audio
    if text.isspace():
        return

    filename = f"tts-{uuid.uuid4()}.mp3"
    with open(filename, '+wb') as file:
        file.write(sound)

    #waits until nothing is playing, just to be safe
    while vc.is_playing():
        await asyncio.sleep(.2)

    try:
        vc.play(discord.FFmpegPCMAudio(executable="C:/ffmpeg/bin/ffmpeg.exe", source=filename))
    except FileNotFoundError as e:
        print(f"Error with audio file: {e}")

    # waits until playback ends
    while vc.is_playing():
        await asyncio.sleep(.2)

    os.remove(filename)


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

    # if a new user sends a message or if enough time has passed, address the user.
    if curr_msg.author != prev_msg.author or time_difference > timedelta(seconds=30):
        return f"{curr_msg.author.display_name} says, {text}"

    return text

async def queue_to_string():
    q_str = ''
    if message_queue.empty():
        return q_str
    else:
        q_str += "Current queue contents:"
        for idx, item in enumerate(list(message_queue._queue)):
            q_str += f"{idx + 1}: message -> {item[1].content}\n"

@bot.command(name="print_queue")
async def print_queue(ctx):
    print(await queue_to_string())

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
    if ctx.voice_client is None:
        await ctx.send("I am already stopped!")

    vc = ctx.voice_client

    message_queue._queue.clear() # clear queue

    # waits for current message to finish playing before disconnecting it
    while vc.is_playing():
        await asyncio.sleep(.2)

    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()

@bot.tree.command(name="join", description="uhh", guild=GUILD_ID)
async def join(interaction: discord.Interaction):
    user = interaction.user

    voice_channel = user.voice.channel

    if voice_channel is None:
        await user.send("Please enter a vc.")
        return

@bot.tree.command(name="test", description="test i guess", guild=GUILD_ID)
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("test message")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)