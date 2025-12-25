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

ORI_GUID_ID = 116250700685508615
ORI_RANDO_LEAGUE_CHANNEL_ID = 1362090460423913522


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
    """Date format transformer"""

    # pylint: disable=arguments-differ
    async def transform(self, interaction: discord.Interaction, value: str):
        return parser.parse(value).replace(hour=21, minute=0, second=0)

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

def get_current_week_start_date():
    """Return the date when the current league week started (previous friday)

    Returns:
        date: Friday of the current week
    """
    return get_week_start_date(datetime.now(EASTERN_TZ))

def get_week_start_date(date):
    """Return the date when the given league week started (previous friday)

    Returns:
        date: Friday of the current week
    """
    date = date - timedelta(hours=21)
    last_friday = date - timedelta(days=(date.weekday() - 4 + 7) % 7)
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

async def should_extend_week(date):
    """Whether the week should be extended

    If the seed number of the next week is forced to be equal to the computed seed number of the current
    week

    Args:
        date (datetime): date of the current week

    Returns:
        bool: True if week should be extended, False otherwise
    """
    current_week_start_date = get_week_start_date(date)
    next_week_start_date = get_week_start_date(date + timedelta(days=7))
    async with asqlite.connect(DB_FILE) as connection:
        query = "SELECT value FROM league_settings WHERE date = ? AND name = 'seed_name';"
        row = await _wrap_query(connection.fetchone, query, next_week_start_date)
        current_seed_name = str(random.Random(current_week_start_date).randint(1, 10**9))
        return row is not None and row[0] == current_seed_name

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
        self.ready = asyncio.Event()
        self._week_refresh.start()  # pylint: disable=no-member
        self._reminder.start()  # pylint: disable=no-member

    async def cog_load(self):
        await self._refresh_cached_data()

    async def cog_app_command_error(self, interaction: discord.Interaction,
                                    error: app_commands.errors.AppCommandError):
        if isinstance(error, app_commands.errors.CheckFailure):
            return await interaction.response.send_message("You don't have the permissions to use this command",
                                                           ephemeral=True)

    # @tasks.loop(hours=1)
    @tasks.loop(time=time(hour=21, minute=0, second=0, tzinfo=EASTERN_TZ))
    async def _reminder(self):
        """Remind players who haven't submitted 24h before the end of the week"""
        date = datetime.now(EASTERN_TZ)

        if not date.weekday() == 3:
            return

        if await should_extend_week(date):
            return

        week_start_date = get_week_start_date(date)
        submissions = await self._get_submissions(week_start_date)
        if not submissions:
            return

        await self.ready.wait()

        runners = await self._get_runners()
        missing_runners = set(runners) ^ set(submissions)

        if not missing_runners:
            return

        deadline = (datetime.now(EASTERN_TZ) + timedelta(days=1)).replace(hour=21, minute=0, second=0)
        timestamp = int(deadline.timestamp())

        missing_members = []
        for runner in sorted(missing_runners):
            member = self.bot.get_guild(ORI_GUID_ID).get_member_named(runner)
            if member:
                missing_members.append(member.mention)
            else:
                logger.warning("Cannot retrieve member for username '%s'", runner)

        reminder =   "## Reminder of the week\n\n"
        reminder += f"Remaining players: {', '.join(missing_members)}\n"
        reminder += f"### You have time to submit until <t:{timestamp}:f>"

        # await (await self.bot.application_info()).owner.send(reminder)
        await self.bot.get_channel(ORI_RANDO_LEAGUE_CHANNEL_ID).send(reminder)

    @_reminder.error
    async def _reminder_error(self, error):
        """Reminder error handler

        Args:
            error (Exception): Exception raised by the reminder method
        """
        logger.exception("Reminder task failed:", exc_info=error)
        await asyncio.sleep(120)

        try:
            await self._reminder()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Retry also failed:", exc_info=e)

    # @tasks.loop(hours=1)
    @tasks.loop(time=time(hour=21, minute=0, second=0, tzinfo=EASTERN_TZ))
    async def _week_refresh(self):
        """Weekly task that auto DNF runners that haven't submitted in time"""
        date = datetime.now(EASTERN_TZ)

        if not date.weekday() == 4:
            return

        await self._refresh_cached_data()

        if await should_extend_week(date - timedelta(hours=1)):
            return

        week_start_date = get_week_start_date(date - timedelta(hours=1))

        submissions = await self._get_submissions(week_start_date)
        if not submissions:
            return

        runners = await self._get_runners()
        missing_runners = set(runners) ^ set(submissions)
        missing_submissions = [[week_start_date, "n/a", runner, "DNF", "n/a"] for runner in missing_runners]
        await self._submit(*missing_submissions)
        logger.info("Submitting missing submissions for week %s: %s", week_start_date, missing_submissions)

    @_week_refresh.error
    async def _week_refresh_error(self, error):
        """Week refresh error handler

        Args:
            error (Exception): Exception raised by the week refresh method
        """
        logger.exception("Week refresh task failed:", exc_info=error)
        await asyncio.sleep(120)

        try:
            await self._week_refresh()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Retry also failed:", exc_info=e)

    async def _refresh_cached_data(self):
        """Refresh all the cached data:
           - Current week seed data
           - Current season number
        """
        self._seed_data = await self._league_seed()
        logger.info("Cached seed data refreshed: %s", self._seed_data['seed_header'])
        self._active_season_number = await self._get_active_season_number()
        logger.info("Cached active season number refreshed: %s", self._active_season_number)
        self.ready.set()

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
        worksheets = (await self._get_spreadsheet()).worksheets()
        return int(worksheets[0].title[1])

    async def _get_runners(self):
        """Retrieve Rando League runners

        Returns:
            list: Rando League runners.
        """
        worksheet = await self._get_worksheet("Names")
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
    @models.add_seed_options
    @app_commands.describe(date="The settings of the week to be set")
    @app_commands.describe(seed_name="A string to be used as seed")
    @app_commands.check(is_league_admin_check)
    # pylint: disable=unused-argument
    async def league_set(self, interaction: discord.Interaction,
                         seed_name: Optional[str] = None,
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
            week_start_date (datetime, optional): The settings of the week to be wiped. Defaults to None.
        """
        week_start_date = get_week_start_date(date) if date else get_current_week_start_date()
        async with asqlite.connect(DB_FILE) as connection:
            settings = [(week_start_date, *s) for s in interaction.namespace if not s[0] == "date"]
            query = "INSERT INTO league_settings (date, name, value) VALUES (?, ?, ?) " \
                    "ON CONFLICT(date, name) DO UPDATE SET value = excluded.value " \
                    "ON CONFLICT(date, value) DO NOTHING;"
            await _wrap_query(connection.executemany, query, settings)
            message = f"League settings for week {week_start_date} have successfully been updated!"
            await interaction.response.send_message(content=message, ephemeral=True)

        if week_start_date == get_current_week_start_date():
            await self._refresh_cached_data()

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

        if week_start_date == get_current_week_start_date():
            await self._refresh_cached_data()

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
        if interaction.user.name in await self._get_submissions(week_start_date):
            return await interaction.followup.send(content='You already have submitted this week!')

        await self._submit([week_start_date, date, interaction.user.name, timer, vod])

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
        async with asqlite.connect(DB_FILE) as connection:
            query = "SELECT * FROM league_settings WHERE date = ?;"
            seed_settings = await _wrap_query(connection.fetchall, query, week_start_date)
            variations = (s['value'] for s in seed_settings if s['name'].startswith('variation'))
            seed_settings = {s['name']: s['value'] for s in seed_settings if not s['name'].startswith('variation')}
            seed_name = seed_settings.pop('seed_name', None) or str(random.Random(week_start_date).randint(1, 10**9))
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
