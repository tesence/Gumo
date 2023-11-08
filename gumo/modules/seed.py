import logging
from datetime import datetime, timedelta
import io
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pytz

from gumo import api
from gumo.api import models

logger = logging.getLogger(__name__)

LOGIC_MODE_CHOICES = [app_commands.Choice(name=name, value=value) for name, value in models.LOGIC_MODES.items()]
KEY_MODE_CHOICES = [app_commands.Choice(name=name, value=value) for name, value in models.KEY_MODES.items()]
GOAL_MODE_CHOICES = [app_commands.Choice(name=name, value=value) for name, value in models.GOAL_MODES.items()]
SPAWN_CHOICES = [app_commands.Choice(name=name, value=value) for name, value in models.SPAWNS.items()]
VARIATION_CHOICES = [app_commands.Choice(name=name, value=value) for name, value in models.VARIATIONS.items()]
LOGIC_PATH_CHOICES = [app_commands.Choice(name=name, value=value) for name, value in models.LOGIC_PATHS.items()]
ITEM_POOL_CHOICES = [app_commands.Choice(name=name, value=value) for name, value in models.ITEM_POOLS.items()]


class BFRandomizer(commands.Cog, name="Blind Forest Randomizer"):

    def __init__(self, bot):
        self.bot = bot
        self.api_client = api.BFRandomizerApiClient()

    @app_commands.command(name='seed')
    @app_commands.describe(seed_name="A string to be used as seed")
    @app_commands.describe(logic_mode="Randomizer logic mode")
    @app_commands.choices(logic_mode=LOGIC_MODE_CHOICES)
    @app_commands.describe(key_mode="Randomizer key mode")
    @app_commands.choices(key_mode=KEY_MODE_CHOICES)
    @app_commands.describe(goal_mode="Randomizer goal mode")
    @app_commands.choices(goal_mode=GOAL_MODE_CHOICES)
    @app_commands.describe(spawn="The location where the player starts in the seed")
    @app_commands.choices(spawn=SPAWN_CHOICES)
    @app_commands.describe(variation1="Extra randomizer variation")
    @app_commands.choices(variation1=VARIATION_CHOICES)
    @app_commands.describe(variation2="Extra randomizer variation")
    @app_commands.choices(variation2=VARIATION_CHOICES)
    @app_commands.describe(variation3="Extra randomizer variation")
    @app_commands.choices(variation3=VARIATION_CHOICES)
    @app_commands.describe(item_pool="Randomizer item pool")
    @app_commands.choices(item_pool=ITEM_POOL_CHOICES)
    async def seed(self, interaction: discord.Interaction,
                   seed_name: Optional[str],
                   logic_mode: Optional[app_commands.Choice[str]],
                   key_mode: Optional[app_commands.Choice[str]],
                   goal_mode: Optional[app_commands.Choice[str]],
                   spawn: Optional[app_commands.Choice[str]],
                   variation1: Optional[app_commands.Choice[str]],
                   variation2: Optional[app_commands.Choice[str]],
                   variation3: Optional[app_commands.Choice[str]],
                   item_pool: Optional[app_commands.Choice[str]]):
        await interaction.response.defer()
        logic_mode = getattr(logic_mode, 'name', None)
        key_mode = getattr(key_mode, 'name', None)
        goal_mode = getattr(goal_mode, 'name', None)
        spawn = getattr(spawn, 'name', None)
        item_pool = getattr(item_pool, 'name', None)
        variations = [variation.name for variation in [variation1, variation2, variation3] if variation]
        return await self._seed(interaction=interaction, seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                                goal_mode=goal_mode, spawn=spawn, variations=variations, item_pool=item_pool)

    @app_commands.command(name='daily')
    @app_commands.describe(logic_mode="Randomizer logic mode")
    @app_commands.choices(logic_mode=LOGIC_MODE_CHOICES)
    @app_commands.describe(key_mode="Randomizer key mode")
    @app_commands.choices(key_mode=KEY_MODE_CHOICES)
    @app_commands.describe(goal_mode="Randomizer goal mode")
    @app_commands.choices(goal_mode=GOAL_MODE_CHOICES)
    @app_commands.describe(spawn="Start location")
    @app_commands.choices(spawn=SPAWN_CHOICES)
    @app_commands.describe(variation1="Extra randomizer variation")
    @app_commands.choices(variation1=VARIATION_CHOICES)
    @app_commands.describe(variation2="Extra randomizer variation")
    @app_commands.choices(variation2=VARIATION_CHOICES)
    @app_commands.describe(variation3="Extra randomizer variation")
    @app_commands.choices(variation3=VARIATION_CHOICES)
    @app_commands.describe(item_pool="Randomizer item pool")
    @app_commands.choices(item_pool=ITEM_POOL_CHOICES)
    async def daily(self, interaction: discord.Interaction,
                    logic_mode: Optional[app_commands.Choice[str]],
                    key_mode: Optional[app_commands.Choice[str]],
                    goal_mode: Optional[app_commands.Choice[str]],
                    spawn: Optional[app_commands.Choice[str]],
                    variation1: Optional[app_commands.Choice[str]],
                    variation2: Optional[app_commands.Choice[str]],
                    variation3: Optional[app_commands.Choice[str]],
                    item_pool: Optional[app_commands.Choice[str]]):
        await interaction.response.defer()
        # pylint: disable=no-value-for-parameter
        seed_name = pytz.UTC.localize(datetime.now()).astimezone(pytz.timezone('US/Pacific')).strftime("%Y-%m-%d")
        logic_mode = getattr(logic_mode, 'name', None)
        key_mode = getattr(key_mode, 'name', None)
        goal_mode = getattr(goal_mode, 'name', None)
        spawn = getattr(spawn, 'name', None)
        item_pool = getattr(item_pool, 'name', None)
        variations = [variation.name for variation in [variation1, variation2, variation3] if variation]
        return await self._seed(interaction=interaction, seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                                goal_mode=goal_mode, spawn=spawn, variations=variations, item_pool=item_pool)

    league = app_commands.Group(name="league", description="BF Rando League commands")

    @league.command(name='seed')
    @app_commands.describe(logic_mode="Randomizer logic mode")
    @app_commands.choices(logic_mode=LOGIC_MODE_CHOICES)
    @app_commands.describe(key_mode="Randomizer key mode")
    @app_commands.choices(key_mode=KEY_MODE_CHOICES)
    @app_commands.describe(goal_mode="Randomizer goal mode")
    @app_commands.choices(goal_mode=GOAL_MODE_CHOICES)
    @app_commands.describe(spawn="Start location")
    @app_commands.choices(spawn=SPAWN_CHOICES)
    @app_commands.describe(variation1="Extra randomizer variation")
    @app_commands.choices(variation1=VARIATION_CHOICES)
    @app_commands.describe(variation2="Extra randomizer variation")
    @app_commands.choices(variation2=VARIATION_CHOICES)
    @app_commands.describe(variation3="Extra randomizer variation")
    @app_commands.choices(variation3=VARIATION_CHOICES)
    @app_commands.describe(item_pool="Randomizer item pool")
    @app_commands.choices(item_pool=ITEM_POOL_CHOICES)
    async def league_seed(self, interaction: discord.Interaction,
                          logic_mode: Optional[app_commands.Choice[str]],
                          key_mode: Optional[app_commands.Choice[str]],
                          goal_mode: Optional[app_commands.Choice[str]],
                          spawn: Optional[app_commands.Choice[str]],
                          variation1: Optional[app_commands.Choice[str]],
                          variation2: Optional[app_commands.Choice[str]],
                          variation3: Optional[app_commands.Choice[str]],
                          item_pool: Optional[app_commands.Choice[str]]):
        await interaction.response.defer(ephemeral=True)
        # pylint: disable=no-value-for-parameter
        week_number = (pytz.UTC.localize(datetime.now()).astimezone(pytz.timezone('US/Eastern')) +
                       timedelta(days=2, hours=3)).isocalendar().week
        random.seed(week_number)
        seed_name = str(random.randint(1, 10**9))
        random.seed(None)
        logic_mode = getattr(logic_mode, 'name', None)
        key_mode = getattr(key_mode, 'name', None)
        goal_mode = getattr(goal_mode, 'name', None)
        spawn = getattr(spawn, 'name', None)
        item_pool = getattr(item_pool, 'name', 'Competitive')
        variations = [variation.name for variation in [variation1, variation2, variation3] if variation]
        return await self._seed(interaction=interaction, seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                                goal_mode=goal_mode, spawn=spawn, variations=variations, item_pool=item_pool,
                                silent=True)

    async def _seed(self, interaction, seed_name, logic_mode=None, key_mode=None, goal_mode=None, spawn=None,
                    variations=(), item_pool=None, silent=False):

        seed_data = await self._get_seed_data(seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                                              goal_mode=goal_mode, spawn=spawn, variations=variations,
                                              item_pool=item_pool)

        message = f"`{seed_data['seed_header']}`\n"
        if not silent:
            message += f"**Spoiler**: [link]({seed_data['spoiler_url']})\n"
            message += f"**Map**: [link]({seed_data['map_url']})\n"
            message += f"**History**: [link]({seed_data['spoiler_url']})\n"

        return await interaction.followup.send(message, files=[seed_data['seed_file']])

    async def _get_seed_data(self, seed_name, logic_mode=None, key_mode=None, goal_mode=None, spawn=None,
                             variations=(), item_pool=None):
        seed_data = await self.api_client.get_data(seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                                                   goal_mode=goal_mode, spawn=spawn, variations=variations,
                                                   item_pool=item_pool)
        seed_buffer = io.BytesIO(bytes(seed_data['players'][0]['seed'], encoding="utf8"))
        return {
            'seed_header': seed_data['players'][0]['seed'].split("\n")[0],
            'spoiler_url': f"{api.SEEDGEN_API_URL}{seed_data['players'][0]['spoiler_url']}",
            'map_url': f"{api.SEEDGEN_API_URL}{seed_data['map_url']}",
            'history_url': f"{api.SEEDGEN_API_URL}{seed_data['history_url']}",
            'seed_file': discord.File(seed_buffer, filename='randomizer.dat')
        }

    @seed.error
    @daily.error
    @league_seed.error
    async def seed_error(self, interaction, error):
        await interaction.followup.send("An error occured while generating the seed")

async def setup(bot):
    await bot.add_cog(BFRandomizer(bot))
