import os, re, uuid, glob
import discord
import logging
import asyncio

from discord.ext import commands
from discord import app_commands, ClientException
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

# these are things i'm going to have to change when adding to multiple servers.
message_queue = asyncio.Queue()
current_channel = None
# list of all voices
voice_choices = [
    app_commands.Choice(name=voice.name, value=voice.value)
    for voice in list(stream_elements.Voice)[1:25]
]
active_voice = "Brian" # an arbitrarily chosen default voice

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

    is_right_channel = current_channel == message.channel

    # if the queue is empty and a message is sent, send it to the queue and begin processing it
    # otherwise, send a consecutive message to the queue (where it will get processed)
    if vc is not None and is_right_channel:
        if message_queue.empty():
            await message_queue.put((vc, message, active_voice))
            asyncio.create_task(process_audio_queue())
        else:
            await message_queue.put((vc, message, active_voice))

    await bot.process_commands(message)

@bot.tree.command(name="start", description="Joins the voice channel your in and automatically starts narrating!", guild=GUILD_ID)
async def start(interaction: discord.Interaction):
    user = interaction.user

    user_vc = user.voice.channel
    bot_vc = interaction.guild.voice_client

    # if user is not in voice chat, do nothing

    global current_channel

    if user.voice is None:
        await interaction.response.send_message("please join a voice channel")

    elif bot_vc is None:
        await user_vc.connect()
        await interaction.response.send_message(
            f"Starting narration of text channel: {interaction.channel.name}"
        )

    elif interaction.channel != current_channel and bot_vc.channel != user_vc:
        await interaction.response.send_message(
            f"Changing narration to text channel: {interaction.channel.name}\n"
            f"moving Narrabot to voice channel: {user_vc.name}"
        )
        await bot_vc.move_to(user_vc)

    elif interaction.channel != current_channel:
        await interaction.response.send_message(
            f"Changing narration to text channel: {interaction.channel.name}\n"
        )

    elif bot_vc.channel != user_vc:
        await interaction.response.send_message(
            f"Moving NarraBot to voice channel: {user_vc.name}"
        )
        await bot_vc.move_to(user_vc)

    else: # user_vc == bot_vc.channel and text channel unchanged
        await interaction.response.send_message(
            f"Already narrating: {interaction.channel.name}"
        )

    current_channel = interaction.channel

@bot.tree.command(name="stop", description="Stop narration and leave voice channel", guild=GUILD_ID)
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    await interaction.response.send_message("Stopping narration and leaving voice channel.")

    if vc is None:
        await interaction.response.send_message("I am already stopped!")

    message_queue._queue.clear()

    # waits for current message to finish playing before disconnecting it
    while vc.is_playing():
        await asyncio.sleep(.2)

    await asyncio.sleep(1)

    await delete_all_mp3()

    if vc is not None:
        await vc.disconnect()

    global current_channel
    current_channel = None

@bot.tree.command(name="voice", description="Change the voice of NarraBot", guild=GUILD_ID)
@app_commands.describe(voice="Choose the new voice")
@app_commands.choices(voice=voice_choices)
async def voice(interaction: discord.Interaction, voice: app_commands.Choice[str]):
    global active_voice
    active_voice = voice.value
    await interaction.response.send_message(f"Voice changed to {voice.name}")

async def process_audio_queue():
    while not message_queue.empty():
        message_obj = message_queue._queue[0]
        await generate_audio(message_obj[0], message_obj[1], message_obj[2])
        await message_queue.get()

async def generate_audio(vc, message, voice):
    # create sound file from text
    text = await prep_text(message)
    sound = stream_elements.requestTTS(text, voice)

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
    except ClientException as e:
        print(f"Error with playing audio. likely caused by spam. Error: {e}")

    # waits until playback ends
    while vc.is_playing():
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