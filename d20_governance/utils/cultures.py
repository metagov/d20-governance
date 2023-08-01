from abc import ABC, abstractmethod
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
class OrderedSet:
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


class CultureModule(ABC):
    def __init__(self, config):
        self.config = config  # This hold the configuration for the module

    async def filter_message(self, ctx, message: discord.Message, message_string: str) -> str:
        return message_string

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
        await toggle_culture_module(ctx, self.config["name"], True)
        await display_culture_module_state(ctx, self.config["name"], True)

    async def deactivate_global_state(self, ctx, timeout=None):
        self.config["global_state"] = False
        await toggle_culture_module(ctx, self.config["name"], False)
        await display_culture_module_state(ctx, self.config["name"], False)

        if timeout:
            print("Timeout True")
            asyncio.create_task(self.timeout(timeout))

    async def toggle_global_state(self, ctx):
        if self.is_global_state_active():
            await self.deactivate_global_state(ctx)
        else:
            await self.activate_global_state(ctx)

    # Timeout method
    async def timeout(self, timeout):
        print("Starting Timeout Task")
        await asyncio.sleep(timeout)
        print("ending Timeout Task")
        if (
            not self.is_local_state_active()
        ):  # Check is module is still deactivated locally after waiting
            # if not
            self.activate_global_state()

class Obscurity(CultureModule):
    # Message string may be pre-filtered by other modules
    async def filter_message(self, ctx, message: discord.Message, message_string: str) -> str:
        # Get the method from the module based on the value of "mode"
        method = getattr(self, self.config["mode"])

        # Call the method
        filtered_message = method(message_string)
        return filtered_message
        
    def scramble(self, message_string):
        words = message_string.split()
        scrambled_words = []
        for word in words:
            if len(word) <= 3:
                scrambled_words.append(word)
            else:
                middle = list(word[1:-1])
                random.shuffle(middle)
                scrambled_words.append(word[0] + "".join(middle) + word[-1])
        return " ".join(scrambled_words)

    def replace_vowels(self, message_string):
        vowels = "aeiou"
        message_content = message_string.lower()
        return "".join([" " if c in vowels else c for c in message_content])

    def pig_latin(self, message_string):
        words = message_string.split()
        pig_latin_words = []
        for word in words:
            if word[0] in "aeiouAEIOU":
                pig_latin_words.append(word + "yay")
            else:
                first_consonant_cluster = ""
                rest_of_word = word
                for letter in word:
                    if letter not in "aeiouAEIOU":
                        first_consonant_cluster += letter
                        rest_of_word = rest_of_word[1:]
                    else:
                        break
                pig_latin_words.append(rest_of_word + first_consonant_cluster + "ay")
        return " ".join(pig_latin_words)

    def camel_case(self, message_string):
        words = message_string.split()
        camel_case_words = [word.capitalize() for word in words]
        return "".join(camel_case_words)

class Diversity(CultureModule):
    async def display_info(self, ctx):
            # Display the message count for each user
        message = "Message count by user:\n"

        # Sort the user_message_count dictionary by message count in descending order
        sorted_user_message_count = sorted(
            USER_MESSAGE_COUNT.items(), key=lambda x: x[1], reverse=True
        )

        for user_id, count in sorted_user_message_count:
            user = await ctx.guild.fetch_member(user_id)
            message += f"{user.name}: {count}\n"
        await ctx.send(f"```{message}```")


class Ritual(CultureModule):
    async def filter_message(self, ctx, message: discord.Message, message_string: str) -> str:
        async for msg in message.channel.history(limit=100):
            if msg.id == message.id:
                continue
            if msg.author.bot and not msg.content.startswith("※"): # This condition lets webhook messages to be checked
                continue
            if msg.content.startswith("/") or msg.content.startswith("-"):
                continue
            previous_message = msg.content
            break
        if previous_message is None:
            return message_string
        filtered_message = await self.initialize_ritual_agreement(
            previous_message, message_string
        )
        return filtered_message
    
    async def initialize_ritual_agreement(self, previous_message, new_message):
        llm = OpenAI(temperature=0.9)
        prompt = PromptTemplate(
            input_variables=["previous_message", "new_message"],
            template="Write a message that reflects the content in the message '{new_message}' but is cast in agreement with the message '{previous_message}'. Preserve and transfer the meaning and any spelling errors or text transformations in the message in the response.",
        )  # FIXME: This template does not preserve obscurity text processing. Maybe obscurity should be reaplied after ritual if active in the active_culture_mode list
        chain = LLMChain(llm=llm, prompt=prompt)
        response = chain.run(previous_message=previous_message, new_message=new_message)
        return response

class Values(CultureModule):
    async def check_values(self, ctx, message: discord.Message):
        if message.reference:
            reference_message = await message.channel.fetch_message(
                message.reference.message_id
            )
            if (
                reference_message.author.bot
                and not reference_message.content.startswith(
                    "※"
                )  # This condition lets webhook messages to be checked
            ):
                await ctx.send("Cannot check values of messages from bot")
                return
            else:
                print(
                    f"Original Message Content: {reference_message.content}, posted by {message.author}"
                )
            
            current_values_dict = VALUES_DICT if VALUES_DICT else DEFAULT_VALUES_DICT
            values_list = f"Community Defined Values:\n\n"
            for value in current_values_dict.keys():
                values_list += f"* {value}\n"
            llm_response = await self.analyze_values(reference_message.content)
            message_content = f"```{values_list}``````Message: {reference_message.content}\n\nMessage author: {reference_message.author}```\n> **Values Analysis:** {llm_response}"
            await ctx.send(message_content)

    async def analyze_values(self, text):
        """
        Analyze message content based on values
        """
        llm = OpenAI(temperature=0.5, model_name="gpt-3.5-turbo")
        template = f"We hold and maintain a set of mutually agreed-upon values. Analyze whether the message '{text}' is in accordance with the values we hold:\n\n"
        current_values_dict = VALUES_DICT if VALUES_DICT else DEFAULT_VALUES_DICT
        for (
            value,
            description,
        ) in current_values_dict.items():
            template += f"- {value}: {description}\n"
        template += f"\nNow, analyze the message:\n{text}. Keep your analysis concise."
        prompt = PromptTemplate.from_template(template=template)
        chain = LLMChain(llm=llm, prompt=prompt)
        return chain.run({"text": text})

class Eloquence(CultureModule):
    async def filter_message(self, ctx, message: discord.Message, message_string: str) -> str:
        """
        A LLM filter for messages during the /eloquence command/function
        """
        llm = OpenAI(temperature=0.5, model_name="gpt-3.5-turbo")
        prompt = PromptTemplate.from_template(
            template="You are from the Shakespearean era. Please rewrite the following input in a way that makes the speaker sound as eloquent, persuasive, and rhetorical as possible, while maintaining the original meaning and intent. Don't complete any sentences, jFust rewrite them. Input: {input_text}"
        )
        prompt.format(input_text=message_string) # TODO: is both formatting and passing the message_string necessary?
        chain = LLMChain(llm=llm, prompt=prompt)
        return chain.run(message_string) 

ACTIVE_MODULES_BY_CHANNEL = defaultdict(OrderedSet)

async def toggle_culture_module(ctx, module_name, state):
    """
    If state is True, turnon the culture module
    if state is False, turn off the culture module
    """
    channel_name = str(ctx.channel) # TODO: add the modules, not just the channel name to this list
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

    # TODO: make state a more descriptive variable name
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
    if module.config["message_alter_mode"] == "llm" and state:
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
        name="ACTIVE CULTURE MODULES:",
        value=active_culture_module_values,
        inline=False,
    )

    await ctx.send(embed=embed)


CULTURE_MODULES = {
    "obscurity": Obscurity(
        {
            "name": "obscurity",
            "global_state": False,
            "local_state": False,
            "mode": "scramble",
            "help": False,
            "message_alter_mode": "text",
            "alter_message": True,
            "activated_message": "Messages will be distored based on mode of obscurity.",
            "deactivated_message": "Messages will no longer be distored by obscurity.",
            "url": "https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/obscurity.png",
            "icon": GOVERNANCE_SVG_ICONS["culture"],
            "input_value": 0,
        }
    ),
    "eloquence": Eloquence(
        {
            "name": "eloquence",
            "global_state": False,
            "local_state": False,
            "mode": None,
            "help": False,
            "message_alter_mode": "llm",
            "llm_disclosure": "You are from the Shakespearean era. Please rewrite the messages in a way that makes the speaker sound as eloquent, persuasive, and rhetorical as possible, while maintaining the original meaning and intent.",
            "activated_message": "Messages will now be process through an LLM.",
            "deactivated_message": "Messages will no longer be processed through an LLM.",
            "url": "https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/eloquence.png",
            "icon": GOVERNANCE_SVG_ICONS["culture"],
            "input_value": 0,
        }
    ),
    "ritual": Ritual(
        {
            "name": "ritual",
            "global_state": False,
            "local_state": False,
            "mode": None,
            "help": False,
            "message_alter_mode": "llm",
            "llm_disclosure": "Write a message that reflects the content in the posted message and is cast in agreement with the previous message. Preserve and transfer any spelling errors or text transformations in these messages in the response.",
            "activated_message": "A ritual of agreement permeates throughout the group.",
            "deactivated_message": "Automatic agreement has ended. But will the effects linger in practice?",
            "url": "",  # TODO: make ritual img
            "icon": GOVERNANCE_SVG_ICONS["culture"],
            "input_value": 0,
        }
    ),
    "diversity": Diversity(
        {
            "name": "diversity",
            "global_state": False,
            "local_state": False,
            "mode": None,
            "help": False,
            "message_alter_mode": None,
            "activated_message": "A measure of diversity influences the distribution of power.",
            "deactivated_message": "Measurements of diversity continue, but no longer govern this environment's interactions.",
            "url": "",  # TODO: make ritual img
            "icon": GOVERNANCE_SVG_ICONS["culture"],
            "input_value": 0,
        }
    ),
    "values": Values(
        {
            "name": "values",
            "global_state": False,
            "mode": None,
            "help": True,
            "how_to_use": "Get a vibe check. See how aligned a post is with your community's values.\nReply to the message you want to check and type `check-values`.",
            "local_state": False,
            "message_alter_mode": None,
            "llm_disclosure": "You hold and maintain a set of mutually agreed upon values. The values you maintain are the values defined by the community. You review the contents of messages sent for validation and analyze the contents in terms of the values you hold. You describe in what ways the input text are aligned or unaligned with the values you hold.",
            "activated_message": "A means of validating the cultural alignment of this online communiuty is now available. Respond to a message with check-values.",
            "deactivated_message": "Automatic measurement of values is no longer present, through an essence of the culture remains, and you can respond to messages with `check-values` to check value alignment.",
            "url": "",  # TODO: make ritual img
            "icon": GOVERNANCE_SVG_ICONS["culture"],
            "input_value": 0,
        }
    ),
}

async def send_msg_to_random_player(game_channel):
    print("Sending random DM...")
    players = [member for member in game_channel.members if not member.bot]
    random_player = random.choice(players)
    dm_channel = await random_player.create_dm()
    await dm_channel.send(
        "🌟 Greetings, esteemed adventurer! A mischievous gnome has entrusted me with a cryptic message just for you: 'In the land of swirling colors, where unicorns prance and dragons snooze, a hidden treasure awaits those who dare to yawn beneath the crescent moon.' Keep this message close to your heart and let it guide you on your journey through the wondrous realms of the unknown. Farewell, and may your path be ever sprinkled with stardust! ✨"
    )


