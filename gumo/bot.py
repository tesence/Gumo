import logging
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

MODULES = [
    "gumo.modules.emoji_chain",
    "gumo.modules.help",
    "gumo.modules.roles",
    "gumo.modules.seed"
]


class Bot(commands.Bot):

    def __init__(self, *args, **kwargs):

        intents = discord.Intents.default()
        intents.message_content = True  # pylint: disable=assigning-non-slot
        intents.members = True  # pylint: disable=assigning-non-slot
        super().__init__(*args, **kwargs, intents=intents)

        self.remove_command('help')

    async def setup_hook(self):
        for module in MODULES:
            await self.load_extension(module)
