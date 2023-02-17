from urllib import parse

from gumo.api import base
from gumo.modules.seed import models

SEEDGEN_API_URL = "https://orirando.com"

PATHS_INHERITENCE = {}
PATHS_INHERITENCE['casual'] = [lp for lp in models.LOGIC_PATHS.values() if lp.startswith('casual')]
PATHS_INHERITENCE['standard'] = PATHS_INHERITENCE['casual'] + \
                                [lp for lp in models.LOGIC_PATHS.values() if lp.startswith('standard')]
PATHS_INHERITENCE['expert'] = PATHS_INHERITENCE['standard'] + \
                              [lp for lp in models.LOGIC_PATHS.values() if lp.startswith('expert')] + \
                              [models.LOGIC_PATHS['dbash']]
PATHS_INHERITENCE['master'] = PATHS_INHERITENCE['expert'] + \
                              [lp for lp in models.LOGIC_PATHS.values() if lp.startswith('master')]
PATHS_INHERITENCE['glitched'] = PATHS_INHERITENCE['expert'] + \
                                [models.LOGIC_PATHS['glitched'], models.LOGIC_PATHS['timedlevel']]


class BFRandomizerApiClient(base.APIClient):

    async def get_data(self, seed_name, logic_mode=None, key_mode=None, item_pool=None, goal_modes=(), variations=(),
                       logic_paths=()):

        params = {('seed', seed_name)}

        # Retrieve the logic paths for the given logic and
        logic_mode = logic_mode or "standard"
        default_logic_paths = PATHS_INHERITENCE[logic_mode]
        # Add the ones passed as argument if they are not already present
        logic_paths = default_logic_paths + \
            [models.LOGIC_PATHS[lp] for lp in logic_paths if lp not in default_logic_paths]
        for logic_path in logic_paths:
            params.add(('path', logic_path))

        # Set the key mode
        keymode = key_mode or 'clues'
        params.add(('key_mode', models.KEY_MODES[keymode]))

        # Set item pool
        item_pool = item_pool or 'standard'
        params.add(('pool_preset', models.ITEM_POOLS[item_pool]))

        # Goal modes (treated as variations)
        goal_modes = goal_modes or ['forcetrees']
        for goal_mode in goal_modes:
            params.add(('var', models.GOAL_MODES[goal_mode]))

        # Variations
        for variation in variations:
            params.add(('var', models.VARIATIONS[variation]))

        # Handle all the preset specificities
        if logic_mode == "easy":
            params.add(('cell_freq', "20"))
        elif logic_mode == "standard":
            params.add(('cell_freq', "40"))
        elif logic_mode == "expert":
            pass
        elif logic_mode == "master":
            params.add(("path_diff", models.PATH_DIFFICULTIES['hard']))
            params.add(('var', models.VARIATIONS['starved']))
        elif logic_mode == "glitched":
            params.add(("path_diff", models.PATH_DIFFICULTIES['hard']))

        url = f"{SEEDGEN_API_URL}/generator/json?{parse.urlencode(list(params))}"
        return await self.get(url, return_json=True)
