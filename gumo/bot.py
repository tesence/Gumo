import logging
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

MODULES = [
    "gumo.modules.emoji_chain",
    "gumo.modules.seed"
]

class CustomCommandTree(app_commands.CommandTree):

    async def on_error(self, interaction, error):
        command = interaction.command
        if command is not None:
            logger.error('Ignoring exception in command %r', command.qualified_name, exc_info=error)
        else:
            logger.error('Ignoring exception in command tree', exc_info=error)


class Bot(commands.Bot):

    def __init__(self, *args, **kwargs):

        intents = discord.Intents.default()
        intents.message_content = True  # pylint: disable=assigning-non-slot
        intents.members = True  # pylint: disable=assigning-non-slot
        super().__init__(*args, **kwargs, intents=intents, tree_cls=CustomCommandTree)

        self.remove_command('help')

    async def setup_hook(self):
        for module in MODULES:
            await self.load_extension(module)

    async def on_ready(self):
        synced = await self.tree.sync()
        logger.info(f"Synced commands: {len(synced)}")

    async def on_interaction(self, interaction):
        message = f"Command invoked by {interaction.user.name} ({interaction.user.display_name}): " + \
                  f"/{interaction.command.qualified_name}"

        if "options" in interaction.data:
            arguments = [f"{opt['name']}='{opt['value']}'" for opt in interaction.data['options'][0]['options']]
            message += f" {' '.join(arguments)}"

        logger.info(message)
