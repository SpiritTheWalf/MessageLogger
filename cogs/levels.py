import os
import json
import random
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import asyncio
from sqlalchemy import delete, True_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from db import Level, SessionLocal, engine # Assuming db.py contains the database setup

class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_message_time = {}  # A dictionary to store the last message time for cooldown
        self.channel_id = int(os.getenv("BOT_CID"))

    @staticmethod
    async def get_user_data(guild_id, user_id):
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
    @staticmethod
    def calculate_level(xp):
        # Example formula for level calculation
        return int((xp / 100) ** 0.5) + 1

    async def level_up_check(self, user_data, xp_to_add):
        """
        Check if the user levels up and update their XP and level.
        Handles cases where the user skips multiple levels.
        """
        new_xp = user_data.xp + xp_to_add
        current_level = user_data.level

        # Calculate the new level iteratively to handle multiple level-ups
        new_level = current_level
        while new_xp >= self.xp_for_level(new_level + 1):
            new_level += 1

        # Update user data with the new XP and level
        await self.update_user_data(user_data.guild_id, user_data.user_id, new_xp, new_level)

        # Check if a level-up occurred
        if new_level > current_level:
            return True, new_level, xp_to_add
        return False, current_level, xp_to_add

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:  # Ignore bot messages
            return

        # Check if the user is on cooldown (1 minute)
        current_time = datetime.now(timezone.utc)
        user_id = message.author.id
        guild_id = message.guild.id

        last_time = self.last_message_time.get(user_id)

        if last_time and current_time - last_time < timedelta(minutes=1):
            return  # User is still on cooldown

        # Update last message time
        self.last_message_time[user_id] = current_time

        # Get current user data
        user_data = await self.get_user_data(guild_id, user_id)

        # Add XP (between 15 and 25)
        xp_to_add = random.randint(15, 25)

        # Check for level-up
        leveled_up, new_level, xp_to_add = await self.level_up_check(user_data, xp_to_add)

        if leveled_up:
            # Notify the user about their level-up
            embed = discord.Embed(
                title=f"Congratulations {message.author.display_name}!",
                description="You have leveled up!",
                color=discord.Color.green()
            )
            embed.add_field(name="New Level", value=f"Level {new_level}", inline=False)
            embed.add_field(name="XP Gained", value=f"+{xp_to_add} XP", inline=False)
            await self.bot.get_channel(self.channel_id).send(embed=embed)

    @staticmethod
    def xp_for_level(level: int) -> int:
        """
        Calculate the total XP required to reach a given level.
        """
        return int(100 * level + 25 * level * (level - 1) + 5 * (level - 1) * level * (2 * level - 1) / 6)

    def xp_for_next_level(self, current_level: int) -> int:
        """
        Calculate the XP required to progress from the current level to the next.
        """
        return self.xp_for_level(current_level + 1) - self.xp_for_level(current_level)

    @commands.command()
    async def level(self, ctx, user: discord.Member = None):
        """Check the user's current level, rank, and XP details."""
        if user is None:
            user = ctx.author

        guild_id = ctx.guild.id
        user_id = user.id

        async with SessionLocal() as session:
            # Fetch user data
            stmt = select(Level).filter(Level.guild_id == guild_id, Level.user_id == user_id)
            result = await session.execute(stmt)
            user_data = result.scalars().first()

            if not user_data:
                await ctx.send(f"{user.mention}, you don't have any level data yet!")
                return

            # Fetch all users in the guild, ordered by XP descending
            stmt = select(Level).filter(Level.guild_id == guild_id).order_by(Level.xp.desc())
            result = await session.execute(stmt)
            all_users = result.scalars().all()

            # Determine rank of the user
            rank = None
            for idx, level_entry in enumerate(all_users):
                if level_entry.user_id == user_id:
                    rank = idx + 1
                    break

            if rank is None:
                await ctx.send("Could not determine your rank.")
                return

            # Calculate XP for next level
            xp_next_level = self.xp_for_next_level(user_data.level)
            xp_remaining = xp_next_level - (user_data.xp - self.xp_for_level(user_data.level))

            # Create the embed
            embed = discord.Embed(
                title=f"{user.name}'s Level",
                description=f"Here are your current stats:",
                color=discord.Color.blue()
            )
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
            embed.add_field(name="Level", value=f"Level {user_data.level}", inline=True)
            embed.add_field(name="XP", value=f"{user_data.xp} XP", inline=True)
            embed.add_field(name="XP to Next Level", value=f"{xp_remaining} XP", inline=True)

            await ctx.send(embed=embed)

    @commands.command()
    async def topten(self, ctx):
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

    @commands.command(hidden=True)
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

    @commands.command(hidden=True)
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

    @commands.command(hidden=True)
    @commands.is_owner()
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


    @commands.command()
    async def leaderboard(self, ctx):
        """Display the leaderboard of the current server"""
        guild_id = ctx.guild.id
        user_id = ctx.author.id

        async with SessionLocal() as session:
            # Get the user's current level and position
            stmt = select(Level).filter(Level.guild_id == guild_id, Level.user_id == user_id)
            result = await session.execute(stmt)
            user_data = result.scalars().first()

            if not user_data:
                await ctx.send(f"{ctx.author.mention}, you don't have any level data yet!")
                return

            # Get all users in the guild ordered by level descending
            stmt = select(Level).filter(Level.guild_id == guild_id).order_by(Level.level.desc())
            result = await session.execute(stmt)
            all_users = result.scalars().all()

            # Find the index of the current user
            user_position = None
            for idx, user in enumerate(all_users):
                if user.user_id == user_id:
                    user_position = idx
                    break

            if user_position is None:
                await ctx.send("Could not find your position in the leaderboard.")
                return

            # Fetch the 2 users behind the current user, the user, and 7 users ahead of them
            start_index = max(0, user_position - 8)  # Ensure no negative index
            end_index = min(len(all_users), user_position + 3)  # Ensure we don't go out of bounds
            leaderboard = all_users[start_index:end_index]

        # Create the embed to send
        embed = discord.Embed(
            title=f"Leaderboard for {ctx.guild.name}",
            description=f"Here are the users around you in the leaderboard based on level:",
            color=discord.Color.gold()
        )

        for idx, user in enumerate(leaderboard):
            member = ctx.guild.get_member(user.user_id)  # Get the Discord member object
            username = member.mention if member else "Unknown User"

            # Correct the rank to reflect the user's position in the leaderboard
            rank = start_index + idx + 1  # Adjust rank accordingly to the slice's starting position

            embed.add_field(
                name="",
                value=f"#{rank} {username} Level: {user.level} | XP: {user.xp}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name="trim_db", hidden=True)
    @commands.is_owner()
    async def trim_db(self, ctx):
        async with SessionLocal() as session:
            query = select(Level).filter(Level.guild_id == ctx.guild.id)
            result = await session.execute(query)
            all_users = result.scalars().all()

            guild_user_ids = {member.id for member in ctx.guild.members}
            removed_user_ids = []

            for user in all_users:
                if user.user_id not in guild_user_ids:
                    user_data = await session.get(Level, (ctx.guild.id, user.user_id))
                    if user_data:
                        await session.delete(user_data)
                        removed_user_ids.append(user.user_id)

            await session.commit()

            header = f"Removed {len(removed_user_ids)} users from the leaderboard.\nUsers removed:\n"
            max_chunk_size = 2000 - len(header)
            removed_users_str = "\n".join(map(str, removed_user_ids)) if removed_user_ids else "User not found"

            chunks = []
            current_chunk = ""

            for user_id in removed_user_ids:
                user_entry = f"{user_id}\n"
                if len(current_chunk) + len(user_entry) > max_chunk_size:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                current_chunk += user_entry

            if current_chunk:
                chunks.append(current_chunk.strip())

            if not removed_user_ids:
                await ctx.send(f"{header}User not found")
            else:
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await ctx.send(header + chunk)
                    else:
                        await ctx.send(chunk)

    @commands.command(name="users", hidden=True)
    @commands.is_owner()
    async def users(self, ctx):
        from checklen import check
        num = check()
        await ctx.send(f"There are {num} users tracked in my database!")


# Setup the cog
async def setup(bot):
    await bot.add_cog(LevelingCog(bot))
