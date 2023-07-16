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
    "whimsy": "d20_governance/d20_configs/quest_configs/whimsy.yaml",
    "colony": "d20_governance/d20_configs/quest_configs/colony.yaml",
    "mascot": "d20_governance/d20_configs/quest_configs/mascot.yaml",
    "josh_game": "d20_governance/d20_configs/minigame_configs/josh_game.yaml",
    "build_a_community": "d20_governance/d20_configs/minigame_configs/build_community_game.yaml",
    "llm_mode": "llm",
}

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

# CULTURE MODULES
ACTIVE_GLOBAL_CULTURE_MODULES = {}

CULTURE_MODULES = {
    "obscurity": {
        "module_string": "obscurity",
        "state": False,
        "mode": "scramble",
        "activated": False,
        "llm_altered": False,
        "activated_message": "Messages will be distored based on mode of obscurity.",
        "deactivated_message": "Messages will no longer be distored by obscurity.",
        "url": "https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/obscurity.png",
        "icon": GOVERNANCE_SVG_ICONS["culture"],
        "input_value": 0,
    },
    "eloquence": {
        "module_string": "eloquence",
        "state": False,
        "mode": None,
        "activated": False,
        "llm_altered": True,
        "llm_disclosure": "You are from the Shakespearean era. Please rewrite the messages in a way that makes the speaker sound as eloquent, persuasive, and rhetorical as possible, while maintaining the original meaning and intent.",
        "activated_message": "Messages will now be process through an LLM.",
        "deactivated_message": "Messages will no longer be processed through an LLM.",
        "url": "https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/eloquence.png",
        "icon": GOVERNANCE_SVG_ICONS["culture"],
        "input_value": 0,
    },
    "ritual": {
        "module_string": "ritual",
        "state": False,
        "mode": None,
        "activated": False,
        "llm_altered": True,
        "llm_disclosure": "Write a message that reflects the content in the posted message and is cast in agreement with the previous message. Preserve and transfer any spelling errors or text transformations in these messages in the response.",
        "activated_message": "A ritual of agreement permeates throughout the group.",
        "deactivated_message": "Automatic agreement has ended. But will the effects linger in practice?",
        "url": "",  # TODO: make ritual img
        "icon": GOVERNANCE_SVG_ICONS["culture"],
        "input_value": 0,
    },
    "diversity": {
        "module_string": "diversity",
        "state": False,
        "mode": None,
        "activated": False,
        "llm_altered": False,
        "activated_message": "A measure of diversity influences the distribution of power.",
        "deactivated_message": "Measurements of diversity continue, but no longer govern this environment's interactions.",
        "url": "",  # TODO: make ritual img
        "icon": GOVERNANCE_SVG_ICONS["culture"],
        "input_value": 0,
    },
    "values": {
        "module_string": "values",
        "state": False,
        "mode": None,
        "activated": False,
        "llm_altered": True,
        "llm_disclosure": "You hold and maintain a set of mutually agreed upon values. The values you maintain are the values defined by the community. You review the contents of messages sent for validation and analyze the contents in terms of the values you hold. You describe in what ways the input text are aligned or unaligned with the values you hold.",
        "activated_message": "A means of validating the cultural alignment of this online communiuty is now available. Respond to a message with check-values.",
        "deactivated_message": "Automatic measurement of values is no longer present, through an essence of the culture remains, and you can respond to messages with `check-values` to check value alignment.",
        "url": "",  # TODO: make ritual img
        "icon": GOVERNANCE_SVG_ICONS["culture"],
        "input_value": 0,
    },
}

# DECISION MODULES
ACTIVE_GLOBAL_DECISION_MODULES = {}

DECISION_MODULES = {
    "majority": {
        "module_string": "majority",
        "description": "Majority requires a simiple majority from the number of people who voteon the options.",
        "state": False,
        "activated": False,
        "activated_message": "Messages will be distored based on mode of obscurity.",
        "deactivated_message": "Messages will no longer be distored by obscurity.",
        "url": "",  # TODO: make decision img
        "icon": GOVERNANCE_SVG_ICONS["decision"],
        "input_value": 0,
    },
    "consensus": {
        "module_string": "consensus",
        "description": "Consensus requires everyone in the simulation to vote on the same option.",
        "state": False,
        "activated": False,
        "activated_message": "Messages will now be process through an LLM.",
        "deactivated_message": "Messages will no longer be processed through an LLM.",
        "url": "",  # TODO: make decision img
        "icon": GOVERNANCE_SVG_ICONS["decision"],
        "input_value": 0,
    },
}

# DECISIONS LOG

DECISION_DICT = {}

# VALUES DEFINITION

MOCK_VALUES_LIST = [
    "respect",
    "divisiveness",
    "support",
    "exploitation",
    "trust",
    "domination",
]

MOCK_VALUES_DICT = {
    "Respect": "Our members should treat each other with respect, recognizing and appreciating diverse perspectives and opinions.",
    "Inclusivity": "Our community strives to be inclusive, creating an environment where everyone feels welcome and valued regardless of their background, identity, or beliefs.",
    "Support": "Our members support and help one another, whether it's providing guidance, advice, or emotional support.",
    "Collaboration": "Our community encourage collaboration, fostering an environment where members can work together and share knowledge or skills.",
    "Trust": "Our community believes building trust is important, as it allows members to feel safe and comfortable sharing their thoughts and experiences.",
}

# SPECTRUM VALUES
INPUT_SPECTRUM = {
    "scale": 10,
    "threshold": 7,
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

# MISC DICTS
USER_MESSAGE_COUNT = {}  # Stores the number of messages sent by each user

# MISC LISTS
WEBHOOK_LIST = []  # stores webhooks

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
