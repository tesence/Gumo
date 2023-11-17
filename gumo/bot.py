"""
Override the discord.py Bot class to:
- Load modules
- Sync applications commands on startup
- Improve error and interaction logging
"""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

MODULES = [
    "gumo.modules.emoji_chain",
    "gumo.modules.seed",
    "gumo.modules.league",
]

class Bot(commands.Bot):
    """Custom Bot class to override the default behaviour and logging"""

    def __init__(self, *args, **kwargs):

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(*args, **kwargs, intents=intents)
        self.remove_command('help')

    async def setup_hook(self):
        for module in MODULES:
            await self.load_extension(module)

    # pylint: disable=missing-function-docstring
    async def on_ready(self):
        synced = await self.tree.sync()
        logger.info("Synced commands: %s", len(synced))

    # pylint: disable=missing-function-docstring
    async def on_interaction(self, interaction: discord.Interaction):
        message = f"Command invoked by {interaction.user.name} ({interaction.user.display_name}): " + \
                  f"/{interaction.command.qualified_name}"

        if interaction.namespace:
            arguments = [f"{opt[0]}='{opt[1]}'" for opt in interaction.namespace]
            message += f" {' '.join(arguments)}"

        logger.info(message)
