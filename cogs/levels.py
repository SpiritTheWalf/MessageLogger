import os
import json
import random
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from db import Level, SessionLocal, engine # Assuming db.py contains the database setup

class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_message_time = {}  # A dictionary to store the last message time for cooldown
        self.channel_id = int(os.getenv("BOT_CID"))

    # Function to get user data from the database
    async def get_user_data(self, guild_id, user_id):
        async with SessionLocal() as session:
            stmt = select(Level).filter(Level.guild_id == guild_id, Level.user_id == user_id)
            result = await session.execute(stmt)
            user_data = result.scalars().first()

            # If the user doesn't exist, create a new entry with default values
            if not user_data:
                user_data = Level(guild_id=guild_id, user_id=user_id, xp=0, level=1)
                session.add(user_data)
                await session.commit()
            return user_data

    # Function to update user data (XP and level)
    async def update_user_data(self, guild_id, user_id, xp, level):
        async with SessionLocal() as session:
            user_data = await self.get_user_data(guild_id, user_id)
            user_data.xp = xp
            user_data.level = level
            session.add(user_data)
            await session.commit()

    # Function to calculate level from XP (example formula)
    def calculate_level(self, xp):
        # Example formula for level calculation
        return int((xp / 100) ** 0.5) + 1

    # Level up check and XP addition
    async def level_up_check(self, user_data, xp_to_add):
        new_xp = user_data.xp + xp_to_add
        new_level = self.calculate_level(new_xp)

        if new_level > user_data.level:  # Level up condition
            # User leveled up, update their data and send a message
            await self.update_user_data(user_data.guild_id, user_data.user_id, new_xp, new_level)
            return True, new_level, xp_to_add
        else:
            # No level up, just update XP
            await self.update_user_data(user_data.guild_id, user_data.user_id, new_xp, user_data.level)
            return False, user_data.level, xp_to_add

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:  # Ignore bot messages
            return

        # Check if the user is on cooldown (1 minute)
        current_time = datetime.utcnow()
        user_id = message.author.id
        guild_id = message.guild.id

        # Fetch the last time the user earned XP
        last_time = self.last_message_time.get(user_id)

        if last_time and current_time - last_time < timedelta(minutes=1):
            # If within cooldown, return
            return

        # Update last message time
        self.last_message_time[user_id] = current_time

        # Get current user data (XP, level)
        user_data = await self.get_user_data(guild_id, user_id)

        # Add XP (between 15 and 25)
        xp_to_add = random.randint(15, 25)

        # Check if the user leveled up and return new level and XP
        leveled_up, new_level, xp_to_add = await self.level_up_check(user_data, xp_to_add)

        if leveled_up:
            # Send a level-up message only if the user leveled up
            embed = discord.Embed(
                title=f"Congratulations {message.author.name}!",
                description=f"You have leveled up!",
                color=discord.Color.green()  # You can change this to any color you prefer
            )
            embed.add_field(name="New Level", value=f"Level {new_level}", inline=False)
            embed.add_field(name="XP Gained", value=f"+{xp_to_add} XP", inline=False)
            await self.bot.get_channel(self.channel_id).send(embed=embed)


    @commands.command()
    async def level(self, ctx, user: discord.Member = None):
        """Check the user's current level"""
        if user is None:
            user = ctx.author

        user_data = await self.get_user_data(ctx.guild.id, user.id)

        # Embed for the level check
        embed = discord.Embed(
            title=f"{user.name}'s Level",
            description=f"Here are your current stats:",
            color=discord.Color.blue()  # You can change this to any color you prefer
        )
        embed.add_field(name="Level", value=f"Level {user_data.level}", inline=False)
        embed.add_field(name="XP", value=f"{user_data.xp} XP", inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def leaderboard(self, ctx):
        """Display the leaderboard for the current guild"""
        guild_id = ctx.guild.id

        async with SessionLocal() as session:
            # Fetch the top 10 users in the guild, ordered by XP descending
            stmt = (
                select(Level)
                .filter(Level.guild_id == guild_id)
                .order_by(Level.xp.desc())
                .limit(10)
            )
            result = await session.execute(stmt)
            top_users = result.scalars().all()

        if not top_users:
            await ctx.send("No leaderboard data available yet!")
            return

        # Build the embed for the leaderboard
        embed = discord.Embed(
            title=f"Leaderboard for {ctx.guild.name}",
            description="Top 10 Users by XP",
            color=discord.Color.gold()
        )

        for idx, user in enumerate(top_users, start=1):
            member = ctx.guild.get_member(user.user_id)  # Get the Discord member object
            username = member.mention if member else "Unknown User"
            embed.add_field(
                name="",
                value=f"#{idx}: {username} | Level: {user.level} | XP: {user.xp}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)  # Restrict to administrators (modify as needed)
    async def add_xp(self, ctx, member: discord.Member, xp: int):
        """Manually add XP to a user."""
        if xp <= 0:
            await ctx.send("XP to add must be greater than zero.")
            return

        guild_id = ctx.guild.id
        user_id = member.id

        async with SessionLocal() as session:
            # Retrieve or create the user's record
            stmt = select(Level).filter_by(guild_id=guild_id, user_id=user_id)
            result = await session.execute(stmt)
            user_data = result.scalars().first()

            if user_data:
                user_data.xp += xp
            else:
                user_data = Level(guild_id=guild_id, user_id=user_id, xp=xp, level=0)
                session.add(user_data)

            # Update the level based on the new XP
            user_data.level = self.calculate_level(user_data.xp)

            await session.commit()

        await ctx.send(f"Added {xp} XP to {member.display_name}. They are now Level {user_data.level}!")

    @commands.command()
    @commands.has_permissions(administrator=True)  # Restrict to administrators (modify as needed)
    async def remove_xp(self, ctx, member: discord.Member, xp: int):
        """Manually remove XP from a user."""
        if xp <= 0:
            await ctx.send("XP to remove must be greater than zero.")
            return

        guild_id = ctx.guild.id
        user_id = member.id

        async with SessionLocal() as session:
            # Retrieve the user's record
            stmt = select(Level).filter_by(guild_id=guild_id, user_id=user_id)
            result = await session.execute(stmt)
            user_data = result.scalars().first()

            if not user_data:
                await ctx.send(f"{member.display_name} has no XP record.")
                return

            # Deduct XP and ensure it doesn't drop below 0
            user_data.xp = max(0, user_data.xp - xp)
            user_data.level = self.calculate_level(user_data.xp)  # Recalculate level

            await session.commit()

        await ctx.send(f"Removed {xp} XP from {member.display_name}. They are now Level {user_data.level}!")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def import_levels(self, ctx):
        """
        Import XP from a Mee6 JSON file provided as an attachment, recalculate levels, and overwrite existing data.
        """
        if not ctx.message.attachments:
            await ctx.send("Please attach a Mee6 JSON file to this command.")
            return

        # Get the attached file
        attachment = ctx.message.attachments[0]

        # Ensure it's a JSON file
        if not attachment.filename.endswith('.json'):
            await ctx.send("The attached file must be a JSON file.")
            return

        try:
            # Read the JSON file from the attachment
            data = await attachment.read()
            mee6_data = json.loads(data)

            guild_id = ctx.guild.id  # Current guild's ID

            async with SessionLocal() as session:
                # Clear all existing data for this guild
                await session.execute(delete(Level).filter_by(guild_id=guild_id))

                # Import new data
                for user_data in mee6_data:
                    # Ensure the data belongs to the current guild
                    if int(user_data.get("guild_id", 0)) != guild_id:
                        continue

                    user_id = int(user_data["id"])
                    xp = user_data.get("xp", 0)

                    # Calculate the level from XP using your formula
                    level = self.calculate_level(xp)

                    # Add the user to the database
                    new_user = Level(
                        guild_id=guild_id,
                        user_id=user_id,
                        xp=xp,
                        level=level
                    )
                    session.add(new_user)

                # Commit changes to the database
                await session.commit()

            await ctx.send("Level data imported successfully! Existing data has been overwritten.")

        except json.JSONDecodeError:
            await ctx.send("Error decoding the JSON file. Please ensure it is formatted correctly.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    def calculate_level(self, xp: int) -> int:
        """
        Calculate the level based on XP using the leveling formula.
        """
        level = 0
        while xp >= self.xp_for_next_level(level):
            xp -= self.xp_for_next_level(level)
            level += 1
        return level

    def xp_for_next_level(self, level: int) -> int:
        """
        Calculate the XP required for the next level.
        Adjust the formula based on your bot's leveling system.
        """
        return 5 * (level ** 2) + 50 * level + 100


# Setup the cog
async def setup(bot):
    await bot.add_cog(LevelingCog(bot))
