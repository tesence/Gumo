"""
Provide Ori and the Blind Forest rando league commands
- "/league clear": Clear rando league seeds settings (admin)
- "/league seed": Generate a seed using randomizer settings
- "/league set": Set rando league seeds settings (admin)
- "/league submit": Submit a rando league result
- "/league view": View rando league seeds settings (admin)

"""

import asyncio
import logging
from datetime import datetime, time, timedelta
import functools
import os
import random
import re
from typing import Optional
import zoneinfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

import asqlite
import gspread
from google.oauth2 import service_account

from gumo import api
from gumo.api import models

logger = logging.getLogger(__name__)

DB_FILE = os.getenv('GUMO_BOT_DB_FILE')

EASTERN_TZ = zoneinfo.ZoneInfo('US/Eastern')


class BadTimeArgumentFormat(app_commands.AppCommandError):
    """Bad duration format Exception"""

# pylint: disable=abstract-method
class TimeFormatTransformer(app_commands.Transformer):
    """Duration format transformer"""

    # pylint: disable=arguments-differ
    async def transform(self, interaction: discord.Interaction, value: str):
        if value.lower() == "dnf":
            return "DNF"

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
    # XMAS HOTFIX
    week_number = (datetime.now(EASTERN_TZ) + timedelta(days=2, hours=3)).isocalendar().week
    return 52 if week_number == 1 else week_number

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
        self.week_refresh.start()  # pylint: disable=no-member

    async def cog_app_command_error(self, interaction: discord.Interaction,
                                    error: app_commands.errors.AppCommandError):
        if isinstance(error, app_commands.errors.CheckFailure):
            return await interaction.response.send_message("You don't have the permissions to use this command",
                                                           ephemeral=True)

    @tasks.loop(time=time(hour=21, minute=0, second=30, tzinfo=EASTERN_TZ))
    async def week_refresh(self):
        """Weekly task that auto DNF runners that haven't submitted in time"""

        if not datetime.now(EASTERN_TZ).weekday() == 4:
            return

        week_number = get_week_number() - 1
        runners = await self._get_runners()
        submissions = await self._get_submissions(week_number)
        missing_runners = set(runners) ^ set(submissions)
        missing_submissions = [[week_number, "n/a", runner, "DNF", "n/a"] for runner in missing_runners]
        await self._submit(*missing_submissions)
        logger.info("Submitting missing submissions for week %s: %s", week_number, missing_submissions)

    @week_refresh.before_loop
    async def before_week_refresh(self):
        """Wait for Bot to be ready before starting the tasks"""
        await self.bot.wait_until_ready()

    async def _get_spreadsheet(self):
        """Retrieve the Rando League spreadsheet

        Returns:
            gspread.Spreadsheet: Rando League spreadsheet.
        """
        part = functools.partial(gspread.authorize, self.credentials)
        client = await self.bot.loop.run_in_executor(None, part)
        part = functools.partial(client.open, title="Ori Rando League Leaderboard")
        return await self.bot.loop.run_in_executor(None, part)

    async def _get_worksheet(self, name: str):
        """Retrieve a Rando League worksheet

        Returns:
            gspread.Worksheet: Rando League worksheet.
        """
        spreadsheet = await self._get_spreadsheet()
        part = functools.partial(spreadsheet.worksheet, name)
        return await self.bot.loop.run_in_executor(None, part)

    async def _get_runners(self):
        """Retrieve Rando League runners

        Returns:
            list: Rando League runners.
        """
        worksheet = await self._get_worksheet("S2 Leaderboard")
        part = functools.partial(worksheet.col_values, 1)
        return (await self.bot.loop.run_in_executor(None, part))[2:]

    async def _get_submissions(self, week_number: int):
        """Retrieve Rando League submissions

        Args:
            week_number (int): The settings of the week to be wiped. Defaults to None.

        Returns:
            list: List of submissions
        """
        worksheet = await self._get_worksheet("S2 Raw Data")
        records = await self.bot.loop.run_in_executor(None, worksheet.get_all_records)
        return [r['Runner'] for r in records if r['Week Number'] == week_number]

    async def _submit(self, *submissions):
        """Sumbit a list of Rando League submissions

        Args:
            submissions (list): List of Rando League submissions to submit.
        """
        worksheet = await self._get_worksheet("S2 Raw Data")
        part = functools.partial(worksheet.append_rows, submissions, value_input_option="USER_ENTERED")
        await self.bot.loop.run_in_executor(None, part)

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

        seed_task = asyncio.create_task(self._league_seed())

        date = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        week_number = get_week_number()
        timer = "DNF" if timer == "DNF" else "{:02}:{:02}:{:02}.{:03}".format(*timer)
        if interaction.user.display_name in await self._get_submissions(week_number):
            return await interaction.followup.send(content='You already have submitted this week!')

        await self._submit([week_number, date, interaction.user.display_name, timer, vod])
        seed_data = await seed_task

        message = f"Submission successful! You can view this week's spoiler [here]({seed_data['spoiler_url']})"
        return await interaction.followup.send(content=message)

    @league.command(name='seed')
    async def league_seed(self, interaction: discord.Interaction):
        """
        Generate an Ori and the Blind Forest Randomizer seed.
        The seed name and option are set to be compliant with the Rando League rules by default.

        Args:
            interaction (discord.Interaction): discord interaction object
        """
        await interaction.response.defer(ephemeral=True)
        seed_data = await self._league_seed()
        return await interaction.followup.send(content=f"`{seed_data['seed_header']}`", files=seed_data['seed_files'])

    async def _league_seed(self):
        """
        Generate the current week seed name and params and returns the corresponding seed data.

        Returns:
            dict: seed data
        """
        week_number = get_week_number()
        random.seed(week_number)
        seed_name = str(random.randint(1, 10**9))
        random.seed(None)
        async with asqlite.connect(DB_FILE) as connection:
            query = "SELECT * FROM league_settings WHERE week_number = ?;"
            seed_settings = await _wrap_query(connection.fetchall, query, week_number)
            variations = (s['value'] for s in seed_settings if s['name'].startswith('variation'))
            seed_settings = {s['name']: s['value'] for s in seed_settings if not s['name'].startswith('variation')}
            return await self.api_client.get_seed(seed_name=seed_name, **seed_settings, variations=variations)

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
            return await interaction.response.send_message("Invalid time format", ephemeral=True)
        logger.error("An occured during the submission process", exc_info=error)


# pylint: disable=missing-function-docstring
async def setup(bot):
    await bot.add_cog(RandomizerLeague(bot))
