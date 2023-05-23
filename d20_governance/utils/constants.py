import os
import yaml as py_yaml
import emoji
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

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if DISCORD_TOKEN is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")

STABILITY_TOKEN = os.getenv("STABILITY_API_KEY")
if STABILITY_TOKEN is None:
    raise Exception("Missing Stability API key.")

API_HOST = "https://api.stability.ai"


# Timeouts
START_TIMEOUT = 600  # The window for starting a game will time out after 10 minutes
GAME_TIMEOUT = (
    86400  # The game will auto-archive if there is no game play within 24 hours
)
VOTE_DURATION_SECONDS = 10 


STABILITY_API_HOST = "https://api.stability.ai"
ENGINE_ID = "stable-diffusion-v1-5"

# CONFIG PATHS

QUEST_CONFIG_PATH = "d20_governance/quest_config.yaml"
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
GOVERNANCE_STACK_SNAPSHOTS_PATH = "assets/user_created/governance_stack_snapshots"

# Fonts
FONT_PATH_BUBBLE = "assets/fonts/bubble_love_demo.otf"
FONT_PATH_LATO = "assets/fonts/Lato-Regular.ttf"

# Module Construction
FILE_COUNT = 0  # Global variable to store the count of created files
MAX_MODULE_LEVELS = 5
MODULE_PADDING = 10

# Init
OBSCURITY = False
ELOQUENCE = False
TEMP_CHANNEL = None
OBSCURITY_MODE = "scramble"

# Set Quest Config Variables
QUEST_DATA = read_config(QUEST_CONFIG_PATH)
QUEST_GAME = QUEST_DATA["game"]
QUEST_TITLE = QUEST_GAME["title"]
QUEST_INTRO = QUEST_GAME["intro"]
QUEST_COMMANDS = QUEST_GAME["meta_commands"]
QUEST_STAGES = QUEST_GAME["stages"]
QUEST_STAGE_MESSAGE = "message"
QUEST_STAGE_ACTION = "action"
QUEST_STAGE_TIMEOUT = "timeout_mins"
QUEST_APPLY_OUTCOME = "apply_outcome"

# Stores the number of messages sent by each user
user_message_count = {}
