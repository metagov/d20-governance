## How to run

1. Install poetry for managing dependencies
2. Run `poetry install`
3. Run `poetry env`
4. Set DISCORD_TOKEN environment variable to your bot's token
5. Run `python3 bot.py`


## Designing a new game

1. Create a new .yaml file in the `d20_governance/game_configs` directory. Copy an existing template to get you started. 
2. Create as many game stages as you like, following the existing template.
3. To use a particular game template, paste its the contents into the `d20_governance/config.yaml` file and run the bot.

**Ideas for Game Actions:** 

Discussion: Encourage participants to engage in structured discussions on a specific topic or issue. The bot could provide a prompt, and participants could share their thoughts, opinions, or experiences.

Brainstorming: Ask participants to come up with ideas or solutions to a given problem or challenge. The bot could gather and display the ideas and allow users to react to or discuss them further.

Delegation: Assign participants to different roles or tasks based on their expertise or interests. The bot could facilitate the process by collecting information about participants' skills and preferences and assigning tasks accordingly.

Consensus Building: Instead of voting, require participants to come to a consensus on a decision or proposal. The bot could monitor the conversation and provide prompts or guidance to help users reach an agreement.

Polling: Instead of a formal vote, the bot could create quick polls to gauge users' opinions on a topic or decision. The results could inform further discussions or decision-making.

Role-playing: Participants could assume different roles within a fictional scenario to explore governance concepts or practice decision-making. The bot could facilitate the role-playing by providing scenarios, assigning roles, or guiding the narrative.

Trivia or Quiz: The bot could present trivia questions or quizzes related to governance concepts or the game's theme. Participants could answer individually or as teams to test their knowledge and learn more about the subject.

Resource Allocation: The bot could simulate a budget or resources that participants must allocate to different projects or initiatives. Users would need to discuss and decide how to distribute the resources to achieve the best outcome.