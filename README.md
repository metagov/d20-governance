# D20 Governance Bot

## How to run locally

1. Install poetry for managing dependencies
2. Run `poetry install`
3. Run `poetry shell`
4. Set DISCORD_TOKEN environment variable to your bot's token
5. Run `python3 bot.py`

## Running tests

Run `pytest` from project root.

## D20 Bot Overview 

### Overview

#### v2
The d20 bot empowers communities to play governance games. Individuals and groups can come together to embark on a governance “quest”, where they make lightweight decisions about the community and experience varied mechanisms of decision-making. The bot moderates the governance game through different "culture models" - playfully modifying users' messages to cultivate diverse interaction environments for participants.

## Build A Community Game 

### Stages 

#### Values
The game begins by reviewing the default values inherited from #agora. Players can propose revisions or object to values through lazy consensus. To check the active values, use the "-list values" command.

#### Picking A Community Name
The random decision module gets activated. Players propose new community name options. They then have time to deliberate before voting.
When the deliberation time ends, the community makes a decision by voting. If a name receives consensus, it is selected.
If no consensus is reached, the bot will automatically pick a name on the group's behalf. In this case, a random culture module gets activated, obscuring players' speech and changing their output. This requires finding creative ways to communicate throughout the decision making process.

#### Picking A Community Purpose
Next, players are tasked with picking a community purpose. They will have a set time to deliberate on options before submitting their votes.

#### First Action
Players must now work to pick the community's first action.

#### After the Game
A record of the decisions made is published, summarizing the options considered and methods used. 

Culture of the community is generated from the group decisions. A new greeting message is also generated based on the decided upon community name, purpose, and goal. Players then return to #agora where they can test out their new community culture using the "-wildcard" function. 

### Culture of your community
Your culture will affect your communication. Think about what cultural environment you want in your community and how you would like that culture to impact your communication.
For example, you already experienced a culture of “eloquence” where your communication with your fellow community members was automatically transformed to be in verbose Shakespearean rhetoric. 
The culture you decide on will become a new communication constraint you can invoke in the agora channel and will become playable in subsequent Build a Community games.

### Agora 
Our Discord Channel is set up for people to experience with culture modules

### Features:

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
- Check-values of messages

### Future Development Goals / potential ideas / next steps
- We hope to develop customizable quests
- More mini-games

---

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

## Technical Capabilities

- The goal of the bot is to help communities learn and experiment with governance in an engaging setting. It provides a governance simulation platform through Discord, with capabilities for proposing and running quests, decision-making, and cultural modes. 
- The d20 bot allows running “quests” with different parameters and objectives. For example, there could be a quest around selecting a community mascot, or governing a hypothetical space colony. 
- It implements culture modules that transform how users communicate. These culture modules function by creating interferences that change and rewrite users’ original messages. 
- It has decision-making capabilities. Different voting systems can be used like majority rule, consensus, etc.
- Users can submit proposals and participate in the governance process through Discord.
