import datetime as dt
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pendulum

from syaroho_rating.utils import perf_to_color


def get_colorlist(performances: pd.Series, n_col: int) -> np.ndarray:
    colordefs = []
    for p in performances:
        rgb = (3.0 + perf_to_color(p)) / 4.0  # type: np.ndarray
        colordef_row = np.tile(rgb, reps=(n_col, 1))
        colordefs.append(colordef_row)
    return np.stack(colordefs)


class TableMaker(object):

    save_dir = Path("result_table")

    def __init__(self, data: pd.DataFrame, date: dt.date):
        self.data = data
        self.date = date
        self.header = self._make_header()

    def _make_header(self) -> str:
        return "SYAROHO RESULT " + self.date.strftime("(%Y/%m/%d)")

    def _make_and_save(self, df: pd.DataFrame, save_path: Path) -> None:
        df_ = df.set_index("Rank")

        fig, ax = plt.subplots(
            figsize=((len(df_.columns) + 1) * 3, (len(df_) + 1) * 0.7)
        )
        fig.subplots_adjust(
            left=0.15, bottom=0.025, right=0.95, top=0.95, wspace=0.15, hspace=0.15
        )
        ax.axis("off")
        colorlist = get_colorlist(df["Perf."], len(df.columns) - 1)
        tbl = ax.table(
            cellText=df_.values,
            colLabels=df_.columns,
            rowLabels=df_.index,
            bbox=[0, 0, 1, 0.99],
            cellLoc="left",
            cellColours=colorlist,
            colWidths=[0.3, 0.25, 0.125, 0.125, 0.125],
            loc="center",
        )
        tbl.set_fontsize(40)

        plt.title(self.header, fontsize=30)
        plt.savefig(str(save_path))
        plt.close("all")

        return

    def make(self) -> List[Path]:
        # 結果を50人ごと分割する
        per_page = 50
        filenames = []
        self.save_dir.mkdir(exist_ok=True)
        for i, c in enumerate(range(0, len(self.data), per_page)):
            save_path = self.save_dir / f"{self.date.isoformat()}_{i}.png"
            self._make_and_save(self.data.iloc[c : c + per_page], save_path)
            filenames.append(save_path)
        return filenames


if __name__ == "__main__":
    # test
    # dummy performances
    data = [
        {"Perf": 200},
        {"Perf": 1000},
        {"Perf": 1300},
        {"Perf": 2000},
    ]
    df = pd.DataFrame(data)
    out = get_colorlist(df["Perf"], 4)

    import random
    import string

    def get_random_string(length: int) -> str:
        letters = string.ascii_lowercase
        result_str = "".join(random.choice(letters) for i in range(length))
        return result_str

    def generate_random_time() -> str:
        time = pendulum.datetime(2020, 1, 1).start_of("day")
        return time.add(microseconds=random.randint(-999999, 999999)).strftime(
            "%H:%M:%S.%f"
        )[:-3]

    def generate_dummy_data(i: int) -> Dict[str, Any]:
        return {
            "Rank": i,
            "Name": get_random_string(8),
            "Record": generate_random_time(),
            "Perf.": random.randint(0, 3200),
            "Rating": random.randint(0, 3200),
            "Change": random.randint(-1000, 1000),
        }

    # dummy data
    dummy_df = pd.DataFrame([generate_dummy_data(x) for x in range(120)])
    # files = TableMaker(dummy_df, "sample_header", dt.date(2020, 12, 31)).make()
    # print(files)
