import random
import discord
from d20_governance.utils.constants import *
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from langchain.chat_models import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage


# Culture Utils
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
