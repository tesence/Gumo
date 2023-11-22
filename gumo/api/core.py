"""
Define a client to interact with the Ori and the Blind Forest Randomizer API
"""

import io
import logging
from urllib import parse
import random

import discord

import aiohttp

from gumo.api import models

logger = logging.getLogger(__name__)

SEEDGEN_API_URL = "https://orirando.com"

PATHS_INHERITENCE = {}
PATHS_INHERITENCE['Casual'] = [v for k, v in models.LOGIC_PATHS.items() if k.startswith('Casual')]
PATHS_INHERITENCE['Standard'] = PATHS_INHERITENCE['Casual'] + \
                                [v for k, v in models.LOGIC_PATHS.items() if k.startswith('Standard')]
PATHS_INHERITENCE['Expert'] = PATHS_INHERITENCE['Standard'] + \
                              [v for k, v in models.LOGIC_PATHS.items() if k.startswith('Expert')] + \
                              [models.LOGIC_PATHS['Dbash']]
PATHS_INHERITENCE['Master'] = PATHS_INHERITENCE['Expert'] + \
                              [v for k, v in models.LOGIC_PATHS.items() if k.startswith('Master')]
PATHS_INHERITENCE['Glitched'] = PATHS_INHERITENCE['Expert'] + \
                                [models.LOGIC_PATHS['Glitched'], models.LOGIC_PATHS['Timed-Level']]


class BFRandomizerApiClient:
    """API Client class to interact with the Blind Forest Randomizer API"""

    def __init__(self, *args, **kwargs):
        self._session = aiohttp.ClientSession(*args, **kwargs, raise_for_status=True)

    async def _get_seed_data(self, seed_name: str = None, logic_mode: str = None, key_mode: str = None,
                       goal_mode: str = None, spawn: str = None, variations: tuple = (), item_pool: str = None,
                       relic_count: int = None):
        """
        Request a seed data to the Blind Forest Randomizer API

        Args:
            seed_name (str, optional): Seed name. Defaults to None.
            logic_mode (str, optional): Randomizer logic mode. Defaults to None.
            key_mode (str, optional): Randomizer key mode. Defaults to None.
            goal_mode (str, optional): Randomizer goal mode. Defaults to None.
            spawn (str, optional): Randomizer spawn location. Defaults to None.
            variations (tuple, optional): Randomizer variations. Defaults to ().
            item_pool (str, optional): Randomizer item pool. Defaults to None.
            relic_count (int, optional): Randomizer relic count (World Tour only). Defaults to None.

        Returns:
            dict: The API response content
        """
        seed_name = seed_name or str(random.randint(1, 10**9))
        logic_mode = logic_mode or "Standard"
        key_mode = key_mode or "Clues"
        goal_mode = goal_mode or "Force Trees"
        spawn = spawn or "Glades"
        item_pool = item_pool or "Standard"
        relic_count = relic_count or 8

        params = {('seed', seed_name)}

        for path in PATHS_INHERITENCE[logic_mode]:
            params.add(('path', path))

        params.add(('key_mode', models.KEY_MODES[key_mode]))
        params.add(('var', models.GOAL_MODES[goal_mode]))
        params.add(('pool_preset', models.ITEM_POOLS[item_pool]))
        params.add(('spawn', spawn))

        if goal_mode == "World Tour":
            params.add(('relics', relic_count))

        # Variations
        for variation in variations:
            params.add(('var', models.VARIATIONS[variation]))

        # Handle all the preset specificities
        if logic_mode == "Casual":
            params.add(('cell_freq', "20"))
        elif logic_mode == "Standard":
            params.add(('cell_freq', "40"))
        elif logic_mode == "Expert":
            pass
        elif logic_mode == "Master":
            params.add(("path_diff", models.PATH_DIFFICULTIES['Hard']))
            params.add(('var', models.VARIATIONS['Starved']))
        elif logic_mode == "Glitched":
            params.add(("path_diff", models.PATH_DIFFICULTIES['Hard']))

        url = f"{SEEDGEN_API_URL}/generator/json?{parse.urlencode(list(params))}"
        logger.info("Outgoing request: %s", url)
        resp = await self._session.request('GET', url)
        return await resp.json()

    async def get_seed(self, seed_name: str = None, logic_mode: str = None, key_mode: str = None,
                             goal_mode: str = None, spawn: str = None, variations: tuple = (),
                             item_pool: str = None, relic_count: int = None):
        """Returns the seed data splitted into different dictionnary keys

        Args:
            seed_name (str, optional): Seed name. Defaults to None.
            logic_mode (str, optional): Randomizer logic mode. Defaults to None.
            key_mode (str, optional): Randomizer key mode. Defaults to None.
            goal_mode (str, optional): Randomizer goal mode. Defaults to None.
            spawn (str, optional): Randomizer spawn location. Defaults to None.
            variations (tuple, optional): Randomizer variations. Defaults to ().
            item_pool (str, optional): Randomizer item pool. Defaults to None.
            relic_count (int, optional): Randomizer relic count (World Tour only). Defaults to None.

        Returns:
            dict: The seed data in a dictonary format
        """
        seed_data = await self._get_seed_data(seed_name=seed_name, logic_mode=logic_mode, key_mode=key_mode,
                                              goal_mode=goal_mode, spawn=spawn, variations=variations,
                                              item_pool=item_pool, relic_count=relic_count)
        seed_buffer = io.BytesIO(bytes(seed_data['players'][0]['seed'], encoding="utf8"))
        return {
            'seed_header': seed_data['players'][0]['seed'].split("\n")[0],
            'spoiler_url': f"{SEEDGEN_API_URL}{seed_data['players'][0]['spoiler_url']}",
            'map_url': f"{SEEDGEN_API_URL}{seed_data['map_url']}",
            'history_url': f"{SEEDGEN_API_URL}{seed_data['history_url']}",
            'seed_files': [discord.File(seed_buffer, filename='randomizer.dat')]
        }
