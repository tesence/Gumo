"""
Provide Ori and the Blind Forest rando league commands
- "/league clear": Clear rando league seeds settings (admin)
- "/league seed": Generate a seed using randomizer settings
- "/league set": Set rando league seeds settings (admin)
- "/league submit": Submit a rando league result
- "/league view": View rando league seeds settings (admin)

"""

import logging
from datetime import datetime, timedelta
import functools
import os
import random
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import asqlite
import pytz
import gspread
from google.oauth2 import service_account

from gumo import api
from gumo.api import models

logger = logging.getLogger(__name__)

DB_FILE = os.getenv('GUMO_BOT_DB_FILE')


class BadTimeArgumentFormat(app_commands.AppCommandError):
    """Bad duration format Exception"""

# pylint: disable=abstract-method
class TimeFormatTransformer(app_commands.Transformer):
    """Duration format transformer"""

    # pylint: disable=arguments-differ
    async def transform(self, interaction: discord.Interaction, value: str):
        if r := re.match(r"^(?:([0-9]+):)?([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?$", value):
            hours, minutes, seconds, milliseconds = r.groups(default='0')
            milliseconds = milliseconds[:3]
            if int(minutes) > 59 or int(seconds) > 59:
                raise BadTimeArgumentFormat()
            return tuple(map(int, (hours, minutes, seconds, milliseconds)))
        raise BadTimeArgumentFormat()

async def is_league_admin_check(interaction: discord.Interaction):
    """Rando league administrator checks

    Args:
        interaction (discord.Interaction): discord interaction object

    Returns:
        bool: True if the user invoking the command is a rando league administrator
    """
    allowed = await interaction.client.is_owner(interaction.user) or \
              isinstance(interaction.user, discord.Member) and interaction.user.get_role(1003785272430960713)
    logger.debug("Check rando league permission for user %s: %s", interaction.user.name,
                 "allowed" if allowed else "denied")
    return allowed

def get_week_number():
    """Returns the current week number (Week starts at 9PM EST)

    Returns:
        int: current week number
    """
    return (pytz.UTC.localize(datetime.utcnow()).astimezone(pytz.timezone('US/Eastern')) +
            timedelta(days=2, hours=3)).isocalendar().week

async def _wrap_query(method, query, *params):
    """Wrap database query execution to log

    Args:
        method (function): The connection method to execute
        query (str): The database query to be executed

    Returns:
        Any: Anything that the connection method is supposed to return
    """
    logger.debug("%s [%s]", query, ", ".join(list(map(str, params))))
    return await method(query, *params)


class RandomizerLeague(commands.Cog, name="Randomizer League"):
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
    async def cog_app_command_error(self, interaction: discord.Interaction,
                                    error: app_commands.errors.AppCommandError):
        if isinstance(error, app_commands.errors.CheckFailure):
            return await interaction.response.send_message("You don't have the permissions to use this command",
                                                           ephemeral=True)

    league = app_commands.Group(name="league", description="BF Rando League commands")

    @league.command(name='set')
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
    @app_commands.describe(week_number="The settings of the week to be set")
    @app_commands.check(is_league_admin_check)
    # pylint: disable=unused-argument
    async def league_set(self, interaction: discord.Interaction,
                         logic_mode: Optional[app_commands.Choice[str]] = None,
                         key_mode: Optional[app_commands.Choice[str]] = None,
                         goal_mode: Optional[app_commands.Choice[str]] = None,
                         spawn: Optional[app_commands.Choice[str]] = None,
                         variation1: Optional[app_commands.Choice[str]] = None,
                         variation2: Optional[app_commands.Choice[str]] = None,
                         variation3: Optional[app_commands.Choice[str]] = None,
                         item_pool: Optional[app_commands.Choice[str]] = None,
                         relic_count: Optional[app_commands.Range[int, 1, 11]] = None,
                         week_number: Optional[app_commands.Range[int, 1, 52]] = None):
        """
        Set league settings for a given week

        Args:
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
            week_number (int, optional): The settings of the week to be wiped. Defaults to None.
        """
        week_number = week_number or get_week_number()
        async with asqlite.connect(DB_FILE) as connection:
            settings = [(week_number, *s) for s in interaction.namespace if not s[0] == "week_number"]
            query = "INSERT INTO league_settings VALUES (?, ?, ?) " \
                    "ON CONFLICT(week_number, name) DO UPDATE SET value = excluded.value " \
                    "ON CONFLICT(week_number, value) DO NOTHING;"
            await _wrap_query(connection.executemany, query, settings)
            message = f"League settings for week {week_number} have successfully been updated!"
            return await interaction.response.send_message(content=message, ephemeral=True)

    @league.command(name='view')
    @app_commands.describe(week_number="The settings of the week to be set")
    @app_commands.check(is_league_admin_check)
    async def league_view(self, interaction: discord.Interaction,
                          week_number:  Optional[app_commands.Range[int, 1, 52]] = None):
        """View rando league settings

        Args:
            interaction (discord.Interaction): discord interaction object
            week_number (int, optional): The settings of the week to be wiped. Defaults to None.
        """
        week_number = week_number or get_week_number()
        async with asqlite.connect(DB_FILE) as connection:
            query = "SELECT * FROM league_settings WHERE week_number = ?;"
            league_settings = await _wrap_query(connection.fetchall, query, week_number)
            if not league_settings:
                message = f"No settings set for week {week_number}"
                return await interaction.response.send_message(content=message, ephemeral=True)
            output = "\n".join([f"{ls['name'].ljust(15)}: {ls['value']}" for ls in league_settings])
            message = f"League settings for week {week_number}\n```{output}```"
            return await interaction.response.send_message(content=message, ephemeral=True)

    @league.command(name='clear')
    @app_commands.describe(week_number="The settings of the week to be wiped")
    @app_commands.check(is_league_admin_check)
    async def league_clear(self, interaction: discord.Interaction,
                           week_number:  Optional[app_commands.Range[int, 1, 52]] = None):
        """Clear rando league settings

        Args:
            interaction (discord.Interaction): discord interaction object
            week_number (int, optional): The settings of the week to be wiped. Defaults to None.
        """
        week_number = week_number or get_week_number()
        async with asqlite.connect(DB_FILE) as connection:
            query = "DELETE FROM league_settings WHERE week_number = ?;"
            await _wrap_query(connection.execute, query, week_number)
            message = f"League settings for week {week_number} have been cleared"
            return await interaction.response.send_message(content=message, ephemeral=True)

    @league.command(name='submit')
    @app_commands.describe(timer="The LiveSplit time (e.g: \"40:43\", \"1:40:43\" or \"1:40:43.630\")")
    @app_commands.describe(vod="The link to the VOD")
    async def league_submit(self, interaction: discord.Interaction,
                            timer: app_commands.Transform[str, TimeFormatTransformer], vod: str):
        """Submit rando league result

        Args:
            interaction (discord.Interaction): discord interaction object
            timer (str): seed timer
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
        week_number = get_week_number()
        timer = "{:02}:{:02}:{:02}.{:03}".format(*timer)
        if any((x['Runner'] == interaction.user.display_name and x['Week Number'] == week_number) for x in records):
            return await interaction.followup.send(content='You already have submitted this week!')

        part = functools.partial(tab.append_row,
                                [week_number, date, interaction.user.display_name, timer, vod],
                                value_input_option="USER_ENTERED")
        await self.bot.loop.run_in_executor(None, part)

        return await interaction.followup.send(content='Submission successful!')

    @league.command(name='seed')
    async def league_seed(self, interaction: discord.Interaction):
        """
        Generate an Ori and the Blind Forest Randomizer seed.
        The seed name and option are set to be compliant with the Rando League rules by default.

        Args:
            interaction (discord.Interaction): discord interaction object
        """
        await interaction.response.defer(ephemeral=True)
        week_number = get_week_number()
        random.seed(week_number)
        seed_name = str(random.randint(1, 10**9))
        random.seed(None)
        async with asqlite.connect(DB_FILE) as connection:
            query = "SELECT * FROM league_settings WHERE week_number = ?;"
            seed_settings = await _wrap_query(connection.fetchall, query, week_number)
            variations = (s['value'] for s in seed_settings if s['name'].startswith('variation'))
            seed_settings = {s['name']: s['value'] for s in seed_settings if not s['name'].startswith('variation')}
            message, files = await self._get_seed_message(seed_name=seed_name, **seed_settings,
                                                          variations=variations)
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
        return f"`{seed_data['seed_header']}`", seed_data['seed_files']

    @league_seed.error
    async def seed_error(self, interaction: discord.Interaction, error: app_commands.errors.AppCommandError):
        """Handler called whenever an error occured while generating a seed

        Args:
            interaction (discord.Interaction): discord interaction object
            error (app_commands.errors.AppCommandError): error raised
        """
        message = "An occured while generating the seed"
        logger.error(message, exc_info=error)
        return await interaction.followup.send(message)

    @league_submit.error
    async def league_submit_error(self, interaction: discord.Interaction, error: app_commands.errors.AppCommandError):
        """Handler called whenever an error occured during the submission process

        Args:
            interaction (discord.Interaction): discord interaction object
            error (app_commands.errors.AppCommandError): error raised
        """
        if isinstance(error, BadTimeArgumentFormat):
            return await interaction.response.send_message("Invalid time format")
        logger.error("An occured during the submission process", exc_info=error)


# pylint: disable=missing-function-docstring
async def setup(bot):
    await bot.add_cog(RandomizerLeague(bot))
