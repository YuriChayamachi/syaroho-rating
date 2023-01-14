import datetime as dt
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from syaroho_rating.utils import perf_to_color


def get_colorlist(performances: pd.Series, n_col: int) -> np.ndarray:
    colordefs = []
    for p in performances:
        rgb = (3.0 + perf_to_color(p)) / 4.0  # type: np.ndarray
        colordef_row = np.tile(rgb, reps=(n_col, 1))
        colordefs.append(colordef_row)
    return np.stack(colordefs)


class SummaryTableMaker(object):

    save_dir = Path("rating_summary_table")
    max_page = 4
    per_page = 25

    def __init__(
        self,
        summary_df: pd.DataFrame,
        header: str,
        end_date: dt.date,
        start_date: dt.date = dt.date(2019, 1, 1),
    ):
        self.summary_df = summary_df
        self.header = header
        self.start_date = start_date
        self.end_date = end_date

    def make(self) -> List[Path]:
        filenames = []
        self.save_dir.mkdir(exist_ok=True)
        num_pages = min(self.max_page, len(self.summary_df) // self.per_page + 1)
        for i, c in enumerate(range(0, num_pages, self.per_page)):
            save_path = self.save_dir / f"{self.end_date.isoformat()}_{i}.png"
            self._make_and_save(self.summary_df.iloc[c : c + self.per_page], save_path)
            filenames.append(save_path)
        return filenames

    def _make_and_save(self, df_w: pd.DataFrame, save_path: Path):

        # 表の背景色の設定
        colorlists = get_colorlist(df_w["Rating"], n_col=5)

        # 画像の作成
        fig, ax = plt.subplots(
            figsize=((len(df_w.columns) + 1) * 3, (len(df_w) + 1) * 0.7)
        )
        fig.subplots_adjust(
            left=0.100, bottom=0.05, right=0.95, top=0.95, wspace=0.00, hspace=0.05
        )
        ax.axis("off")
        tbl = ax.table(
            cellText=df_w.values,
            colLabels=df_w.columns,
            rowLabels=df_w.index,
            bbox=[0, 0, 1, 0.99],
            cellLoc="right",
            cellColours=colorlists,
            colWidths=[0.225, 0.1, 0.1, 0.1, 0.2],
            loc="center",
        )
        tbl.set_fontsize(40)
        header = (
            "SYAROHO RANKING ("
            + self.start_date.strftime("%Y/%m/%d")
            + " - "
            + self.end_date.strftime("%Y/%m/%d")
            + ")"
        )
        plt.title(header, fontsize=40)

        # 保存
        plt.savefig(save_path)
        plt.close("all")
        return
