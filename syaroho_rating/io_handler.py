import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Dict, List, Union

import boto3
from botocore.exceptions import ClientError

from syaroho_rating.consts import S3_BUCKET_NAME


class IOHandlerBase(object):

    ###################
    # base operations #
    ###################

    def save_dict(self, dict_obj: Union[Dict, List], relative_path: str):
        raise NotImplementedError

    def load_dict(self, relative_path: str):
        raise NotImplementedError

    def delete(self, relative_path: str):
        raise NotImplementedError

    def list_path(self, relative_path: str):
        raise NotImplementedError

    #######################
    # concrete operations #
    #######################

    def get_statuses(self, date: dt.date):
        dirname = "statuses"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        # 同じ日付のファイルが複数ある場合は統合する
        file_list = self.list_path(dirname)
        target_files = [f_path for f_path in file_list if date_str in f_path]
        results = []
        for f_path in target_files:
            statuses_dict = self.load_dict(f_path)
            results += statuses_dict["results"]
        return results

    def save_statuses(self, statuses: List, date: dt.date):
        dirname = "statuses"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        # 既存のファイルとの互換性のため "results" キーでラッピングする。
        statuses_dict = {"results": statuses}

        filename = f"{date_str}_1.json"
        self.save_dict(statuses_dict, f"{dirname}/{filename}")
        return

    def get_statuses_dq(self, date: dt.date):
        dirname = "statuses_dq"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        filename = f"{date_str}.json"
        statuses = self.load_dict(f"{dirname}/{filename}")
        return statuses

    def save_statuses_dq(self, statuses: List, date: dt.date):
        dirname = "statuses_dq"
        date_str = date.strftime("%Y%m%d")  # like 20200101

        filename = f"{date_str}.json"
        self.save_dict(statuses, f"{dirname}/{filename}")
        return

    def get_members(self):
        dirname = "member"
        filename = "member.json"
        members_dict = self.load_dict(f"{dirname}/{filename}")
        return members_dict["users"]

    def save_members(self, members: List):
        dirname = "member"
        filename = "member.json"

        # 既存のファイルとの互換性のため "users" キーでラッピングする。
        members_dict = {"users": members}

        self.save_dict(members_dict, f"{dirname}/{filename}")
        return

    def get_rating_info(self, date: dt.date):
        dirname = "rating_info"
        date_str = date.strftime("%Y%m%d")  # like 20200101
        filename = f"{date_str}.json"
        rating_info = self.load_dict(f"{dirname}/{filename}")
        return rating_info

    def save_rating_info(self, rating_info: Dict, date: dt.date):
        dirname = "rating_info"
        date_str = date.strftime("%Y%m%d")  # like 20200101
        filename = f"{date_str}.json"
        self.save_dict(rating_info, f"{dirname}/{filename}")
        return


class S3IOHandler(IOHandlerBase):
    temp_dir = Path("temp")

    def __init__(self):
        super().__init__()
        self.s3 = boto3.client("s3")
        self.temp_dir.mkdir(exist_ok=True)

    def save_dict(self, dict_obj: Union[Dict, List], relative_path: str):
        temp_path = self.temp_dir / f"{uuid.uuid4()}.json"
        with temp_path.open("w") as f:
            json.dump(dict_obj, f, indent=4, ensure_ascii=False)
        with temp_path.open("rb") as f:
            self.s3.upload_fileobj(f, S3_BUCKET_NAME, relative_path)
        temp_path.unlink(missing_ok=True)
        return

    def load_dict(self, relative_path: str):
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

    def delete(self, relative_path: str):
        raise NotImplementedError

    def list_path(self, relative_path: str):
        """バケットルートからの相対パスのリストを返す"""
        res = self.s3.list_objects(Bucket=S3_BUCKET_NAME, Prefix=relative_path)
        obj_list = [c["Key"] for c in res.get("Contents", [])]
        return obj_list


class LocalIOHandler(IOHandlerBase):
    base_path = Path("data")

    def __init__(self):
        super().__init__()
        self.base_path.mkdir(exist_ok=True)

    def save_dict(self, dict_obj: Union[Dict, List], relative_path: str):
        file_path = self.base_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w") as f:
            json.dump(dict_obj, f, indent=4, ensure_ascii=False)
        return

    def load_dict(self, relative_path: str):
        file_path = self.base_path / relative_path
        with file_path.open() as f:
            dict_obj = json.load(f)
        return dict_obj

    def delete(self, relative_path: str):
        pass

    def list_path(self, relative_path: str):
        """base path からの相対パスのリストを返す"""
        dir_path = self.base_path / relative_path
        obj_list = [str(p.relative_to(self.base_path)) for p in dir_path.iterdir()]
        return obj_list
