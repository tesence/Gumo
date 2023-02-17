import logging
from datetime import datetime
import io
import random
import re

import discord
from discord.ext import commands

import pytz

from gumo.modules.seed import models
from gumo import api
from gumo.api import bf_randomizer

logger = logging.getLogger(__name__)

HELP_STRING = """
    Defaults options are: `Standard,Clues,ForceTrees`

    **Logic Modes**: `casual`, `standard`, `expert`, `master`, `glitched`

    **Key Modes**: `default`, `shards`, `limitkeys`, `clues`

    **Goal Modes**: `forcetrees` (or `ft`), `worldtour` (or `wt`), `forcemaps` (or `fm`), `warmthfrags` (or `wf`)

    **Variations**: `starved`, `ohko`, `0xp`, `closeddungeons`, `extracopies`, `strictmapstones`, `tpstarved`, `skipfinalescape`, `wallstarved`, `grenadestarved`

    **Logic Paths**
    casual: `casual-core`, `casual-dboost`
    standard: `standard-core`, `standard-dboost`, `standard-lure`, `standard-abilities`
    expert: `expert-core`, `expert-dboost`, `expert-lure`, `expert-abilities`
    master: `master-core`, `master-dboost`, `master-lure`, `master-abilities`
    misc: `dbash`, `gjump`, `timedlevel`, `insane`

    **Item Pools**: `standard`, `competitive`, `bonuslite`, `extrabonus`, `hard`
"""


class BFRandomizer(commands.Cog, name="Blind Forest Randomizer"):

    def __init__(self, bot):
        self.bot = bot
        self.api_client = bf_randomizer.BFRandomizerApiClient()

    @staticmethod
    def _pop_seed_names(body):
        seed_names = re.findall('"([^"]*)"', body)

        # If at least one string between quotes is matched, use the first match as seed name
        # Use a random number otherwise
        if seed_names:
            # Remove every seed name candidate to keep seed flags only
            for seed_name in seed_names:
                body = body.replace(f"\"{seed_name}\"", "")
            seed_name = seed_names[0]
        else:
            seed_name = str(random.randint(1, 10**9))

        return seed_name, body

    _SEED_HELP_TEXT = "Generate a seed using a random seed name"

    @commands.command(help=f"{_SEED_HELP_TEXT}\n{HELP_STRING}")
    async def seed(self, ctx, *, body=""):
        seed_name, body = self._pop_seed_names(body)
        await self._seed(ctx, body, seed_name)

    _DAILY_HELP_TEXT = "Generate a seed using the date as seed name"

    @commands.command(help=f"{_DAILY_HELP_TEXT}\n{HELP_STRING}")
    async def daily(self, ctx, *, body=""):
        _, body = self._pop_seed_names(body)
        # pylint: disable=no-value-for-parameter
        seed_name = pytz.UTC.localize(datetime.now()).astimezone(pytz.timezone('US/Pacific')).strftime("%Y-%m-%d")
        await self._seed(ctx, body, seed_name)

    async def _seed(self, ctx, body, seed_name):
        try:
            async with ctx.typing():
                seed_data = await self._get_seed_data(body, seed_name)
                await self._send_seed(ctx, seed_data)
        except (api.APIError, discord.HTTPException):
            logger.exception("An error has occurred while generating the seed")

    async def _get_seed_data(self, body, seed_name):
        # Split and reduce all the flags to match them with reference lists
        flags = {f.lower().replace('_', '').replace('-', '') for f in body.split()}

        logic_mode = None
        key_mode = None
        item_pool = None
        goal_modes = []
        variations = []
        logic_paths = []

        for flag in flags:

            if flag in models.LOGIC_MODES:
                logic_mode = flag

            elif flag in models.KEY_MODES:
                key_mode = flag

            elif flag in models.ITEM_POOLS:
                item_pool = flag

            elif flag in models.GOAL_MODES:
                goal_modes.append(flag)

            elif flag in models.VARIATIONS:
                variations.append(flag)

            elif flag in models.PATH_DIFFICULTIES:
                logic_paths.append(flag)

        logger.debug(f"Detected flags: seed_name=\"{seed_name}\" logic_mode=\"{logic_mode}\" "
                     f"key_mode=\"{key_mode}\" item_pool={item_pool} goal_modes={goal_modes} "
                     f"variations={variations} logic_paths={logic_paths}")

        return await self.api_client.get_data(seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                                              item_pool=item_pool, goal_modes=goal_modes, variations=variations,
                                              logic_paths=logic_paths)

    async def _send_seed(self, ctx, seed_data):
        # Store the data into file buffers
        seed_buffer = io.BytesIO(bytes(seed_data['players'][0]['seed'], encoding="utf8"))
        spoiler_buffer = io.BytesIO(bytes(seed_data['players'][0]['spoiler'], encoding="utf8"))

        # Send the files in the channel
        seed_header = seed_data['players'][0]['seed'].split("\n")[0]
        message = f"`{seed_header}`\n"
        message += f"**Spoiler link**: {bf_randomizer.SEEDGEN_API_URL + seed_data['players'][0]['spoiler_url']}\n"
        if "map_url" in seed_data and "history_url" in seed_data:
            message += f"**Map**: {bf_randomizer.SEEDGEN_API_URL + seed_data['map_url']}\n"
            message += f"**History**: {bf_randomizer.SEEDGEN_API_URL + seed_data['history_url']}\n"

        await ctx.reply(message, mention_author=False, files=[discord.File(seed_buffer, filename="randomizer.dat"),
                                                              discord.File(spoiler_buffer, filename="spoiler.dat")])
