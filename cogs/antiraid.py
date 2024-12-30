import re
import os
import discord

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from discord import app_commands, Guild
from discord.ext import commands

load_dotenv()
MESSAGE_THRESHOLD = 5 # number of messages
TIME_WINDOW = 10 # in seconds
MUTE_COOLDOWN = 10 # in minutes

message_cache = defaultdict(list)
warned_users = {}
cooldown_cache = {}

class AntiRaid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.name_regex = "^(?![._])(?!.*[._]$)(?!.*[._]{2,})(?!.*[._]\d+)(?!.*\d+[._])([a-zA-Z]+([._][a-zA-Z]+)*)$"
        self.guild = None
        self.muted_channel = None
        self.muted_role = None
        self.moderator_role = None

    async def initialize(self):
        self.guild: discord.Guild = await self.bot.fetch_guild(int(os.getenv("GUILD_ID")))
        self.muted_channel: discord.TextChannel = await self.guild.fetch_channel(int(os.getenv("MUTED_CHANNEL_ID")))
        self.muted_role: discord.Role = self.guild.get_role(int(os.getenv("MUTED_ROLE_ID")))


    async def automute(self, member: discord.Member, reason: str):
        await member.add_roles(self.muted_role)
        await self.muted_channel.send(f"Hi there {member.mention}! You have been muted for {reason}")


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        time_dif: timedelta = datetime.now(timezone.utc) - member.created_at
        emoji = "<:Unusual_Account_Activity:1223677920065749043>"
        if not member.avatar:
            await self.automute(member,
                                reason="having a default avatar. "
                                    "Although this by itself is not suspicious, "
                                    "we do get a lot of spammer accounts with no pfp, "
                                    f"this is just a precaution, a <@&{int(os.getenv('MODERATOR_ROLE_ID'))}> "
                                    f"will be here soon to manually check.")

        elif not re.search(self.name_regex, member.name):
            await self.automute(member,
                                reason="having a common name structure. "
                                    "Your name is in a common format used by many "
                                    "scammers and spammers. You are not being accused of anything, "
                                    "this is just a precaution to preserve the safety of our server, "
                                    f"a <@&{int(os.getenv('MODERATOR_ROLE_ID'))}> will be here soon to "
                                    f"manually check.")

        elif time_dif.days < 7:
            await self.automute(member,
                                reason="having a too new account. "
                                    "You are not being accused of anything, "
                                    "this is just a precaution to preserve the safety of our server, "
                                    f"a <@&{int(os.getenv('MODERATOR_ROLE_ID'))}> will be here soon to "
                                    "manually check.")

        elif discord.PublicUserFlags.spammer in member.public_flags:
            await self.automute(member,
                                reason="having a spammer flag on your account. "
                                    "Discord has flagged your account as possibly being a spam account, "
                                    f"commonly represented by this image {emoji}, please answer as to why "
                                    "within a few hours or you may be kicked, please ping a "
                                    f"<@&{int(os.getenv('MODERATOR_ROLE_ID'))}> and one will be "
                                    "here shortly")



    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user: # Stops the bot from getting muted
            return
        elif isinstance(message.author, discord.User): # If a member is not in the server
            return
        elif isinstance(message.author, discord.Member) and message.author.bot: # If the member is a bot
            return
        if self.moderator_role in message.author.roles: # If a member is a moderator
            return
        if message.channel.category_id == 958386788085407794: # Admin chats
            return
        if isinstance(message.channel, discord.DMChannel): # Dms
            return

        now = datetime.now(timezone.utc)
        user_id = message.author.id

        if user_id not in message_cache:
            message_cache[user_id] = []
        message_cache[user_id].append(now)

        message_cache[user_id] = [
            timestamp for timestamp in message_cache[user_id]
            if now - timestamp < timedelta(seconds=TIME_WINDOW)
        ]

        if len(message_cache[user_id]) >= MESSAGE_THRESHOLD:
            if user_id in cooldown_cache and now - cooldown_cache[user_id] < timedelta(minutes=MUTE_COOLDOWN):
                return

            if user_id not in warned_users:
                warned_users[user_id] = True
                await message.channel.send(
                    f"{message.author.mention} you are spamming. "
                    f"Please slow down or you will be muted.")
                await message.author.timeout(timedelta(seconds=10), reason="spamming")

            else:
                await self.automute(message.author,
                            reason=f"spamming.\n<@&{int(os.getenv('MODERATOR_ROLE_ID'))}>"
                                    )

                message_cache[user_id] = []
                warned_users.pop(user_id, None)
                cooldown_cache[user_id] = now

        if len(message.mentions) >= 4:
            await message.channel.send("Please stop spamming mentions or you may be muted")



async def setup(bot):
    anti_raid = AntiRaid(bot)
    await anti_raid.initialize()
    await bot.add_cog(anti_raid)
