from collections import defaultdict
from typing import Callable
from typing import List

from slack import RTMClient
from slack import WebClient


class SlackClient(object):
    token = None
    _client = None
    web_client: WebClient = None
    callbacks = defaultdict(list)

    def __init__(self, token: str):
        self.token = token
        self.web_client = WebClient(token=self.token)

    @property
    def client(self) -> RTMClient:
        assert self._client, "Client must be initialized first"
        return self._client

    @client.setter
    def client(self, client):
        self._client = client

    def connect(self):
        self.client = RTMClient(token=self.token)
        self.add_callback("open", self._on_open)
        self.client.start()

    def add_callback(self, event_type: str, callback: Callable):
        self.callbacks[event_type].append(callback)
        RTMClient.on(event=event_type, callback=callback)

    def emails_to_user_ids(self, emails: List[str]):
        for email in emails:
            user = self.web_client.users_lookupByEmail(email=email)
            print(user)

    def subscribe_to_presence(self, user_ids: List[str]):
        res = self.client.send_over_websocket(
            payload={"type": "presence_sub", "ids": user_ids,}
        )

    def _on_open(self, **payload: dict):
        self.slack_team = payload["data"]["team"]
        self.slack_self = payload["data"]["self"]
        self.web_client = payload["web_client"]
