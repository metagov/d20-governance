import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import discord
from d20_governance.bot import process_stage, start_quest
from d20_governance.tests.utils import create_quest
from d20_governance.utils.constants import MINIGAME_JOSH
from d20_governance.utils.utils import Quest  # replace with actual import
from discord.ext import commands

class TestQuestMockActions(unittest.IsolatedAsyncioTestCase):
    @patch('d20_governance.bot.bot', new_callable=MagicMock) 
    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_quest(self, mock_sleep, mock_bot):
        quest = create_quest()
        mock_bot.quest = quest
        mock_ctx = unittest.mock.Mock(spec=commands.Context)
        mock_bot.get_context = AsyncMock()
        mock_bot.get_context.return_value = mock_ctx
        
        # Create a mock command with a callback coroutine
        mock_command = MagicMock()
        mock_command.callback = AsyncMock()  # add callback coroutine to the mock command
        
        mock_bot.get_command.return_value = mock_command  # make get_command return the mock command
        await start_quest(quest)

        quest.game_channel.send.assert_called()


if __name__ == '__main__':
    unittest.main()
