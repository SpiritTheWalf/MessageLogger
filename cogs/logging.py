import discord
import os
from discord.ext import commands
from datetime import datetime, timezone

class ReactionLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stats = 0
        self.channel_id = int(os.getenv("CHNL_ID"))

    @staticmethod
    def create_embed(action, reaction: discord.Reaction, user: discord.User) -> discord.Embed:
        embed = discord.Embed(
            title=f"Reaction {action}",
            description=f"{user.mention} {'added' if action == 'added' else 'removed'} a reaction",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Emoji", value=str(reaction.emoji), inline=True)
        embed.add_field(name="Message", value=f"[Jump to Message]({reaction.message.jump_url})", inline=True)
        embed.add_field(name="Channel", value=reaction.message.channel.mention, inline=True)
        embed.set_footer(text=f"User: {user.name} (ID: {user.id})")
        return embed

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        if message.content == self.bot.user.mention:
            await message.reply("I'm just logging reactions, nothing else :3\n-# Coded by SpiritTheWalf",
                                mention_author=False)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):
        channel = self.bot.get_channel(self.channel_id)
        embed = self.create_embed("added", reaction, user)
        await channel.send(embed=embed)
        self.stats += 1

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.Member):
        channel = self.bot.get_channel(self.channel_id)
        embed = self.create_embed("removed", reaction, user)
        await channel.send(embed=embed)
        self.stats += 1

    @commands.command(name="stats")
    async def stats(self, ctx):
        await ctx.reply(f"I have logged {self.stats} reactions since last restart!", mention_author=False)


async def setup(bot):
    await bot.add_cog(ReactionLogger(bot))
