from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List

from syaroho_rating.utils import clean_html_tag, tweetid_to_datetime


@dataclass(frozen=True)
class User:
    id: str
    username: str
    protected: bool

    @staticmethod
    def from_responses_v1(raw_response: Iterable[Dict[str, Any]]) -> List["User"]:
        return [
            User(
                id=u["id"],
                username=u["screen_name"],
                protected=u["protected"],
            )
            for u in raw_response
        ]


@dataclass(frozen=True)
class Tweet:
    text: str
    source: str
    created_at_ms: datetime
    id: str
    author: User

    @staticmethod
    def from_responses_v1(raw_response: Iterable[Dict[str, Any]]) -> List["Tweet"]:
        return [
            Tweet(
                text=t["text"],
                # s["source"] is like "<a href="url_to_client">client_name</a>"
                source=clean_html_tag(t["source"]),
                created_at_ms=tweetid_to_datetime(t["id"]),
                id=t["id"],
                author=User(
                    id=t["user"]["id"],
                    username=t["user"]["screen_name"],
                    protected=t["user"]["protected"],
                ),
            )
            for t in raw_response
        ]
