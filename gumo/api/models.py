"""
Define the mapping between Randomizer parameters presented to the user and the parameters passed in the API request.
"""

from discord import app_commands

LOGIC_MODES = {
    'Casual': "Casual",
    'Standard': "Standard",
    'Expert': "Expert",
    'Master': "Master",
    'Glitched': "Glitched"
}

KEY_MODES = {
    'None': "Default",
    'Shards': "Shards",
    'Limitkeys': "Limitkeys",
    'Clues': "Clues",
    'Free': "Free"
}

GOAL_MODES = {
    'None': "",
    'Force Trees': "ForceTrees",
    'World Tour': "WorldTour",
    'Force Maps': "ForceMaps",
    'Warmth Frags': "WarmthFrags",
    'Bingo': "Bingo"
}

SPAWNS = {
    'Random': "Random",
    'Glades': "Glades",
    'Grove': "Grove",
    'Swamp': "Swamp",
    'Grotto': "Grotto",
    'Forlorn': "Forlorn",
    'Valley': "Valley",
    'Horu': "Horu",
    'Ginso': "Ginso",
    'Sorrow': "Sorrow",
    'Blackroot': "Blackroot"
}

VARIATIONS = {
    'Starved': "Starved",
    'OHKO': "OHKO",
    '0XP': "0XP",
    'Closed Dungeons': "ClosedDungeons",
    'Extra Copies': "DoubleSkills",
    'Strict Mapstones': "StrictMapstones",
    'TP Starved': "TPStarved",
    'Skip Final Escape': "GoalModeFinish",
    'Wall Starved': "WallStarved",
    'Grenade Starved': "GrenadeStarved",
    'In-Logic Warps': "InLogicWarps"
}

LOGIC_PATHS = {
    'Casual-core': "casual-core",
    'Casual-dboost': "casual-dboost",
    'Standard-core': "standard-core",
    'Standard-dboost': "standard-dboost",
    'Standard-lure': "standard-lure",
    'Standard-abilities': "standard-abilities",
    'Expert-core': "expert-core",
    'Expert-dboost': "expert-dboost",
    'Expert-lure': "expert-lure",
    'Expert-abilities': "expert-abilities",
    'Master-core': "master-core",
    'Master-dboost': "master-dboost",
    'Master-lure': "master-lure",
    'Dbash': "dbash",
    'Gjump': "gjump",
    'Glitched': "glitched",
    'Timed-Level': "timed-level",
    'Insane': "insane"
}

ITEM_POOLS = {
    'Standard': "Standard",
    'Competitive': "Competitive",
    'Bonus Lite': "Bonus Lite",
    'Extra Bonus': "Extra Bonus",
    'Hard': "Hard"
}

PATH_DIFFICULTIES = {
    'Easy': "Easy",
    'Normal': "Normal",
    'Hard': "Hard"
}

LOGIC_MODE_CHOICES = [app_commands.Choice(name=name, value=name) for name, value in LOGIC_MODES.items()]
KEY_MODE_CHOICES = [app_commands.Choice(name=name, value=name) for name, value in KEY_MODES.items()]
GOAL_MODE_CHOICES = [app_commands.Choice(name=name, value=name) for name, value in GOAL_MODES.items()]
SPAWN_CHOICES = [app_commands.Choice(name=name, value=name) for name, value in SPAWNS.items()]
VARIATION_CHOICES = [app_commands.Choice(name=name, value=name) for name, value in VARIATIONS.items()]
LOGIC_PATH_CHOICES = [app_commands.Choice(name=name, value=name) for name, value in LOGIC_PATHS.items()]
ITEM_POOL_CHOICES = [app_commands.Choice(name=name, value=name) for name, value in ITEM_POOLS.items()]

def add_seed_options(func):
    """Set all the common options for seed commands

    Args:
        func (function): Command definition
    """
    func = app_commands.describe(logic_mode="Randomizer logic mode")(func)
    func = app_commands.choices(logic_mode=LOGIC_MODE_CHOICES)(func)
    func = app_commands.describe(key_mode="Randomizer key mode")(func)
    func = app_commands.choices(key_mode=KEY_MODE_CHOICES)(func)
    func = app_commands.describe(goal_mode="Randomizer goal mode")(func)
    func = app_commands.choices(goal_mode=GOAL_MODE_CHOICES)(func)
    func = app_commands.describe(spawn="The location where the player starts in the seed")(func)
    func = app_commands.choices(spawn=SPAWN_CHOICES)(func)
    func = app_commands.describe(variation1="Extra randomizer variation")(func)
    func = app_commands.choices(variation1=VARIATION_CHOICES)(func)
    func = app_commands.describe(variation2="Extra randomizer variation")(func)
    func = app_commands.choices(variation2=VARIATION_CHOICES)(func)
    func = app_commands.describe(variation3="Extra randomizer variation")(func)
    func = app_commands.choices(variation3=VARIATION_CHOICES)(func)
    func = app_commands.describe(item_pool="Randomizer item pool")(func)
    func = app_commands.choices(item_pool=ITEM_POOL_CHOICES)(func)
    func = app_commands.describe(relic_count="(World Tour only) The number of relics to place in the seed")(func)
    return func
