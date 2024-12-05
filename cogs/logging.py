from cgitb import handler

import discord
import os

from aiohttp import payload
from discord.ext import commands
from datetime import datetime, timezone

class ReactionLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stats = 0
        self.channel_id = int(os.getenv('CHNL_ID'))
        self.reactions = []

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Triggered when a reaction is added."""
        reaction_data = {
            "emoji": payload.emoji,
            "user_id": payload.user_id,
            "guild_id": payload.guild_id,
            "channel_id": payload.channel_id,
            "message_id": payload.message_id,
            "timestamp": datetime.now(timezone.utc).strftime('%m-%d %H:%M:%S'),
            "action": "added"
        }
        self.reactions.append(reaction_data)

        # Automatically send reactions if the list reaches 50
        if len(self.reactions) >= 25:
            await self.handle_reactions()

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Triggered when a reaction is removed."""
        reaction_data = {
            "emoji": payload.emoji,
            "user_id": payload.user_id,
            "guild_id": payload.guild_id,
            "channel_id": payload.channel_id,
            "message_id": payload.message_id,
            "timestamp": datetime.now(timezone.utc).strftime('%m-%d %H:%M:%S'),
            "action": "removed"
        }
        self.reactions.append(reaction_data)
        if len(self.reactions) >= 25:
            await self.handle_reactions()

    @commands.Cog.listener()
    @commands.cooldown(1, 10.0 , commands.BucketType.user)
    async def on_message(self, message: discord.Message):
        if message.content.startswith("<@1311839620161601546>"):
            await message.reply("I log reactions, nothing else ~~yet~~ :3\n"
                                "-# Coded by SpiritTheWalf", mention_author=False)

    async def compile_footer_data(self):
        footer_data = ""
        for reaction in self.reactions:
            if isinstance(reaction["emoji"], discord.PartialEmoji) and reaction["emoji"].is_custom_emoji():
                emoji = f"<:{reaction['emoji'].name}:{reaction['emoji'].id}>"
            else:
                emoji = reaction["emoji"].name

            user = self.bot.get_user(reaction["user_id"])
            if user:
                user_name = user.name
            else:
                user_name = "Unknown User"

            footer_data += (
                f"Reaction {reaction['action']} | "
                f"User: {user_name} | "
                f"Emoji: {emoji} | "
                f"Timestamp: {reaction['timestamp']}\n"
            )

        return footer_data

    async def handle_reactions(self):
        embed = discord.Embed(title="Reactions logged")
        channel = self.bot.get_channel(self.channel_id)
        footer = await self.compile_footer_data()
        embed.description = footer
        self.reactions.clear()
        await channel.send(embed=embed)

    @commands.command(name="stats")
    @commands.has_permissions(administrator=True)
    async def stats(self, ctx):
        """Send the number of tracked reactions so far."""
        await ctx.reply(f"I have logged {len(self.reactions)} reactions since last restart!", mention_author=False)

    @commands.command(name="send_reactions")
    @commands.has_permissions(administrator=True)
    async def send_reactions(self, ctx):
        if self.reactions:
            await self.handle_reactions()
        else:
            await ctx.send("No reactions logged yet")


async def setup(bot):
    await bot.add_cog(ReactionLogger(bot))