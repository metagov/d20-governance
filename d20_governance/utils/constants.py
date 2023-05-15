import os
import yaml
import emoji
from dotenv import load_dotenv


def read_config(file_path):
    """
    Function for reading a yaml file
    """
    with open(file_path, "r") as f:
        config = yaml.safe_load(f)
    return config


load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if DISCORD_TOKEN is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")

STABILITY_TOKEN = os.getenv("STABILITY_API_KEY")
if STABILITY_TOKEN is None:
    raise Exception("Missing Stability API key.")

API_HOST = os.getenv("API_HOST")
if API_HOST is None:
    raise Exception("Missing API Host.")

# Timeouts
START_TIMEOUT = 600  # The window for starting a game will time out after 10 minutes
GAME_TIMEOUT = (
    86400  # The game will auto-archive if there is no game play within 24 hours
)

# Const
# Stabiliy
STABILITY_API_HOST = "https://api.stability.ai"
ENGINE_ID = "stable-diffusion-v1-5"

# Config Paths
QUEST_CONFIG_PATH = "d20_governance/quest_config.yaml"
GOVERNANCE_STACK_CONFIG_PATH = "d20_governance/governance_stack_config.yaml"
GOVERNANCE_STACK_CHAOS_PATH = (
    "d20_governance/governance_stacks/governance_stack_templates/chaos_stack.yaml"
)
GOVERNANCE_STACK_BDFL_PATH = (
    "d20_governance/governance_stacks/governance_stack_templates/bdfl_stack.yaml"
)
GOVERNANCE_STACK_CULTURES_PATH = (
    "d20_governance/governance_stacks/governance_stack_types/governance_cultures.yaml"
)
GOVERNANCE_STACK_DECISIONS_PATH = (
    "d20_governance/governance_stacks/governance_stack_types/governance_decisions.yaml"
)
GOVERNANCE_STACK_PROCESSES_PATH = (
    "d20_governance/governance_stacks/governance_stack_types/governance_processes.yaml"
)
GOVERNANCE_STACK_STRUCTURES_PATH = (
    "d20_governance/governance_stacks/governance_stack_types/governance_structures.yaml"
)
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

# Set Governance Stack Yaml Variables
# GOVERNANCE_DATA = read_config(GOVERNANCE_STACK_CONFIG_PATH)
# GOVERNANCE_MODULES = GOVERNANCE_DATA["modules"]


def load_governance_stack_config():
    if GOVERNANCE_STACK_DECISIONS_PATH is None:
        raise Exception("Missing Stability API key.")
    else:
        GOVERNANCE_DATA = read_config(GOVERNANCE_STACK_CONFIG_PATH)
        GOVERNANCE_MODULES = GOVERNANCE_DATA["modules"]


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

# Decision Modules
DECISION_MODULES = [
    "👎 Approval Voting",
    "🪗 Consensus",
    "🥇 Ranked Choice",
    "☑️ Majority Voting",
]

# Dynamically extract emojis from the decision_modules list
# Prepare list
decision_emojis = []
for module in DECISION_MODULES:
    # Extract 'emoji' string produced by the emoji_list attribute for each culture module
    emojis = [e["emoji"] for e in emoji.emoji_list(module)]
    if len(emojis) > 0:
        # Append extracted emojis to the culture_emoji list
        decision_emojis.append(emojis[0])

# Prepare list of culture modules
list_decision_modules = "\n".join(DECISION_MODULES)

# Culture Modules
CULTURE_MODULES = [
    "💐 Eloquence",
    "🤫 Secrecy",
    "🪨 Rituals",
    "🪢 Friendship",
    "🤝 Solidarity",
    "🥷 Obscurity",
]

# Dynamically extract emojis from the culture_modules list
# Prepare list
culture_emojis = []
for module in CULTURE_MODULES:
    # Extract 'emoji' string produced by the emoji_list attribute for each culture module
    emojis = [e["emoji"] for e in emoji.emoji_list(module)]
    if len(emojis) > 0:
        # Append extracted emojis to the culture_emoji list
        culture_emojis.append(emojis[0])

# Prepare list of culture modules
list_culture_modules = "\n".join(CULTURE_MODULES)
