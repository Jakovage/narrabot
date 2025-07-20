import discord
import asyncio

class AudioTask:
    def __init__(self, bot_vc: discord.VoiceProtocol, message: discord.Message):
        self.bot_vc = bot_vc
        self.message = message

class Guild:
    def __init__(self, guild_id: int, message_queue: asyncio.Queue, curr_channel: discord.TextChannel, curr_voice: str):
        self.guild_id = guild_id # the guild id
        self.message_queue = message_queue # the queue of messages for this guild
        self.curr_channel = curr_channel # the text channel NarraBot was called from (the one being narrated)
        self.curr_voice = curr_voice # the current voice that NarraBot is using to narrate
