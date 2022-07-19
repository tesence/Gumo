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
        intents.members = True  # pylint: disable=assigning-non-slot
        super().__init__(*args, **kwargs, intents=intents)

        self.remove_command('help')
        self.load_modules()

    def load_modules(self):
        for module in MODULES:
            self.load_extension(module)
