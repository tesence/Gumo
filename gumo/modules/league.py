"""
Provide Ori and the Blind Forest rando league commands
- "/league clear": Clear rando league seeds settings (admin)
- "/league seed": Generate a seed using randomizer settings
- "/league set": Set rando league seeds settings (admin)
- "/league submit": Submit a rando league result
- "/league view": View rando league seeds settings (admin)
"""

import logging
from datetime import datetime, time, timedelta
import functools
import io
import os
import random
import re
from typing import Optional
import zoneinfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

import asqlite
from dateutil import parser
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

class DateTransformer(app_commands.Transformer):

    async def transform(self, interaction: discord.Interaction, value: str):
        return parser.parse(value)

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
    return (datetime.now(EASTERN_TZ) + timedelta(days=2, hours=3)).isocalendar().week

def get_current_week_start_date():
    return get_week_start_date(datetime.now(EASTERN_TZ))

def get_week_start_date(date):
    now = date - timedelta(hours=21)
    last_friday = now - timedelta(days=(now.weekday() - 4 + 7) % 7)
    return last_friday.strftime('%Y-%m-%d')

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
        self._seed_data = None
        self._active_season_number = None

        self.credentials = service_account.Credentials.from_service_account_file(
            os.getenv("GUMO_BOT_GOOGLE_API_SA_FILE"),
            scopes = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
        )
        self._week_refresh.start()  # pylint: disable=no-member

    async def cog_load(self):
        await self._refresh_cached_data()

    async def cog_app_command_error(self, interaction: discord.Interaction,
                                    error: app_commands.errors.AppCommandError):
        if isinstance(error, app_commands.errors.CheckFailure):
            return await interaction.response.send_message("You don't have the permissions to use this command",
                                                           ephemeral=True)

    @tasks.loop(time=time(hour=20, minute=59, second=30, tzinfo=EASTERN_TZ))
    async def _week_refresh(self):
        """Weekly task that auto DNF runners that haven't submitted in time"""

        if not datetime.now(EASTERN_TZ).weekday() == 4:
            return

        week_start_date = get_current_week_start_date()
        submissions = await self._get_submissions(week_start_date)

        # DNF runners only if there is at least one submission. If there is no submission, it means the season is over.
        if submissions:
            runners = await self._get_runners()
            missing_runners = set(runners) ^ set(submissions)
            missing_submissions = [[week_start_date, "n/a", runner, "DNF", "n/a"] for runner in missing_runners]
            await self._submit(*missing_submissions)
            logger.info("Submitting missing submissions for week %s: %s", week_start_date, missing_submissions)

        await self._refresh_cached_data()

    async def _refresh_cached_data(self):
        """Refresh all the cached data:
           - Current week seed data
           - Current season number
        """
        self._seed_data = await self._league_seed()
        logger.info("Cached seed data refreshed: %s", self._seed_data['seed_header'])
        self._active_season_number = await self._get_active_season_number()
        logger.info("Cached active season number refreshed: %s", self._active_season_number)

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

    async def _get_active_season_number(self):
        """Retrieve the active season number

        Returns:
            int: active season number
        """
        worksheet_title_pattern = "^S([0-9]+) .*$"
        worksheets = (await self._get_spreadsheet()).worksheets()
        filtered_worksheet_titles = [wk.title for wk in worksheets if re.match(worksheet_title_pattern, wk.title)]
        return int(re.search(worksheet_title_pattern, sorted(filtered_worksheet_titles)[-1]).group(1))

    async def _get_runners(self):
        """Retrieve Rando League runners

        Returns:
            list: Rando League runners.
        """
        worksheet = await self._get_worksheet(f"S{self._active_season_number} Scores")
        part = functools.partial(worksheet.col_values, 1)
        return (await self.bot.loop.run_in_executor(None, part))[2:]

    async def _get_submissions(self, date: datetime):
        """Retrieve Rando League submissions

        Args:
            date (date): The settings of the week to be wiped. Defaults to None.

        Returns:
            list: List of submissions
        """
        worksheet = await self._get_worksheet(f"S{self._active_season_number} Raw Data")
        records = await self.bot.loop.run_in_executor(None, worksheet.get_all_records)
        return [r['Runner'] for r in records if r['Week'] == date]

    async def _submit(self, *submissions):
        """Sumbit a list of Rando League submissions

        Args:
            submissions (list): List of Rando League submissions to submit.
        """
        worksheet = await self._get_worksheet(f"S{self._active_season_number} Raw Data")
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
    @app_commands.describe(date="The settings of the week to be set")
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
                         date: app_commands.Transform[datetime, DateTransformer] = None):
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
            week_start_date (datetime, optional): The settings of the week to be wiped. Defaults to None.
        """
        week_start_date = get_week_start_date(date) if date else get_current_week_start_date()
        async with asqlite.connect(DB_FILE) as connection:
            settings = [(week_start_date, *s) for s in interaction.namespace if not s[0] == "week_start_date"]
            query = "INSERT INTO league_settings (date, name, value) VALUES (?, ?, ?) " \
                    "ON CONFLICT(date, name) DO UPDATE SET value = excluded.value " \
                    "ON CONFLICT(date, value) DO NOTHING;"
            await _wrap_query(connection.executemany, query, settings)
            message = f"League settings for week {week_start_date} have successfully been updated!"
            await interaction.response.send_message(content=message, ephemeral=True)
        if week_start_date == get_current_week_start_date(): await self._refresh_cached_data()

    @league.command(name='view')
    @app_commands.describe(date="The settings of the week to be set")
    @app_commands.check(is_league_admin_check)
    async def league_view(self, interaction: discord.Interaction,
                          date: app_commands.Transform[datetime, DateTransformer] = None):
        """View rando league settings

        Args:
            interaction (discord.Interaction): discord interaction object
            week_start_date (datetime, optional): The settings of the week to be wiped. Defaults to None.
        """
        week_start_date = get_week_start_date(date) if date else get_current_week_start_date()
        async with asqlite.connect(DB_FILE) as connection:
            query = "SELECT * FROM league_settings WHERE date = ?;"
            league_settings = await _wrap_query(connection.fetchall, query, week_start_date)
            if not league_settings:
                message = f"No settings set for week {week_start_date}"
                return await interaction.response.send_message(content=message, ephemeral=True)
            output = "\n".join([f"{ls['name'].ljust(15)}: {ls['value']}" for ls in league_settings])
            message = f"League settings for week {week_start_date}\n```{output}```"
            await interaction.response.send_message(content=message, ephemeral=True)

    @league.command(name='clear')
    @app_commands.describe(date="The settings of the week to be wiped")
    @app_commands.check(is_league_admin_check)
    async def league_clear(self, interaction: discord.Interaction,
                           date: app_commands.Transform[datetime, DateTransformer] = None):
        """Clear rando league settings

        Args:
            interaction (discord.Interaction): discord interaction object
            week_start_date (datetime, optional): The settings of the week to be wiped. Defaults to None.
        """
        week_start_date = get_week_start_date(date) if date else get_current_week_start_date()
        async with asqlite.connect(DB_FILE) as connection:
            query = "DELETE FROM league_settings WHERE date = ?;"
            await _wrap_query(connection.execute, query, week_start_date)
            message = f"League settings for week {week_start_date} have been cleared"
            await interaction.response.send_message(content=message, ephemeral=True)
        if week_start_date == get_current_week_start_date(): await self._refresh_cached_data()

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

        date = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        week_start_date = get_current_week_start_date()
        timer = "DNF" if timer == "DNF" else "{:02}:{:02}:{:02}.{:03}".format(*timer)
        if interaction.user.display_name in await self._get_submissions(week_start_date):
            return await interaction.followup.send(content='You already have submitted this week!')

        await self._submit([week_start_date, date, interaction.user.display_name, timer, vod])

        message = f"Submission successful! You can view this week's spoiler [here]({self._seed_data['spoiler_url']})"
        await interaction.followup.send(content=message)

    @league.command(name='seed')
    async def league_seed(self, interaction: discord.Interaction):
        """
        Generate an Ori and the Blind Forest Randomizer seed.
        The seed name and option are set to be compliant with the Rando League rules by default.

        Args:
            interaction (discord.Interaction): discord interaction object
        """
        await interaction.response.defer(ephemeral=True)
        seed_buffer = io.BytesIO(bytes(self._seed_data['seed_file_content'], encoding="utf8"))
        seed_file = discord.File(seed_buffer, filename='randomizer.dat')
        return await interaction.followup.send(content=f"`{self._seed_data['seed_header']}`", files=[seed_file])

    async def _league_seed(self):
        """
        Generate the current week seed name and params and returns the corresponding seed data.

        Returns:
            dict: seed data
        """
        week_start_date = get_current_week_start_date()
        random.seed(week_start_date)
        seed_name = str(random.randint(1, 10**9))
        random.seed(None)
        async with asqlite.connect(DB_FILE) as connection:
            query = "SELECT * FROM league_settings WHERE date = ?;"
            seed_settings = await _wrap_query(connection.fetchall, query, week_start_date)
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
