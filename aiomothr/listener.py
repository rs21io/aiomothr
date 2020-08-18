# Copyright 2020 Resilient Solutions Inc. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import aioredis
import asyncio
import os
from aioredis.pubsub import Receiver
from typing import List

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')


class Listener:
    """Object that listens and responds to specific events triggered on the system.

    This class is intended to be used as a base class for creating listeners. To use
    simply inherit and override the ``handle_message`` method.

    Args:
        channels (str, :obj:`list` of :obj:`str`): Event channel(s) to listen on.
            These can be explicit names (e.g., channel:1) or patterns with a
            wildcard (e.g., channel:*) which will listen to all channels that start
            with "channel:".
    """
    def __init__(self, channels: List[str]) -> None:
        loop = asyncio.get_event_loop()
        db = loop.run_until_complete(aioredis.create_redis(f'redis://{REDIS_HOST}'))
        pubsub = Receiver(loop=loop)

        if isinstance(channels, str):
            channels = [channels]
        subs = [pubsub.channel(channel)
                for channel in channels if not channel.endswith('*')]
        pattern_subs = [pubsub.pattern(channel)
                        for channel in channels if channel.endswith('*')]
        if len(subs) > 0:
            loop.run_until_complete(db.subscribe(*subs))
        if len(pattern_subs) > 0:
            loop.run_until_complete(db.psubscribe(*pattern_subs))

        self.pubsub = pubsub
        self.subs = subs
        self.psubs = pattern_subs

    async def handle_message(self, channel, message):
        """Handler for received messages

        Args:
            channel (str): Name of the channel on which the message was received
            message (str): The message received on the channel
        """
        raise NotImplementedError('You must override handle_message to use this class')

    async def run(self) -> None:
        """Listen for messages on subscribed channels"""
        async for channel, message in self.pubsub.iter():
            if channel.is_pattern:
                channel = message[0]
                message = message[1]
            else:
                channel = channel.name
            asyncio.create_task(
                self.handle_message(channel.decode(), message.decode())
            )

    def start(self) -> None:
        print('Starting listener')
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.run())
        except KeyboardInterrupt:
            print('Stopping Listener')
        finally:
            # Unsubscribe from channels
            db = loop.run_until_complete(aioredis.create_redis(f'redis://{REDIS_HOST}'))
            map(lambda channel: loop.run_until_complete(db.unsubscribe(channel=channel)), self.subs)
            map(lambda pattern: loop.run_until_complete(db.punsubscribe(pattern=pattern)), self.psubs)
            self.pubsub.stop()
            loop.close()
