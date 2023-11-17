"""
Provide Ori and the Blind Forest seed generation commands:
- "/seed": the default seed generation command
- "/daily": the default seed generation command, forcing the seed name to the current date YYYY-MM-DD.
"""

import logging
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pytz

from gumo import api
from gumo.api import models

logger = logging.getLogger(__name__)


class BFRandomizer(commands.Cog, name="Blind Forest Randomizer"):
    """Custom Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.api_client = api.BFRandomizerApiClient()

    @app_commands.command(name='seed')
    @app_commands.describe(seed_name="A string to be used as seed")
    @app_commands.describe(logic_mode="Randomizer logic mode")
    @app_commands.choices(logic_mode=models.LOGIC_MODE_CHOICES)
    @app_commands.describe(key_mode="Randomizer key mode")
    @app_commands.choices(key_mode=models.KEY_MODE_CHOICES)
    @app_commands.describe(goal_mode="Randomizer goal mode")
    @app_commands.choices(goal_mode=models.GOAL_MODE_CHOICES)
    @app_commands.describe(spawn="The location where the player starts in the seed")
    @app_commands.choices(spawn=models.SPAWN_CHOICES)
    @app_commands.describe(variation1="Extra randomizer variation")
    @app_commands.choices(variation1=models.VARIATION_CHOICES)
    @app_commands.describe(variation2="Extra randomizer variation")
    @app_commands.choices(variation2=models.VARIATION_CHOICES)
    @app_commands.describe(variation3="Extra randomizer variation")
    @app_commands.choices(variation3=models.VARIATION_CHOICES)
    @app_commands.describe(item_pool="Randomizer item pool")
    @app_commands.choices(item_pool=models.ITEM_POOL_CHOICES)
    @app_commands.describe(relic_count="(World Tour only) The number of relics to place in the seed")
    # pylint: disable=unused-argument
    async def seed(self, interaction: discord.Interaction,
                   seed_name: Optional[str] = None,
                   logic_mode: Optional[app_commands.Choice[str]] = None,
                   key_mode: Optional[app_commands.Choice[str]] = None,
                   goal_mode: Optional[app_commands.Choice[str]] = None,
                   spawn: Optional[app_commands.Choice[str]] = None,
                   variation1: Optional[app_commands.Choice[str]] = None,
                   variation2: Optional[app_commands.Choice[str]] = None,
                   variation3: Optional[app_commands.Choice[str]] = None,
                   item_pool: Optional[app_commands.Choice[str]] = None,
                   relic_count: Optional[app_commands.Range[int, 1, 11]] = None):
        """
        Generate an Ori and the Blind Forest Randomizer seed.

        Args:
            interaction (discord.Interaction): discord interaction object
            seed_name (str, optional): Seed name. Defaults to None.
            logic_mode (app_commands.Choice[str], optional): Randomizer logic mode. Defaults to None.
            key_mode (app_commands.Choice[str], optional): Randomizer key mode. Defaults to None.
            goal_mode (app_commands.Choice[str], optional): Randomizer goal mode. Defaults to None.
            spawn (app_commands.Choice[str], optional): Randomizer spawn location. Defaults to None.
            variation1 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            variation2 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            variation3 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            item_pool (app_commands.Choice[str], optional): Randomizer item pool. Defaults to None.
            relic_count (int, optional): Randomizer relic count (World Tour only). Defaults to None.
        """
        await interaction.response.defer()
        seed_settings = {s[0]: s[1] for s in interaction.namespace if not s[0].startswith('variation')}
        variations = (s[1] for s in interaction.namespace if s[0].startswith('variation'))
        message, files = await self._get_seed_message(**seed_settings, variations=variations)
        return await interaction.followup.send(content=message, files=files)

    @app_commands.command(name='daily')
    @app_commands.describe(logic_mode="Randomizer logic mode")
    @app_commands.choices(logic_mode=models.LOGIC_MODE_CHOICES)
    @app_commands.describe(key_mode="Randomizer key mode")
    @app_commands.choices(key_mode=models.KEY_MODE_CHOICES)
    @app_commands.describe(goal_mode="Randomizer goal mode")
    @app_commands.choices(goal_mode=models.GOAL_MODE_CHOICES)
    @app_commands.describe(spawn="Start location")
    @app_commands.choices(spawn=models.SPAWN_CHOICES)
    @app_commands.describe(variation1="Extra randomizer variation")
    @app_commands.choices(variation1=models.VARIATION_CHOICES)
    @app_commands.describe(variation2="Extra randomizer variation")
    @app_commands.choices(variation2=models.VARIATION_CHOICES)
    @app_commands.describe(variation3="Extra randomizer variation")
    @app_commands.choices(variation3=models.VARIATION_CHOICES)
    @app_commands.describe(item_pool="Randomizer item pool")
    @app_commands.choices(item_pool=models.ITEM_POOL_CHOICES)
    @app_commands.describe(relic_count="(World Tour only) The number of relics to place in the seed")
    # pylint: disable=unused-argument
    async def daily(self, interaction: discord.Interaction,
                    logic_mode: Optional[app_commands.Choice[str]] = None,
                    key_mode: Optional[app_commands.Choice[str]] = None,
                    goal_mode: Optional[app_commands.Choice[str]] = None,
                    spawn: Optional[app_commands.Choice[str]] = None,
                    variation1: Optional[app_commands.Choice[str]] = None,
                    variation2: Optional[app_commands.Choice[str]] = None,
                    variation3: Optional[app_commands.Choice[str]] = None,
                    item_pool: Optional[app_commands.Choice[str]] = None,
                    relic_count: Optional[app_commands.Range[int, 1, 11]] = None):
        """
        Generate an Ori and the Blind Forest Randomizer seed.
        The seed name is forced to the current date in YYYY-MM-DD format.

        Args:
            interaction (discord.Interaction): discord interaction object
            logic_mode (app_commands.Choice[str], optional): Randomizer logic mode. Defaults to None.
            key_mode (app_commands.Choice[str], optional): Randomizer key mode. Defaults to None.
            goal_mode (app_commands.Choice[str], optional): Randomizer goal mode. Defaults to None.
            spawn (app_commands.Choice[str], optional): Randomizer spawn location. Defaults to None.
            variation1 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            variation2 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            variation3 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            item_pool (app_commands.Choice[str], optional): Randomizer item pool. Defaults to None.
            relic_count (int, optional): Randomizer relic count (World Tour only). Defaults to None.
        """
        await interaction.response.defer()
        seed_name = pytz.UTC.localize(datetime.utcnow()).astimezone(pytz.timezone('US/Pacific')).strftime("%Y-%m-%d")
        seed_settings = {s[0]: s[1] for s in interaction.namespace if not s[0].startswith('variation')}
        variations = (s[1] for s in interaction.namespace if s[0].startswith('variation'))
        message, files = await self._get_seed_message(seed_name=seed_name, **seed_settings, variations=variations)
        return await interaction.followup.send(content=message, files=files)

    async def _get_seed_message(self, seed_name: str = None, logic_mode: str = None, key_mode: str = None,
                                goal_mode: str = None, spawn: str = None, variations: tuple = (),
                                item_pool: str = None, relic_count: int = None):
        """Return the seed data in a formatted message

        Args:
            seed_name (str, optional): Seed name. Defaults to None.
            logic_mode (str, optional): Randomizer logic mode. Defaults to None.
            key_mode (str, optional): Randomizer key mode. Defaults to None.
            goal_mode (str, optional): Randomizer goal mode. Defaults to None.
            spawn (str, optional): Randomizer spawn location. Defaults to None.
            variations (List[str], optional): Randomizer extra variations. Defaults to None.
            item_pool (str, optional): Randomizer item pool. Defaults to None.
            relic_count (int, optional): Randomizer relic count (World Tour only). Defaults to None.

        Returns:
            message: (str): The content of the message
            files: (List[discord.File]) The to be attached to the message
        """
        seed_data = await self.api_client.get_seed(seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                                                   goal_mode=goal_mode, spawn=spawn, variations=variations,
                                                   item_pool=item_pool, relic_count=relic_count)
        message = f"`{seed_data['seed_header']}`\n" \
                  f"**Spoiler**: [link]({seed_data['spoiler_url']})\n" \
                  f"**Map**: [link]({seed_data['map_url']})\n" \
                  f"**History**: [link]({seed_data['history_url']})"
        return message, seed_data['seed_files']

    @seed.error
    @daily.error
    async def seed_error(self, interaction: discord.Interaction, error: app_commands.errors.AppCommandError):
        """Handler called whenever an error occured while generating a seed

        Args:
            interaction (discord.Interaction): discord interaction object
            error (app_commands.errors.AppCommandError): error raised
        """
        message = "An occured while generating the seed"
        logger.error(message, exc_info=error)
        return await interaction.followup.send(message)


# pylint: disable=missing-function-docstring
async def setup(bot):
    await bot.add_cog(BFRandomizer(bot))
