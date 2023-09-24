
# D20 Governance Bot


## How to run locally

1. Install poetry for managing dependencies
2. Run `poetry install`
3. Run `poetry shell`
4. Create a .env file and set DISCORD_TOKEN environment variable to your bot's token as well as OPENAI_API_KEY to your OpenAI API key. 
5. Make sure the bot has been added to your server with admin permissions.
6. Run python3 d20_governance/__main__.py. The bot will create all the necessary channels in your server once it runs.
7. Try the `/solo` command in the #d20-agora channel to start a solo quest, and use -f for fast mode
8. Running tests
    Run `pytest` from project root.

## Overview
The d20 bot allows communities to play governance games in an LLM-mediated environment. Individuals and groups can come together to embark on a governance “quest”, where they make lightweight decisions about the community and experience varied mechanisms of decision-making. The bot moderates the governance game through different "culture modules" - playfully modifying users' messages to cultivate diverse interaction environments for participants.

[Join our discord server to try it out!](https://discord.gg/ex9D8RcN)

### Build A Group Voice Game

#### Stages

##### Propose a quest from the agora

Start in the #d20-agora channel and use the `/embark` command to start a new quest, specifying which quest you want to play as well as the number of players. The bot will create a new channel for the quest and direct you to it.

##### The Quest Begins

Players are welcomed and introduced to the game's objectives: deciding the group's name, main topic of interest, and way of speaking. The group explores conversational confusion and deliberates to shape the community's communication in the agora. The game begins by reviewing the default values inherited from #agora. Players can propose revisions or object to values through lazy consensus. To check the active values, use the "-list values" command.

##### Group Name
 
Players propose names for the group and deliberate. A random culture module may be activated during this period, affecting the conversation. After deliberation, players vote on the proposed names. If consensus is not reached, the game progresses with additional conditions or actions.

##### Group's Main Topic of Interest

Players propose and deliberate on the group's main topic of interest. After a set deliberation time, players vote on the proposed topics. The game progresses based on the voting results and any additional conditions or actions.

##### Group Way of Speaking

Players discuss and propose the group's way of speaking, considering formality, tone, and style. After deliberation and voting, the game progresses, considering the results and any additional conditions or actions.


#### After the Game

A record of the decisions made is published, summarizing the options considered and methods used. 

The "culture" of the community is generated from the group decisions. A new wildcard prompt is generated based on the decided upon community name, purpose, and goal. Players then return to #d20-agora channel where they can test out their new community culture using the `/wildcard` command. When wildcard mode is on, all language that happens in the agora will be transformed according to the community's culture.

### Culture of your community

Your culture will affect your communication. Think about what cultural environment you want in your community and how you would like that culture to impact your communication.
For example, you already experienced a culture of “eloquence” where your communication with your fellow community members was automatically transformed to be in verbose Shakespearean rhetoric. 
The culture you decide on will become a new communication constraint you can invoke in the agora channel and will become playable in subsequent Build a Community games.

### Agora 
The agora channel (#d20-agora) is a free-form discussion and experimentation channel meant to  


#### Decision Modules
- **Majority**: The Majority decision model allows for decisions when the community is not in full agreement. Majority voting aims to reach a decision even if not all players agree, more than half of the group agree. 
- **Consensus**: Consensus voting is also known as unanimous consent. It aims for full agreement through discussion. 
- **Lazy Consensus**: Lazy Consensus is a decision mechanism that assumes players to agree with the presented option unless they explicitly object to it. Decision occurs when no objections, rather than unanimous agreement. 
- **BDFL**: Benevolent Dictatorship is a governance model where one person has the final say over decisions. Others in the community have no way to override the BDFL's decisions even if they disagree.

#### Culture Modules
- **Eloquence**: Manipulates messages to be elaborate and Shakespearean. 
- **Obscurity**: Manipulates message text to make it obscure and hard to understand.
- **Ritual**: Modifies messages to be in agreement with the group’s previous messages. 

### Values Feature 
- Propose value and definition
- Propose-values
- Revise-values 
- Decision-making about values: lazy consensus
- Check-values of messages## Future Development Goals / Potential Ideas / Next Steps
Develop more decision and culture modules and more types of quests.
## Culture Module Functionalities 

The culture modes act as language interferences that transform user messages in different ways:
- The modes work by detecting a new message and then deleting the original message.
- The message content is then passed through the active culture mode functions to transform it.
- For example, the obscurity mode might scramble the words, replace vowels, or translate to pig latin.
- The transparency mode simply passes the original text unchanged.
- The eloquence mode attempts to refine and formalize the text using LLMs.
- After transformation, the modified message content is sent via a webhook under the original user's name.
- This process effectively disturbs or alters the user's original language before broadcasting it to the channel.
- The result is that users see altered messages according to the active modes, rather than the unmodified original text.
- Modes can be toggled on or off, resulting in messages either being disturbed or passed through cleanly.
- This system allows experimenting with how different language norms like secrecy, rituals, and formality affect governance discussions. By transforming text before sending, culture modes allow experimenting with how different communication norms affect governance.
- The culture modes create a space where language itself is fluid and subject to communal decisions and norms.
### Technical Capabilities

- The goal of the bot is to help communities learn and experiment with governance in an engaging setting. It provides a governance simulation platform through Discord, with capabilities for proposing and running quests, decision-making, and cultural modes. 
- The d20 bot allows running “quests” with different parameters and objectives. For example, there could be a quest around selecting a community mascot, or governing a hypothetical space colony. 
- It implements culture modules that transform how users communicate. These culture modules function by creating interferences that change and rewrite users’ original messages. 
- It has decision-making capabilities. Different voting systems can be used like majority rule, consensus, etc.
- Users can submit proposals and participate in the governance process through Discord.