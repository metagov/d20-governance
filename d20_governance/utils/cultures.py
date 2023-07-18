import random
import discord
import asyncio
from d20_governance.utils.constants import *
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from langchain.chat_models import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from collections import defaultdict


# This is a custom List that tracks order or append and removal as well as groups of channels through sets
class ListSet(object):
    def __init__(self):
        self.set = set()
        self.list = []

    def add(self, item):
        if item not in self.set:
            self.set.add(item)
            self.list.append(item)

    def remove(self, item):
        if item in self.set:
            self.set.discard(item)
            self.list.remove(item)

    def __iter__(self):
        return iter(self.list)

    def __len__(self):
        return len(
            self.list
        )  # The lengthof the ListSet is the length of the internal list

    def __bool__(self):
        return len(self) > 0  # Theinstance is "Truthy" if there are elements in it


class CultureModule:
    def __init__(self, config):
        self.config = config  # This hold the configuration for the module

    # Methods to handle local state
    def is_local_state_active(self):
        return self.config["local_state"]

    def activate_local_state(self):
        self.config["local_state"] = True

    def deactivate_local_state(self):
        self.config["local_state"] = False

    # Methods to handle global state
    def is_global_state_active(self):
        return self.config["global_state"]

    async def activate_global_state(self, ctx):
        self.config["global_state"] = True
        await toggle_culture_module(ctx, self.config["module_string"], True)
        await display_culture_module_state(ctx, self.config["module_string"], True)

    async def deactivate_global_state(self, ctx, timeout=None):
        self.config["global_state"] = False
        await toggle_culture_module(ctx, self.config["module_string"], False)
        await display_culture_module_state(ctx, self.config["module_string"], False)

        if timeout:
            print("Timeout True")
            asyncio.create_task(self.timeout_task(timeout))

    async def toggle_global_state(self, ctx):
        if self.is_global_state_active():
            await self.deactivate_global_state(ctx)
        else:
            await self.activate_global_state(ctx)

    # Timeout method
    async def timeout_task(self, timeout):
        print("Starting Timeout Task")
        await asyncio.sleep(timeout)
        print("ending Timeout Task")
        if (
            not self.is_local_state_active()
        ):  # Check is module is still deactivated locally after waiting
            # if not
            self.activate_global_state()


ACTIVE_MODULES_BY_CHANNEL = defaultdict(ListSet)


async def toggle_culture_module(ctx, module_name, state):
    """
    If state is True, turnon the culture module
    if state is False, turn off the culture module
    """
    channel_name = str(ctx.channel)
    active_modules_by_channel = ACTIVE_MODULES_BY_CHANNEL[channel_name]

    if state:
        active_modules_by_channel.add(module_name)
    else:
        active_modules_by_channel.remove(module_name)


async def display_culture_module_state(ctx, module_name, state):
    """
    Send an embed displaying state of active culture moduled by channel
    """
    channel_name = str(ctx.channel)
    active_modules_by_channel = ACTIVE_MODULES_BY_CHANNEL[channel_name]

    module = CULTURE_MODULES[module_name]

    if state:
        name = "Activated"
        value = module.config["activated_message"]
    else:
        name = "Deactivated"
        value = module.config["deactivated_message"]

    if active_modules_by_channel.list:
        active_culture_module_values = ", ".join(active_modules_by_channel.list)
    else:
        active_culture_module_values = "none"

    embed = discord.Embed(
        title=f"Culture: {module_name.upper()}", color=discord.Color.dark_gold()
    )
    embed.set_thumbnail(url=module.config["url"])
    embed.add_field(
        name=name,
        value=value,
        inline=False,
    )
    if module.config["mode"] is not None and state:
        embed.add_field(
            name="Mode:",
            value=module.config["mode"],
            inline=False,
        )
    if module.config["llm_altered"] and state:
        embed.add_field(
            name="LLM Prompt:",
            value=module.config["llm_disclosure"],
            inline=False,
        )
    if module.config["help"] and state:
        embed.add_field(
            name="How to use:",
            value=module.config["how_to_use"],
            inline=False,
        )
    embed.add_field(
        name="ACTIVE CULTURE MODES:",
        value=active_culture_module_values,
        inline=False,
    )

    await ctx.send(embed=embed)


CULTURE_MODULES = {
    "obscurity": CultureModule(
        {
            "module_string": "obscurity",
            "global_state": False,
            "local_state": False,
            "mode": "scramble",
            "help": False,
            "llm_altered": False,
            "activated_message": "Messages will be distored based on mode of obscurity.",
            "deactivated_message": "Messages will no longer be distored by obscurity.",
            "url": "https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/obscurity.png",
            "icon": GOVERNANCE_SVG_ICONS["culture"],
            "input_value": 0,
        }
    ),
    "eloquence": CultureModule(
        {
            "module_string": "eloquence",
            "global_state": False,
            "local_state": False,
            "mode": None,
            "help": False,
            "llm_altered": True,
            "llm_disclosure": "You are from the Shakespearean era. Please rewrite the messages in a way that makes the speaker sound as eloquent, persuasive, and rhetorical as possible, while maintaining the original meaning and intent.",
            "activated_message": "Messages will now be process through an LLM.",
            "deactivated_message": "Messages will no longer be processed through an LLM.",
            "url": "https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/eloquence.png",
            "icon": GOVERNANCE_SVG_ICONS["culture"],
            "input_value": 0,
        }
    ),
    "ritual": CultureModule(
        {
            "module_string": "ritual",
            "global_state": False,
            "local_state": False,
            "mode": None,
            "help": False,
            "llm_altered": True,
            "llm_disclosure": "Write a message that reflects the content in the posted message and is cast in agreement with the previous message. Preserve and transfer any spelling errors or text transformations in these messages in the response.",
            "activated_message": "A ritual of agreement permeates throughout the group.",
            "deactivated_message": "Automatic agreement has ended. But will the effects linger in practice?",
            "url": "",  # TODO: make ritual img
            "icon": GOVERNANCE_SVG_ICONS["culture"],
            "input_value": 0,
        }
    ),
    "diversity": CultureModule(
        {
            "module_string": "diversity",
            "global_state": False,
            "local_state": False,
            "mode": None,
            "help": False,
            "llm_altered": False,
            "activated_message": "A measure of diversity influences the distribution of power.",
            "deactivated_message": "Measurements of diversity continue, but no longer govern this environment's interactions.",
            "url": "",  # TODO: make ritual img
            "icon": GOVERNANCE_SVG_ICONS["culture"],
            "input_value": 0,
        }
    ),
    "values": CultureModule(
        {
            "module_string": "values",
            "global_state": False,
            "mode": None,
            "help": True,
            "how_to_use": "Get a vibe check. See how aligned a post is with your community's values.\nReply to the message you want to check and type `check-values`.",
            "local_state": False,
            "llm_altered": True,
            "llm_disclosure": "You hold and maintain a set of mutually agreed upon values. The values you maintain are the values defined by the community. You review the contents of messages sent for validation and analyze the contents in terms of the values you hold. You describe in what ways the input text are aligned or unaligned with the values you hold.",
            "activated_message": "A means of validating the cultural alignment of this online communiuty is now available. Respond to a message with check-values.",
            "deactivated_message": "Automatic measurement of values is no longer present, through an essence of the culture remains, and you can respond to messages with `check-values` to check value alignment.",
            "url": "",  # TODO: make ritual img
            "icon": GOVERNANCE_SVG_ICONS["culture"],
            "input_value": 0,
        }
    ),
}


class Obscurity:
    def __init__(self, string):
        self.string = string

    def scramble(self):
        print(self.string)
        words = self.string.split()
        scrambled_words = [scramble_word(word) for word in words]
        return " ".join(scrambled_words)

    def replace_vowels(self):
        vowels = "aeiou"
        message_content = self.string.lower()
        return "".join([" " if c in vowels else c for c in message_content])

    def pig_latin_word(self):
        if self.string[0] in "aeiouAEIOU":
            return self.string + "yay"
        else:
            first_consonant_cluster = ""
            rest_of_word = self.string
            for letter in self.string:
                if letter not in "aeiouAEIOU":
                    first_consonant_cluster += letter
                    rest_of_word = rest_of_word[1:]
                else:
                    break
            return rest_of_word + first_consonant_cluster + "ay"

    def pig_latin(self):
        words = self.string.split()
        pig_latin_words = [pig_latin_word(word) for word in words]
        return " ".join(pig_latin_words)

    def camel_case(self):
        words = self.string.split()
        camel_case_words = [word.capitalize() for word in words]
        return "".join(camel_case_words)


def scramble_word(word):
    if len(word) <= 3:
        return word
    else:
        middle = list(word[1:-1])
        random.shuffle(middle)
        return word[0] + "".join(middle) + word[-1]


def pig_latin_word(word):
    if word[0] in "aeiouAEIOU":
        return word + "yay"
    else:
        first_consonant_cluster = ""
        rest_of_word = word
        for letter in word:
            if letter not in "aeiouAEIOU":
                first_consonant_cluster += letter
                rest_of_word = rest_of_word[1:]
            else:
                break
        return rest_of_word + first_consonant_cluster + "ay"


async def filter_eloquence(text):
    """
    A LLM filter for messages during the /eloquence command/function
    """
    llm = OpenAI(temperature=0.5, model_name="gpt-3.5-turbo")
    prompt = PromptTemplate.from_template(
        template="You are from the Shakespearean era. Please rewrite the following input in a way that makes the speaker sound as eloquent, persuasive, and rhetorical as possible, while maintaining the original meaning and intent. Don't complete any sentences, jFust rewrite them. Input: {input_text}"
    )
    prompt.format(input_text=text)
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain.run(text)


async def filter_by_values(text):
    """
    Filter and analyze message content based on values
    """
    llm = OpenAI(temperature=0.5, model_name="gpt-3.5-turbo")
    template = f"You hold and maintain a set of mutually agreed-upon values. Let's analyze the message '{text}' in terms of the values you hold:\n\n"
    for (
        value,
        description,
    ) in MOCK_VALUES_DICT.items():
        template += f"- {value}: {description}\n"
    template += f"\nNow, analyze the message:\n{text}. Keep your analysis concise."
    prompt = PromptTemplate.from_template(template=template)
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain.run({"text": text, "mock_values_dict": MOCK_VALUES_DICT})


async def send_msg_to_random_player(game_channel):
    print("Sending random DM...")
    players = [member for member in game_channel.members if not member.bot]
    random_player = random.choice(players)
    dm_channel = await random_player.create_dm()
    await dm_channel.send(
        "🌟 Greetings, esteemed adventurer! A mischievous gnome has entrusted me with a cryptic message just for you: 'In the land of swirling colors, where unicorns prance and dragons snooze, a hidden treasure awaits those who dare to yawn beneath the crescent moon.' Keep this message close to your heart and let it guide you on your journey through the wondrous realms of the unknown. Farewell, and may your path be ever sprinkled with stardust! ✨"
    )


async def initialize_ritual_agreement(previous_message, new_message):
    llm = OpenAI(temperature=0.9)
    prompt = PromptTemplate(
        input_variables=["previous_message", "new_message"],
        template="Write a message that reflects the content in {new_message} and is cast in agreement with {previous_message}. Preserve and transfer any spelling errors or text transformations in these messages in the response.",
    )  # FIXME: This template does not preserve obscurity text processing. Maybe obscurity should be reaplied after ritual if active in the active_culture_mode list
    chain = LLMChain(llm=llm, prompt=prompt)
    response = chain.run(previous_message=previous_message, new_message=new_message)
    return response
