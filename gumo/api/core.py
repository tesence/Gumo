import logging
from urllib import parse

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


    def __init__(self, *args, **kwargs):
        self._session = aiohttp.ClientSession(*args, **kwargs, raise_for_status=True)


    async def get_data(self, seed_name, logic_mode=None, key_mode=None, goal_mode=None, spawn=None,  variations=(),
                       item_pool=None):

        params = {('seed', seed_name)}

        for path in PATHS_INHERITENCE[logic_mode]:
            params.add(('path', path))

        params.add(('key_mode', models.KEY_MODES[key_mode]))
        params.add(('var', models.GOAL_MODES[goal_mode]))
        params.add(('pool_preset', models.ITEM_POOLS[item_pool]))
        params.add(('spawn', spawn))

        # Variations
        for variation in variations:
            params.add(('var', models.VARIATIONS[variation]))

        # Handle all the preset specificities
        if logic_mode == "Casual":
            params.add(('cell_freq', "20"))
        elif logic_mode == "Standard":
            params.add(('cell_freq', "40"))
        elif logic_mode == "Expert":
            params.add(('cell_freq', "256"))
        elif logic_mode == "Master":
            params.add(('cell_freq', "256"))
            params.add(("path_diff", models.PATH_DIFFICULTIES['Hard']))
            params.add(('var', models.VARIATIONS['Starved']))
        elif logic_mode == "Glitched":
            params.add(('cell_freq', "256"))
            params.add(("path_diff", models.PATH_DIFFICULTIES['Hard']))

        url = f"{SEEDGEN_API_URL}/generator/json?{parse.urlencode(list(params))}"
        logger.debug(f"Outgoing request: {url}")
        resp = await self._session.request('GET', url)
        return await resp.json()
