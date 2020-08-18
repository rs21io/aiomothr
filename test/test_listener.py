import os
import pytest
import sys
from asynctest import CoroutineMock, MagicMock, patch
from collections import namedtuple

sys.path.append('.')

from aiomothr import Listener

class MockSender:
    def __init__(self, channel, message, is_pattern=False):
        channel_obj = namedtuple('channel_obj', 'is_pattern name')
        self.channel = channel_obj(is_pattern=is_pattern, name=channel)
        if is_pattern:
            self.message = (channel, message)
        else:
            self.message = message


class TestListener:
    @patch('aioredis.create_redis')
    @patch('aiomothr.listener.Receiver')
    def setup_method(self, _, mock_pubsub, mock_redis):
        messages = [
            MockSender(channel=b'test', message=b'test message'),
            MockSender(channel=b'test:testing', message=b'test message', is_pattern=True),
            MockSender(channel=b'test', message=b'test message2'),
            MockSender(channel=b'test', message=b'test message3')
        ]
        messages = [(msg.channel, msg.message) for msg in messages]
        mock_redis.return_value.subscribe = CoroutineMock()
        mock_redis.return_value.psubscribe = CoroutineMock()
        mock_pubsub.return_value.iter = MagicMock()
        mock_pubsub.return_value.iter.return_value.__aiter__.return_value = [msg for msg in messages]
        self.listener = Listener(['test', 'test:*'])
        self.listener.handle_message = CoroutineMock()

    @patch('aioredis.create_redis')
    def test_run(self, mock_redis):
        self.listener.start()
        assert(self.listener.handle_message.call_count == 4)
