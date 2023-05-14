import random
from constants import *
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from decisions import decision


# Culture Utils
def scramble_word(word):
    if len(word) <= 3:
        return word
    else:
        middle = list(word[1:-1])
        random.shuffle(middle)
        return word[0] + "".join(middle) + word[-1]


def scramble(text):
    words = text.split()
    scrambled_words = [scramble_word(word) for word in words]
    return " ".join(scrambled_words)


def replace_vowels(text):
    vowels = "aeiou"
    message_content = text.lower()
    return "".join([" " if c in vowels else c for c in message_content])


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


def pig_latin(text):
    words = text.split()
    pig_latin_words = [pig_latin_word(word) for word in words]
    return " ".join(pig_latin_words)


def camel_case(text):
    words = text.split()
    camel_case_words = [word.capitalize() for word in words]
    return "".join(camel_case_words)


async def eloquence_filter(text):
    """
    A LLM filter for messages during the /eloquence command/function
    """
    llm = OpenAI(temperature=0.9)
    prompt = PromptTemplate(
        input_variables=["input_text"],
        template="You are from the Shakespearean era. Please rewrite the following text in a way that makes the speaker sound as eloquent, persuasive, and rhetorical as possible, while maintaining the original meaning and intent: {input_text}",
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain.run(text)


async def send_msg_to_random_player():
    print("Sending random DM...")
    players = [member for member in TEMP_CHANNEL.members if not member.bot]
    random_player = random.choice(players)
    dm_channel = await random_player.create_dm()
    await dm_channel.send(
        "🌟 Greetings, esteemed adventurer! A mischievous gnome has entrusted me with a cryptic message just for you: 'In the land of swirling colors, where unicorns prance and dragons snooze, a hidden treasure awaits those who dare to yawn beneath the crescent moon.' Keep this message close to your heart and let it guide you on your journey through the wondrous realms of the unknown. Farewell, and may your path be ever sprinkled with stardust! ✨"
    )


async def culture_options_msg(ctx):
    print("A list of culture modules are presented")
    culture_how = "how culture is defined"
    msg = await ctx.send(
        "Decide a new cultural value to adopt for your organization:\n"
        f"{list_culture_modules}"
    )
    # Add reactions to the sent message based on emojis in culture_modules list
    for emoji in culture_emojis:
        await msg.add_reaction(emoji)
    # TODO: Collect and count the votes for each value
    # TODO: Apply the chosen communication constraint based on the new value
    await decision(ctx, culture_how)
