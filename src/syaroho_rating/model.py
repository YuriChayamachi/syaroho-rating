from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List

import tweepy

from syaroho_rating.utils import clean_html_tag, tweetid_to_datetime


@dataclass(frozen=True)
class User:
    id: str
    name: str
    """the name defined in user profile"""
    username: str
    """the name followed after @"""
    protected: bool

    @staticmethod
    def from_responses_v1(
        raw_response: Iterable[Dict[str, Any]]
    ) -> List["User"]:
        return [
            User(
                id=u["id"],
                name=u["name"],
                username=u["screen_name"],
                protected=u["protected"],
            )
            for u in raw_response
        ]

    @staticmethod
    def from_responses_v2(users: Iterable[tweepy.User]) -> List["User"]:
        return [
            User(
                id=u.id, name=u.name, username=u.username, protected=u.protected
            )
            for u in users
        ]


@dataclass(frozen=True)
class Tweet:
    text: str
    source: str
    created_at_ms: datetime
    id: str
    author: User

    @staticmethod
    def from_responses_v1(
        raw_response: Iterable[Dict[str, Any]]
    ) -> List["Tweet"]:
        return [
            Tweet(
                text=t["text"],
                # s["source"] is like "<a href="url_to_client">client_name</a>"
                source=clean_html_tag(t["source"]),
                created_at_ms=tweetid_to_datetime(t["id"]),
                id=t["id"],
                author=User(
                    id=t["user"]["id"],
                    name=t["user"]["name"],
                    username=t["user"]["screen_name"],
                    protected=t["user"]["protected"],
                ),
            )
            for t in raw_response
        ]

    @staticmethod
    def from_responses_v2(
        tweets: Iterable[tweepy.Tweet], users: Iterable[tweepy.User]
    ) -> List["Tweet"]:
        users_dict = {
            u.id: User(u.id, u.name, u.username, u.protected) for u in users
        }
        return [
            Tweet(
                text=t.text,
                source=t.source,
                created_at_ms=tweetid_to_datetime(t.id),
                id=t.id,
                author=users_dict[t.author_id],
            )
            for t in tweets
        ]
