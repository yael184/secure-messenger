"""
broadcaster.py — Fan-out messaging for Server-Sent Events.

This module manages real-time message delivery to all connected clients.
When a user sends a message, it's published to every connected SSE client
so they receive updates instantly without polling.

HOW IT WORKS:
  1. Each connected client subscribes with subscribe()
  2. When a message is sent, publish() broadcasts it to all subscribers
  3. Each subscriber receives the message via their async generator
  4. If a client disconnects, unsubscribe() removes them
"""

import asyncio
import logging
from typing import AsyncGenerator

log = logging.getLogger(__name__)


class Broadcaster:
    """Manages real-time message fan-out to multiple connected clients."""

    def __init__(self):
        # Each open connection gets its own queue, keyed by a unique connection
        # id (NOT the username) so the same user can hold several streams at
        # once (e.g. two browser tabs) without one overwriting the other.
        # When publish() is called, we enqueue the message to every queue.
        self.subscriptions: dict[int, asyncio.Queue] = {}
        self._next_id = 0

    async def subscribe(self, username: str) -> AsyncGenerator:
        """
        Open a subscription for a user.

        Usage:
            async for message in broadcaster.subscribe(username):
                # Yield message to client via SSE
                yield message
        """
        # Create a new queue for this connection under a unique id
        queue = asyncio.Queue()
        sub_id = self._next_id
        self._next_id += 1
        self.subscriptions[sub_id] = queue
        log.info(f"User {username} subscribed. Total subscribers: {len(self.subscriptions)}")

        try:
            while True:
                # Wait for a message to arrive in this subscriber's queue
                message = await queue.get()
                yield message
        except asyncio.CancelledError:
            log.info(f"User {username} unsubscribed.")
            raise
        finally:
            # Clean up when the connection closes
            self.subscriptions.pop(sub_id, None)
            log.info(f"User {username} disconnected. Remaining subscribers: {len(self.subscriptions)}")

    async def publish(self, message: dict):
        """
        Broadcast a message to all connected subscribers.
        
        Args:
            message: dict with keys like 'id', 'sender', 'recipient', 'content', 'created_at'
        
        Safely handles the case where subscribers disconnect mid-publish.
        """
        log.info(f"Broadcasting message from {message.get('sender')} to {len(self.subscriptions)} subscribers")

        # Publish to all current subscribers
        # Use a list() copy because the dict may change during iteration if someone disconnects
        for sub_id, queue in list(self.subscriptions.items()):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full — client is slow or disconnected
                log.warning(f"Queue full for subscriber {sub_id}, skipping message")
            except Exception as e:
                log.error(f"Error publishing to subscriber {sub_id}: {e}")


# Global broadcaster instance — shared across all requests
broadcaster = Broadcaster()
