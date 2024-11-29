import discord
import os
import traceback
from discord.ext import commands
from dotenv import load_dotenv
from discord.ext.commands import ExtensionError

load_dotenv()

# Set up intents
intents = discord.Intents.default()
intents.members = True
intents.reactions = True
intents.messages = True
intents.message_content = True
intents.guilds = True

async def cog_loader(bot_instance: commands.Bot) -> None:
    """This function loads all cogs in the cogs folder."""
    for file in os.listdir('./cogs'):
        if file.endswith('.py') and file != '__init__.py':
            cog_name = file[:-3]
            try:
                await bot_instance.load_extension(f'cogs.{cog_name}')
                print(f'Successfully loaded {cog_name}')
            except ExtensionError as e:
                print(f'Failed to load cog {cog_name}: {str(e)}')
                print(traceback.format_exc())

class ReactionLogger(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        print(f"Logged in as {self.user.name}")
        print("Ready to log all reactions!")

    async def setup_hook(self):
        await cog_loader(self)

bot = ReactionLogger(command_prefix=commands.when_mentioned, intents=intents, message_cache_size=1000)

if __name__ == "__main__":
    bot.run(os.getenv("TOKEN"))
