import os
import yaml as py_yaml
from dotenv import load_dotenv
from ruamel.yaml import YAML
from discord.ext import commands


def read_config(file_path):
    """
    Function for reading a yaml file
    """
    with open(file_path, "r") as f:
        config = py_yaml.safe_load(f)
    return config


ru_yaml = YAML()
ru_yaml.indent(mapping=2, sequence=4, offset=2)

# API KEY AND INFO
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if DISCORD_TOKEN is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")

STABILITY_TOKEN = os.getenv("STABILITY_API_KEY")
if STABILITY_TOKEN is None:
    raise Exception("Missing Stability API key.")

API_HOST = "https://api.stability.ai"
STABILITY_API_HOST = "https://api.stability.ai"
ENGINE_ID = "stable-diffusion-v1-5"

# TIMEOUTS
timeouts = {
    "cooldown": 5,  # global cooldown value
    "start": 600,  # The window for starting a game will time out after 10 minutes
    "no_game_play": 86400,  # The game will auto-archive if there is no game play within 24 hours
    "vote": 60,  # amount of time to vote
}
cooldowns = {
    "decisions": commands.CooldownMapping.from_cooldown(
        1, timeouts["cooldown"], commands.BucketType.user
    ),
    "cultures": commands.CooldownMapping.from_cooldown(
        1, timeouts["cooldown"], commands.BucketType.user
    ),
}

# TEMP DIRECTORY PATHS
AUDIO_MESSAGES_PATH = "assets/audio/bot_generated"
GOVERNANCE_STACK_SNAPSHOTS_PATH = "assets/user_created/governance_stack_snapshots"
LOGGING_PATH = "logs"
LOG_FILE_NAME = f"{LOGGING_PATH}/bot.log"

# BOT IMAGES
BOT_ICON = "assets/imgs/game_icons/d20-gov-icon.png"

# SIMULATION CONFIGS
SIMULATIONS = {
    "build_a_community": {
        "name": "build a community",
        "emoji": "🎪",
        "file": "d20_governance/d20_configs/minigame_configs/build_community_game.yaml",
        "description": "Build a community prompt",
    },
    "whimsy": {
        "name": "whimsy",
        "emoji": "🤪",
        "file": "d20_governance/d20_configs/quest_configs/whimsy.yaml",
        "description": "A whimsical governance game",
    },
    "colony": {
        "name": "colony",
        "emoji": "🛸",
        "file": "d20_governance/d20_configs/quest_configs/colony.yaml",
        "description": "Governance under space colony",
    },
    "mascot": {
        "name": "mascot",
        "emoji": "🐻‍❄️",
        "file": "d20_governance/d20_configs/quest_configs/mascot.yaml",
        "description": "Propose a new community mascot",
    },
    "llm_mode": {
        "name": "llm_mode",
        "emoji": "🤔",
        "file": "llm",
        "description": "A random game of d20 governance",
    },
    "josh_game": {
        "name": "josh_game",
        "emoji": "👨‍🦰",
        "file": "d20_governance/d20_configs/minigame_configs/josh_game.yaml",
        "description": "The josh gam",
    },
}

# DELIBERATION QUESTIONS
deliberation_questions = [
    "As you discuss and deliberate your proposals, consider: what emotional associations might your proposals evoke",
    "As you discuss and deliberate your proposals, consider: does your proposal tends towards the descriptive and abstract, or specific and concrete?",
    "As you discuss and deliberate your proposals, consider: does your proposal resonate in any way with the community that the group is embeeded in?",
]

# INIT
values_check_task = None

# QUEST KEYS
QUEST_MESSAGE_KEY = "message"
QUEST_NAME_KEY = "stage"
QUEST_ACTIONS_KEY = "actions"
QUEST_PROGRESS_CONDITIONS_KEY = "progress_conditions"
QUEST_IMAGE_PATH_KEY = "image_path"

# GOVERNANCE STACK CONFIGS
GOVERNANCE_STACK_CONFIG_PATH = "d20_governance/governance_stack_config.yaml"
GOVERNANCE_STACK_CHAOS_PATH = (
    "d20_governance/governance_stacks/governance_stack_templates/chaos_stack.yaml"
)
GOVERNANCE_STACK_BDFL_PATH = (
    "d20_governance/governance_stacks/governance_stack_templates/bdfl_stack.yaml"
)
GOVERNANCE_TYPES = {
    "culture": "d20_governance/governance_stacks/types/culture.yaml",
    "decision": "d20_governance/governance_stacks/types/decision.yaml",
    "process": "d20_governance/governance_stacks/types/process.yaml",
    "structure": "d20_governance/governance_stacks/types/structure.yaml",
}
GOVERNANCE_SVG_ICONS = {
    "culture": "assets/imgs/CommunityRule/icons/palette.svg",
    "decision": "assets/imgs/CommunityRule/icons/thumb-up.svg",
    "process": "assets/imgs/CommunityRule/icons/rotate.svg",
    "structure": "assets/imgs/CommunityRule/icons/building.svg",
}

# FONTS
FONT_PATH_BUBBLE = "assets/fonts/bubble_love_demo.otf"
FONT_PATH_LATO = "assets/fonts/Lato-Regular.ttf"

# GRAPHIC SETS
CIRCLE_EMOJIS = [
    "🔴",
    "🟠",
    "🟡",
    "🟢",
    "🔵",
    "🟣",
    "🟤",
    "⚫",
    "⚪",
]

# MODULE STACK IMG CONSTRUCTION
FILE_COUNT = 0  # Global variable to store the count of created files
MAX_MODULE_LEVELS = 5
MODULE_PADDING = 10

# DECISIONS LOG
DECISION_DICT = {}

# SPECTRUM VALUES
INPUT_SPECTRUM = {
    "scale": 10,
    "threshold": 5,
}

# INTERNAL ACCESS CONTROL SETTINGS
ACCESS_CONTROL_SETTINGS = {
    "allowed_roles": ["@everyone"],
    "excluded_roles": [],
    "command_name": [],
}

# MISC INITS
IS_QUIET = False
MAX_VOTE_TRIGGERS = 3
VOTE_RETRY = False
QUEST_IN_PROGRESS = False

# MISC DICTS
USER_MESSAGE_COUNT = {}  # Stores the number of messages sent by each user

# MISC LISTS
WEBHOOK_LIST = []  # stores webhooks
ARCHIVED_CHANNELS = []

# JOSH GAME # todo: move this out to game-specific file
JOSH_NICKNAMES = [
    "Jigsaw Joshy",
    "Josh-a-mania",
    "Jovial Joshington",
    "Jalapeño Josh",
    "Jitterbug Joshie",
    "Jamboree Josh",
    "Jumping Jack Josh",
    "Just Joking Josh",
    "Jubilant Jostler",
    "Jazz Hands Josh",
    "Jetset Josh",
    "Java Junkie Josh",
    "Juicy Josh",
    "Juggler Josh",
    "Joyful Jester Josh",
    "Jackpot Josh",
    "Jeopardy Josh",
    "Jammin' Josh",
    "Jurassic Josh",
    "Jingle Bell Josh",
]
