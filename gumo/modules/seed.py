"""
Provide Ori and the Blind Forest seed generation commands:
- "/seed": the default seed generation command
- "/daily": the default seed generation command, forcing the seed name to the current date YYYY-MM-DD.
- /league: Command group specific to the Blind Forest Randomizer League
    - /league seed: seed generation command forcing the seed name and the proper options
"""

import logging
from datetime import datetime, timedelta
import functools
import io
import os
import random
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pytz

import gspread
from google.oauth2 import service_account

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

class BadDurationArgumentFormat(app_commands.AppCommandError):
    """Bad duration format Exception"""

# pylint: disable=abstract-method
class DurationFormatTransformer(app_commands.Transformer):
    """Duration format transformer"""

    # pylint: disable=arguments-differ
    async def transform(self, interaction: discord.Interaction, value: str):
        if r := re.match(r"^(?:([0-9]+):)?([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?$", value):
            hours, minutes, seconds, milliseconds = r.groups(default='0')
            milliseconds = milliseconds[:3]
            if int(minutes) > 59 or int(seconds) > 59: raise BadDurationArgumentFormat()
            return tuple(map(int, (hours, minutes, seconds, milliseconds)))
        raise BadDurationArgumentFormat()

class BFRandomizer(commands.Cog, name="Blind Forest Randomizer"):
    """Custom Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.api_client = api.BFRandomizerApiClient()

        self.credentials = service_account.Credentials.from_service_account_file(
            os.getenv("GUMO_BOT_GOOGLE_API_SA_FILE"),
            scopes = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
        )

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
    @app_commands.describe(relic_count="(World Tour only) The number of relics to place in the seed")
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
            logic_mode (str, optional): Randomizer logic mode. Defaults to None.
            key_mode (str, optional): Randomizer key mode. Defaults to None.
            goal_mode (str, optional): Randomizer goal mode. Defaults to None.
            spawn (str, optional): Randomizer spawn location. Defaults to None.
            variation1 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            variation2 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            variation3 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            item_pool (str, optional): Randomizer item pool. Defaults to None.
            relic_count (int, optional): Randomizer relic count (World Tour only). Defaults to None.
        """
        await interaction.response.defer()
        logic_mode = getattr(logic_mode, 'name', None)
        key_mode = getattr(key_mode, 'name', None)
        goal_mode = getattr(goal_mode, 'name', None)
        spawn = getattr(spawn, 'name', None)
        item_pool = getattr(item_pool, 'name', None)
        variations = [variation.name for variation in [variation1, variation2, variation3] if variation]
        await self._seed(interaction=interaction, seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                         goal_mode=goal_mode, spawn=spawn, variations=variations, item_pool=item_pool,
                         relic_count=relic_count)

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
    @app_commands.describe(relic_count="(World Tour only) The number of relics to place in the seed")
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
            logic_mode (str, optional): Randomizer logic mode. Defaults to None.
            key_mode (str, optional): Randomizer key mode. Defaults to None.
            goal_mode (str, optional): Randomizer goal mode. Defaults to None.
            spawn (str, optional): Randomizer spawn location. Defaults to None.
            variation1 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            variation2 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            variation3 (Optional[app_commands.Choice[str]], optional): Randomizer extra variation. Defaults to None.
            item_pool (str, optional): Randomizer item pool. Defaults to None.
            relic_count (int, optional): Randomizer relic count (World Tour only). Defaults to None.
        """
        await interaction.response.defer()
        seed_name = pytz.UTC.localize(datetime.utcnow()).astimezone(pytz.timezone('US/Pacific')).strftime("%Y-%m-%d")
        logic_mode = getattr(logic_mode, 'name', None)
        key_mode = getattr(key_mode, 'name', None)
        goal_mode = getattr(goal_mode, 'name', None)
        spawn = getattr(spawn, 'name', None)
        item_pool = getattr(item_pool, 'name', None)
        variations = (variation.name for variation in [variation1, variation2, variation3] if variation)
        await self._seed(interaction=interaction, seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                         goal_mode=goal_mode, spawn=spawn, variations=variations, item_pool=item_pool,
                         relic_count=relic_count)

    league = app_commands.Group(name="league", description="BF Rando League commands")

    @league.command(name='seed')
    async def league_seed(self, interaction: discord.Interaction):
        """
        Generate an Ori and the Blind Forest Randomizer seed.
        The seed name and option are set to be compliant with the Rando League rules by default.

        Args:
            interaction (discord.Interaction): discord interaction object
        """
        await interaction.response.defer(ephemeral=True)
        week_number = (pytz.UTC.localize(datetime.utcnow()).astimezone(pytz.timezone('US/Eastern')) +
                       timedelta(days=2, hours=3)).isocalendar().week
        random.seed(week_number)
        seed_name = str(random.randint(1, 10**9))
        random.seed(None)
        logic_mode = None
        key_mode = 'Clues'
        goal_mode = 'World Tour'
        relic_count = 4
        spawn = 'Grotto'
        item_pool = 'Competitive'
        variations = ()
        await self._seed(interaction=interaction, seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                         goal_mode=goal_mode, spawn=spawn, variations=variations, item_pool=item_pool,
                         relic_count=relic_count, silent=True)

    async def _seed(self, interaction: discord.Interaction, seed_name: str, logic_mode: str = None,
                    key_mode: str = None, goal_mode: str = None, spawn: str = None, variations: tuple = (),
                    item_pool: str = None, relic_count: int = None, silent: bool = False):

        seed_data = await self._get_seed_data(seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                                              goal_mode=goal_mode, spawn=spawn, variations=variations,
                                              item_pool=item_pool, relic_count=relic_count)

        message = f"`{seed_data['seed_header']}`\n"
        if not silent:
            message += f"**Spoiler**: [link]({seed_data['spoiler_url']})\n"
            message += f"**Map**: [link]({seed_data['map_url']})\n"
            message += f"**History**: [link]({seed_data['spoiler_url']})\n"

        return await interaction.followup.send(message, files=[seed_data['seed_file']])

    async def _get_seed_data(self, seed_name: str = None, logic_mode: str = None, key_mode: str = None,
                             goal_mode: str = None, spawn: str = None, variations: tuple = (),
                             item_pool: str = None, relic_count: int = None):
        seed_data = await self.api_client.get_data(seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                                                   goal_mode=goal_mode, spawn=spawn, variations=variations,
                                                   item_pool=item_pool, relic_count=relic_count)
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
    # pylint: disable=unused-argument, missing-function-docstring
    async def seed_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await interaction.followup.send("An error occured while generating the seed")

    @league.command(name='submit')
    @app_commands.describe(timer="The LiveSplit time (e.g: \"40:43\", \"1:40:43\" or \"1:40:43.630\")")
    @app_commands.describe(vod="The link to the VOD")
    async def league_submit(self, interaction: discord.Interaction,
                            timer: app_commands.Transform[str, DurationFormatTransformer], vod: str):
        """Submit rando league result

        Args:
            interaction (discord.Interaction): discord interaction object
            timer (app_commands.Transform[str, DurationTransformer]): seed timer
            vod (str): link to the vod
        """
        await interaction.response.defer(ephemeral=True)

        part = functools.partial(gspread.authorize, self.credentials)
        client = await self.bot.loop.run_in_executor(None, part)

        part = functools.partial(client.open, title="Ori Rando League Leaderboard")
        spreadsheet = await self.bot.loop.run_in_executor(None, part)

        part = functools.partial(spreadsheet.worksheet, "S2 Raw Data")
        tab = await self.bot.loop.run_in_executor(None, part)
        records = await self.bot.loop.run_in_executor(None, tab.get_all_records)

        now = pytz.UTC.localize(datetime.utcnow()).astimezone(pytz.timezone('US/Eastern'))
        date = now.strftime("%Y-%m-%d %H:%M:%S")
        week_number = (now + timedelta(days=2, hours=3)).isocalendar().week
        timer = "{:02}:{:02}:{:02}.{:03}".format(*timer)
        if any((x['Runner'] == interaction.user.display_name and x['Week Number'] == week_number) for x in records):
            return await interaction.followup.send('You already have submitted this week!')

        part = functools.partial(tab.append_row,
                                [week_number, date, interaction.user.display_name, timer, vod],
                                value_input_option="USER_ENTERED")
        await self.bot.loop.run_in_executor(None, part)

        await interaction.followup.send('Submission successful!')

    @league_submit.error
    # pylint: disable=missing-function-docstring
    async def league_submit_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, BadDurationArgumentFormat):
            await interaction.response.send_message("Invalid timer format", ephemeral=True)
        else:
            await interaction.response.send_message("An error occured during the submission", ephemeral=True)

# pylint: disable=missing-function-docstring
async def setup(bot):
    await bot.add_cog(BFRandomizer(bot))
