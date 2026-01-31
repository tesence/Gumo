"""
Define a Google spreadsheet helper class
"""

from concurrent import futures
import functools
import logging
import os

import gspread
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class SpreadsheetManager:
    """Helper class to interact with the Ori Rando League spreadsheet"""

    def __init__(self, loop):
        self._credentials = service_account.Credentials.from_service_account_file(
            os.getenv("GUMO_BOT_GOOGLE_API_SA_FILE"),
            scopes = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
        )
        self._loop = loop
        self._executor = futures.ThreadPoolExecutor(max_workers=1)
        self._spreadsheet = None
        self.active_season_number = None

    async def _run_async(self, fn, *args, **kwargs):
        """Run a blocking call inside a custom executor.

        Args:
            fn (function): The method to run in the custom executor

        Returns:
            Any: The result of the blocking call
        """
        return await self._loop.run_in_executor(self._executor, functools.partial(fn, *args, **kwargs))

    async def init(self):
        """Authenticate to Google Sheets and open the ori rando league spreadsheet."""
        client = await self._run_async(gspread.authorize, self._credentials)
        self._spreadsheet = await self._run_async(client.open, title="Ori Rando League Leaderboard")

    async def refresh_active_season_number(self):
        """Retrieve the current rando league season number.

        Uses the first tab in the list as reference
        """
        worksheets = await self._run_async(self._spreadsheet.worksheets)
        self.active_season_number = int(worksheets[0].title.split()[0][1:])

    async def get_runners(self):
        """Retrieve Rando League runners.

        Returns:
            list: Rando League runners
        """
        worksheet = await self._run_async(self._spreadsheet.worksheet, f"S{self.active_season_number} Names")
        first_column = await self._run_async(worksheet.col_values, 1)
        return first_column[2:]

    async def get_submissions(self, week_start_date):
        """Retrieve Rando League submissions.

        Args:
            week_start_date (str): String in YYYY-MM-DD format

        Returns:
            list: List of submissions
        """
        worksheet = await self._run_async(self._spreadsheet.worksheet, f"S{self.active_season_number} Raw Data")
        records = await self._run_async(worksheet.get_all_records)
        return [r for r in records if r['Week'] == week_start_date]

    async def submit(self, *submissions):
        """Submit a list of Rando League submissions.

        Args:
            submissions (list): List of Rando League submissions to submit
        """
        worksheet = await self._run_async(self._spreadsheet.worksheet, f"S{self.active_season_number} Raw Data")
        await self._run_async(worksheet.append_rows, submissions, value_input_option="USER_ENTERED")

    async def get_missing_runners(self, week_start_date):
        """Return the list of runner names who have not submitted yet.

        Args:
            week_start_date (str): String in YYYY-MM-DD format

        Returns:
            missing_runners (list): List of runners who haven't submitted yet
        """
        submissions = await self.get_submissions(week_start_date)
        if not submissions:
            return []
        runners = await self.get_runners()
        missing_runners = list(set(runners) ^ set(submission['Runner'] for submission in submissions))
        logger.info("Runners who have not submitted yet for week %s: %s", week_start_date, missing_runners)
        return missing_runners

    async def auto_dnf(self, week_start_date):
        """Declare runners who have not submitted yet forfeited.

        Args:
            week_start_date (str): FString in YYYY-MM-DD format
        """
        missing_runners = await self.get_missing_runners(week_start_date)
        missing_submissions = [[week_start_date, "n/a", runner, "DNF", "n/a"] for runner in missing_runners]
        logger.info("Submitting missing submissions for week %s: %s", week_start_date, missing_submissions)
        await self.submit(*missing_submissions)
