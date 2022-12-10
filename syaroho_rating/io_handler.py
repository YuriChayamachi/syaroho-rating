import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Union

import boto3
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

from syaroho_rating.consts import S3_BUCKET_NAME, STORAGE
from syaroho_rating.model import Tweet


def get_io_handler() -> "IOHandlerBase":

    if STORAGE == "s3":
        return S3IOHandler()
    elif STORAGE == "local":
        return LocalIOHandler()
    else:
        raise RuntimeError(f"Unexpected STORAGE variable: {STORAGE}")


class IOHandlerBase(object):

    ###################
    # base operations #
    ###################

    def save_dict(self, dict_obj: Union[Dict, List], relative_path: str) -> None:
        raise NotImplementedError

    def load_dict(self, relative_path: str) -> Any:
        raise NotImplementedError

    def delete(self, relative_path: str) -> None:
        raise NotImplementedError

    def list_path(self, relative_path: str) -> List[Any]:
        raise NotImplementedError

    #######################
    # concrete operations #
    #######################

    def get_statuses_v1(self, date: dt.date) -> List[Tweet]:
        dirname = "statuses"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        # 同じ日付のファイルが複数ある場合は統合する
        file_list = self.list_path(dirname)
        target_files = [
            f_path for f_path in file_list if f"{dirname}/{date_str}" in f_path
        ]
        results = []
        for f_path in target_files:
            statuses_dict = self.load_dict(f_path)
            results += statuses_dict["results"]
        tweets = Tweet.from_responses_v1(results)
        return tweets

    def save_statuses(self, statuses: List, date: dt.date) -> None:
        dirname = "statuses"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        # 既存のファイルとの互換性のため "results" キーでラッピングする。
        statuses_dict = {"results": statuses}

        filename = f"{date_str}_1.json"
        self.save_dict(statuses_dict, f"{dirname}/{filename}")
        return

    def get_statuses_dq_v1(self, date: dt.date) -> List[Tweet]:
        dirname = "statuses_dq"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        filename = f"{date_str}.json"
        raw_statuses = self.load_dict(f"{dirname}/{filename}")
        tweets = Tweet.from_responses_v1(raw_statuses)
        return tweets

    def save_statuses_dq(self, statuses: List, date: dt.date) -> None:
        dirname = "statuses_dq"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        filename = f"{date_str}.json"
        self.save_dict(statuses, f"{dirname}/{filename}")
        return

    def get_members_v1(self) -> List[Dict[str, Any]]:
        dirname = "member"
        filename = "member.json"
        members_dict = self.load_dict(f"{dirname}/{filename}")
        return members_dict["users"]

    def save_members(self, members: List) -> None:
        dirname = "member"
        filename = "member.json"

        # 既存のファイルとの互換性のため "users" キーでラッピングする。
        members_dict = {"users": members}

        self.save_dict(members_dict, f"{dirname}/{filename}")
        return

    def get_rating_info(self, date: dt.date) -> Dict[str, Any]:
        dirname = "rating_info"
        date_str = date.strftime("%Y%m%d")  # like 20200101
        filename = f"{date_str}.json"
        rating_info = self.load_dict(f"{dirname}/{filename}")
        return rating_info

    def save_rating_info(self, rating_info: Dict, date: dt.date) -> None:
        dirname = "rating_info"
        date_str = date.strftime("%Y%m%d")  # like 20200101
        filename = f"{date_str}.json"
        self.save_dict(rating_info, f"{dirname}/{filename}")
        return


class S3IOHandler(IOHandlerBase):
    temp_dir = Path("temp")

    def __init__(self) -> None:
        super().__init__()
        self.s3 = boto3.client("s3")
        self.temp_dir.mkdir(exist_ok=True)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5)
    )
    def save_dict(self, dict_obj: Union[Dict, List], relative_path: str) -> None:
        temp_path = self.temp_dir / f"{uuid.uuid4()}.json"
        with temp_path.open("w") as f:
            json.dump(dict_obj, f, indent=4, ensure_ascii=False)
        with temp_path.open("rb") as f:
            self.s3.upload_fileobj(f, S3_BUCKET_NAME, relative_path)
        temp_path.unlink(missing_ok=True)
        return

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5)
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
        wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5)
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


class LocalIOHandler(IOHandlerBase):
    def __init__(self, base_path: Path = Path("data")):
        super().__init__()
        self.base_path = base_path
        self.base_path.mkdir(exist_ok=True)

    def save_dict(self, dict_obj: Union[Dict, List], relative_path: str) -> None:
        file_path = self.base_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w") as f:
            json.dump(dict_obj, f, indent=4, ensure_ascii=False)
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
