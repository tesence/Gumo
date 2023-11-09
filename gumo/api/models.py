"""
Define the mapping between Randomizer parameters presented to the user and the parameters passed in the API request.
"""

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
