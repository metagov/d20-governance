import os
import yaml as py_yaml
from dotenv import load_dotenv
from ruamel.yaml import YAML

def read_config(file_path):
    """
    Function for reading a yaml file
    """
    with open(file_path, "r") as f:
        config = py_yaml.safe_load(f)
    return config

ru_yaml = YAML()
ru_yaml.indent(mapping=2, sequence=4, offset=2)

# API Keys and Info

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


# Timeouts
START_TIMEOUT = 600  # The window for starting a game will time out after 10 minutes
GAME_TIMEOUT = (
    86400  # The game will auto-archive if there is no game play within 24 hours
)
VOTE_DURATION_SECONDS = 60


# TEMP DIRECTORY PATHS
AUDIO_MESSAGES_PATH = "assets/audio/bot_generated"
GOVERNANCE_STACK_SNAPSHOTS_PATH = "assets/user_created/governance_stack_snapshots"
LOGGING_PATH = "logs"
LOG_FILE_NAME = f"{LOGGING_PATH}/bot.log"

# BOT IMAGES
BOT_ICON = "assets/imgs/game_icons/d20-gov-icon.png"

# QUEST CONFIGS
QUEST_WHIMSY = "d20_governance/d20_configs/quest_configs/whimsy.yaml"
QUEST_COLONY = "d20_governance/d20_configs/quest_configs/colony.yaml"
QUEST_MASCOT = "d20_governance/d20_configs/quest_configs/mascot.yaml"
MINIGAME_JOSH = "d20_governance/d20_configs/minigame_configs/josh_game.yaml"
QUEST_MODE_LLM = "llm"
QUEST_STAGE_MESSAGE = "message"
QUEST_STAGE_NAME = "stage"
QUEST_STAGE_ACTION = "actions"
QUEST_STAGE_TIMEOUT = "timeout_secs"


# GOVERNANCE CONFIGS
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

# Module Construction
FILE_COUNT = 0  # Global variable to store the count of created files
MAX_MODULE_LEVELS = 5
MODULE_PADDING = 10

# CULTURE MODES
OBSCURITY = False
ELOQUENCE = False
RITUAL = False
OBSCURITY_MODE = "scramble"
IS_QUIET = False
COMMAND_VISIBILITY = {}
DECISION_MODULE = None
MAX_VOTE_TRIGGERS = 3

# INTERNAL ACCESS CONTROL SETTINGS 
ACCESS_CONTROL_SETTINGS = {
    "allowed_roles": ["@everyone"],
    "excluded_roles": [],
    "command_name": [],
}

# MISC
COMMAND_VISIBILITY = {}

# CULTURE COMMANDS
active_culture_modes = []

# Stores the number of messages sent by each user
user_message_count = {}

# JOSH GAME # todo: move this out to game-specific file
players_to_nicknames = {}
nicknames = [
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
    "Jigsaw Juggler Josh",
    "Joyful Jester Josh",
    "Jackpot Josh",
    "Jeopardy Josh",
    "Jammin' Josh",
    "Jurassic Josh",
    "Jingle Bell Josh",
]

nicknames_to_speeches = {}
