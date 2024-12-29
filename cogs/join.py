import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()

class Join(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = self.bot.get_channel(int(os.getenv('UNVERIFIED_CHANNEL_ID')))
        await channel.send(
            f"Hi there {member.mention}! Thanks for joining the server!\n"
            f"If you react to this message in <#958385865372098610>  "
            f"you can see all of the channels we have to offer! "
            f"https://discord.com/channels/958378689169621012/958385865372098610/958427189915820042"
        )


async def setup(bot):
    await bot.add_cog(Join(bot))