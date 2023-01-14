import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Protocol, Union

import boto3
import tweepy
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

from syaroho_rating.consts import S3_BUCKET_NAME, STORAGE
from syaroho_rating.model import Tweet, User


def get_io_handler(version: int) -> "IOHandler":
    base_handler: IOBaseHandler
    if STORAGE == "s3":
        base_handler = S3IOBaseHandler()
    elif STORAGE == "local":
        base_handler = LocalIOBaseHandler()
    else:
        raise RuntimeError(f"Unexpected STORAGE variable: {STORAGE}")

    if version == 1:
        return IOHandlerV1(base_handler)
    if version == 2:
        return IOHandlerV2(base_handler)
    else:
        raise RuntimeError(f"Unexpected version: {version}")


JsonObj = Union[List[Dict[str, Any]], Dict[str, Any]]


class IOBaseHandler(Protocol):
    def save_dict(self, dict_obj: JsonObj, relative_path: str) -> None:
        ...

    def load_dict(self, relative_path: str) -> Any:
        ...

    def list_path(self, relative_path: str) -> List[Any]:
        ...

    def delete(self, relative_path: str) -> None:
        ...


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, dt.datetime):
        return obj.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    raise TypeError("Type %s not serializable" % type(obj))


class S3IOBaseHandler(IOBaseHandler):
    temp_dir = Path("temp")

    def __init__(self) -> None:
        super().__init__()
        self.s3 = boto3.client("s3")
        self.temp_dir.mkdir(exist_ok=True)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(3)
    )
    def save_dict(self, dict_obj: JsonObj, relative_path: str) -> None:
        temp_path = self.temp_dir / f"{uuid.uuid4()}.json"
        with temp_path.open("w") as f:
            json.dump(dict_obj, f, indent=4, ensure_ascii=False, default=json_serial)
        with temp_path.open("rb") as f:
            self.s3.upload_fileobj(f, S3_BUCKET_NAME, relative_path)
        temp_path.unlink(missing_ok=True)
        return

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(3)
    )
    def load_dict(self, relative_path: str) -> Any:
        temp_path = self.temp_dir / f"{uuid.uuid4()}.json"
        with temp_path.open("wb") as f:
            try:
                self.s3.download_fileobj(S3_BUCKET_NAME, relative_path, f)
            except ClientError as e:
                raise FileNotFoundError(e)
        with temp_path.open() as f:
            dict_obj = json.load(f)
        temp_path.unlink(missing_ok=True)
        return dict_obj

    def delete(self, relative_path: str) -> None:
        raise NotImplementedError

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(3)
    )
    def list_path(self, relative_path: str) -> List[Any]:
        """バケットルートからの相対パスのリストを返す"""
        # use paginator since list_object only returns maximum 1000 objects
        paginator = self.s3.get_paginator("list_objects")
        res_iterator = paginator.paginate(
            Bucket=S3_BUCKET_NAME, Prefix=relative_path, MaxKeys=1000000
        )
        obj_list = []
        for res in res_iterator:
            obj_list += [c["Key"] for c in res.get("Contents", [])]
        return obj_list


class LocalIOBaseHandler(IOBaseHandler):
    def __init__(self, base_path: Path = Path("data")):
        super().__init__()
        self.base_path = base_path
        self.base_path.mkdir(exist_ok=True)

    def save_dict(self, dict_obj: JsonObj, relative_path: str) -> None:
        file_path = self.base_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w") as f:
            json.dump(dict_obj, f, indent=4, ensure_ascii=False, default=json_serial)
        return

    def load_dict(self, relative_path: str) -> Any:
        file_path = self.base_path / relative_path
        with file_path.open() as f:
            dict_obj = json.load(f)
        return dict_obj

    def delete(self, relative_path: str) -> None:
        pass

    def list_path(self, relative_path: str) -> List[Any]:
        """base path からの相対パスのリストを返す"""
        dir_path = self.base_path / relative_path
        obj_list = [str(p.relative_to(self.base_path)) for p in dir_path.iterdir()]
        return obj_list


class IOHandler(Protocol):
    def get_statuses(self, date: dt.date) -> List[Tweet]:
        ...

    def save_statuses(self, statuses: JsonObj, date: dt.date) -> None:
        ...

    def get_statuses_dq(self, date: dt.date) -> List[Tweet]:
        ...

    def save_statuses_dq(self, statuses: JsonObj, date: dt.date) -> None:
        ...

    def get_members(self) -> JsonObj:
        ...

    def save_members(self, members: JsonObj) -> None:
        ...

    def get_rating_info(self, date: dt.date) -> Dict[str, Any]:
        ...

    def save_rating_info(self, rating_info: Dict, date: dt.date) -> None:
        ...


class IOHandlerV1(object):
    def __init__(self, base_handler: IOBaseHandler) -> None:
        self.base_handler = base_handler

    def get_statuses(self, date: dt.date) -> List[Tweet]:
        dirname = "statuses"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        # 同じ日付のファイルが複数ある場合は統合する
        file_list = self.base_handler.list_path(dirname)
        target_files = [
            f_path for f_path in file_list if f"{dirname}/{date_str}" in f_path
        ]
        results = []
        for f_path in target_files:
            statuses_dict = self.base_handler.load_dict(f_path)
            results += statuses_dict["results"]
        tweets = Tweet.from_responses_v1(results)
        return tweets

    def save_statuses(self, statuses: JsonObj, date: dt.date) -> None:
        dirname = "statuses"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        # 既存のファイルとの互換性のため "results" キーでラッピングする。
        statuses_dict = {"results": statuses}

        filename = f"{date_str}_1.json"
        self.base_handler.save_dict(statuses_dict, f"{dirname}/{filename}")
        return

    def get_statuses_dq(self, date: dt.date) -> List[Tweet]:
        dirname = "statuses_dq"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        filename = f"{date_str}.json"
        raw_statuses = self.base_handler.load_dict(f"{dirname}/{filename}")
        tweets = Tweet.from_responses_v1(raw_statuses)
        return tweets

    def save_statuses_dq(self, statuses: JsonObj, date: dt.date) -> None:
        dirname = "statuses_dq"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        filename = f"{date_str}.json"
        self.base_handler.save_dict(statuses, f"{dirname}/{filename}")
        return

    def get_members(self) -> List[User]:
        dirname = "member"
        filename = "member.json"
        members_dict = self.base_handler.load_dict(f"{dirname}/{filename}")
        return User.from_responses_v1(members_dict["users"])

    def save_members(self, members: JsonObj) -> None:
        dirname = "member"
        filename = "member.json"

        # 既存のファイルとの互換性のため "users" キーでラッピングする。
        members_dict = {"users": members}

        self.base_handler.save_dict(members_dict, f"{dirname}/{filename}")
        return

    def get_rating_info(self, date: dt.date) -> Dict[str, Any]:
        dirname = "rating_info"
        date_str = date.strftime("%Y%m%d")  # like 20200101
        filename = f"{date_str}.json"
        rating_info = self.base_handler.load_dict(f"{dirname}/{filename}")
        return rating_info

    def save_rating_info(self, rating_info: Dict, date: dt.date) -> None:
        dirname = "rating_info"
        date_str = date.strftime("%Y%m%d")  # like 20200101
        filename = f"{date_str}.json"
        self.base_handler.save_dict(rating_info, f"{dirname}/{filename}")
        return


class IOHandlerV2(object):
    def __init__(self, base_handler: IOBaseHandler) -> None:
        self.base_handler = base_handler

    def get_statuses(self, date: dt.date) -> List[Tweet]:
        dirname = "statuses_v2"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        # 同じ日付のファイルが複数ある場合は統合する
        file_list = self.base_handler.list_path(dirname)
        target_files = [
            f_path for f_path in file_list if f"{dirname}/{date_str}" in f_path
        ]
        data = []
        users = []
        for f_path in target_files:
            statuses_dict = self.base_handler.load_dict(f_path)
            data += statuses_dict["data"]
            users += statuses_dict["includes"].get("users", [])
        data_objs = [tweepy.Tweet(t) for t in statuses_dict["data"]]
        users_objs = [
            tweepy.User(u) for u in statuses_dict["includes"].get("users", [])
        ]
        tweets = Tweet.from_responses_v2(data_objs, users_objs)
        return tweets

    def save_statuses(self, all_info_dict: JsonObj, date: dt.date) -> None:
        dirname = "statuses_v2"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        # TODO: convert datetime to string

        filename = f"{date_str}_1.json"
        self.base_handler.save_dict(all_info_dict, f"{dirname}/{filename}")
        return

    def get_statuses_dq(self, date: dt.date) -> List[Tweet]:
        dirname = "statuses_dq_v2"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        filename = f"{date_str}.json"
        statuses_dict = self.base_handler.load_dict(f"{dirname}/{filename}")
        data_objs = [tweepy.Tweet(t) for t in statuses_dict["data"]]
        users_objs = [
            tweepy.User(u) for u in statuses_dict["includes"].get("users", [])
        ]
        tweets = Tweet.from_responses_v2(data_objs, users_objs)
        return tweets

    def save_statuses_dq(self, all_info_dict: JsonObj, date: dt.date) -> None:
        dirname = "statuses_dq_v2"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        # TODO: convert datetime to string

        filename = f"{date_str}.json"
        self.base_handler.save_dict(all_info_dict, f"{dirname}/{filename}")
        return

    def get_members(self) -> List[User]:
        dirname = "member_v2"
        filename = "member.json"
        members_dict = self.base_handler.load_dict(f"{dirname}/{filename}")
        user_objs = [tweepy.User(u) for u in members_dict["data"]]
        return User.from_responses_v2(user_objs)

    def save_members(self, members: JsonObj) -> None:
        dirname = "member_v2"
        filename = "member.json"

        self.base_handler.save_dict(members, f"{dirname}/{filename}")
        return

    def get_rating_info(self, date: dt.date) -> Dict[str, Any]:
        dirname = "rating_info"
        date_str = date.strftime("%Y%m%d")  # like 20200101
        filename = f"{date_str}.json"
        rating_info = self.base_handler.load_dict(f"{dirname}/{filename}")
        return rating_info

    def save_rating_info(self, rating_info: Dict, date: dt.date) -> None:
        dirname = "rating_info"
        date_str = date.strftime("%Y%m%d")  # like 20200101
        filename = f"{date_str}.json"
        self.base_handler.save_dict(rating_info, f"{dirname}/{filename}")
        return