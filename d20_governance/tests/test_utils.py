import unittest
from unittest.mock import MagicMock, AsyncMock, call
import asyncio
import shlex

from d20_governance.utils.utils import execute_action  # replace with actual import

class TestExecuteAction(unittest.IsolatedAsyncioTestCase):
    async def test_execute_action(self):
        # Create a mock bot object
        mock_bot = MagicMock()

        # Configure the mock bot to return a mock command when get_command() is called
        mock_command = AsyncMock()
        mock_bot.get_command.return_value = mock_command

        # Create a mock temp_channel object
        mock_temp_channel = AsyncMock()

        # Create a mock message object
        mock_message = MagicMock()
        mock_temp_channel.fetch_message.return_value = mock_message

        # Create a mock context object
        mock_ctx = MagicMock()
        mock_bot.get_context.return_value = mock_ctx

        # The action to execute
        action = "/some_command some_arg"

        # Run the function
        await execute_action(mock_bot, action, mock_temp_channel)

        # Check that get_command() was called with the expected arguments
        command_name = shlex.split(action.lower())[0]
        mock_bot.get_command.assert_called_with(command_name)

        # Check that the command's callback was called with the expected context and arguments
        mock_command.callback.assert_called_with(mock_ctx, *shlex.split(action.lower())[1:])

        # Check that fetch_message() was called with the last message ID
        mock_temp_channel.fetch_message.assert_called_with(mock_temp_channel.last_message_id)

        # Check that get_context() was called with the last message
        mock_bot.get_context.assert_called_with(mock_message)
