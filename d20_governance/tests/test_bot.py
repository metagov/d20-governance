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
        await start_quest(mock_ctx, quest)

        quest.game_channel.send.assert_called()

from unittest.mock import patch, MagicMock, call
from d20_governance.bot import Stage, Quest

class TestRetryAction(unittest.IsolatedAsyncioTestCase):
    @patch('d20_governance.bot.bot', new_callable=MagicMock)
    @patch('d20_governance.bot.execute_action', new_callable=AsyncMock)
    @patch('d20_governance.bot.stream_message', new_callable=AsyncMock)
    async def test_retry_action(self, mock_stream_message, mock_execute_action, mock_bot):
        # Set up stage and quest objects
        action = MagicMock()
        action.retries = 3
        action.retry_message = 'Retry message'
        action.failure_message = 'Failure message'
        stage = Stage(name='Test Stage', message='Test message', actions=[action], progress_conditions=[])
        quest = create_quest()
        quest.stages = [stage]

        # Make execute_action raise an exception
        mock_execute_action.side_effect = Exception('Test exception')

        mock_ctx = unittest.mock.Mock(spec=commands.Context)

        # Run the function
        with self.assertRaises(Exception):
            await process_stage(mock_ctx, stage, quest)

        # Check that the retry message was sent the correct number of times
        calls = [call.send(action.retry_message) for _ in range(action.retries)]
        quest.game_channel.assert_has_calls(calls)

        # Check that the failure message was sent once
        quest.game_channel.send.assert_called_with(action.failure_message)

        # Clean up mocks
        mock_stream_message.reset_mock()
        mock_execute_action.reset_mock()

if __name__ == '__main__':
    unittest.main()
