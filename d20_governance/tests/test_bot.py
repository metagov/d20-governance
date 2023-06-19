import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import discord
from d20_governance.bot import process_stage, start_quest
from d20_governance.tests.utils import create_quest
from d20_governance.utils.constants import MINIGAME_JOSH
from d20_governance.utils.utils import Quest  # replace with actual import


class TestQuestMockActions(unittest.TestCase):
    @patch('d20_governance.bot.execute_action', new_callable=AsyncMock)
    @patch('d20_governance.bot.bot', new_callable=MagicMock) 
    @patch('asyncio.sleep', new_callable=AsyncMock)
    def test_quest(self, mock_sleep, mock_bot, mock_execute_action):
        quest = create_quest()
        mock_bot.quest = quest
        asyncio.run(start_quest(quest))

        mock_execute_action.assert_called()
        quest.game_channel.send.assert_called()

if __name__ == '__main__':
    unittest.main()
