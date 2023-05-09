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

# Timeouts
START_TIMEOUT = 600  # The window for starting a game will time out after 10 minutes
GAME_TIMEOUT = (
    86400  # The game will auto-archive if there is no game play within 24 hours
)

# Const
STABILITY_API_HOST = "https://api.stability.ai"
ENGINE_ID = "stable-diffusion-v1-5"
QUEST_CONFIG_PATH = "d20_governance/config.yaml"
GOVERNANCE_STACK_CONFIG_PATH = (
    "d20_governance/governance-stack-configs/governance-stack-config.yaml"
)
FONT_PATH = "assets/fonts/bubble_love_demo.otf"

# Init
OBSCURITY = False
ELOQUENCE = False
TEMP_CHANNEL = None
OBSCURITY_MODE = "scramble"

# Set Governance Stack Yaml Variables
GOVERNANCE_STACK_CONFIG = read_config(GOVERNANCE_STACK_CONFIG_PATH)
GOVERNANCE_STACK_MODULES = GOVERNANCE_STACK_CONFIG["rule"]["modules"][0]
GOVERNANCE_STACK_MODULE_NAME = GOVERNANCE_STACK_MODULES["name"]
GOVERNANCE_STACK_SUB_MODULES = GOVERNANCE_STACK_MODULES["modules"]

# Set Quest Config Variables
QUEST_CONFIG = read_config(QUEST_CONFIG_PATH)
QUEST_GAME = QUEST_CONFIG["game"]
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
