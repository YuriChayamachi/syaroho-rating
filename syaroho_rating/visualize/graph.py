import datetime as dt
from pathlib import Path
from typing import Dict, List

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pendulum
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import FuncFormatter

from syaroho_rating.consts import graph_colors, month_name
from syaroho_rating.utils import classes, colors

fp = FontProperties(
    fname="syaroho_rating/font/NotoSansCJK-Regular.ttc",
    size=14,
)


class GraphMaker(object):
    save_dir = Path("graph")

    def __init__(self, rating_history: Dict):
        # self.history_data[usr_name]["rate_hist"] = [rate1, ...]
        # self.history_data[usr_name]["attend_date"] = [date1, ...]
        self.rating_history = rating_history

    def draw_graph_and_save(self, user_name) -> Path:
        attend_dates = [
            dt.datetime.strptime(d, "%Y/%m/%d")
            for d in self.rating_history[user_name]["attend_date"]
        ]
        ratings = self.rating_history[user_name]["rate_hist"]

        save_path = self.get_savepath(user_name)
        self.save_dir.mkdir(exist_ok=True)

        self._draw_graph_and_save(ratings, attend_dates, user_name, save_path)
        return

    def _draw_graph_and_save(self, rate_hist, attend_dates, user_name, save_path):
        first_date, last_date = min(attend_dates), max(attend_dates)
        lowest_rate, highest_rate, = (
            min(rate_hist),
            max(rate_hist),
        )

        fig, ax = plt.subplots()
        x_start = dt.datetime(2018, 12, 31)
        x_min = max(x_start, first_date - dt.timedelta(days=3))
        x_max = last_date + dt.timedelta(days=3)
        plt.xlim(x_min, x_max)

        ymarks = [i for i in range(0, 3200, 200)]
        plt.yticks(ymarks)

        y_min = max(200, lowest_rate) - 200
        y_max = max(500, highest_rate + max((highest_rate - lowest_rate) * 0.125, 200))
        plt.ylim(y_min, y_max)

        # set graph bg color
        for color, low_rate, high_rate in graph_colors:
            plt.axhspan(low_rate, high_rate, color=color, alpha=0.3)

        markercolor = list(map(lambda x: colors(x), rate_hist))
        plt.plot(attend_dates, rate_hist, alpha=1.0, color="#666666", zorder=1)
        plt.scatter(
            attend_dates,
            rate_hist,
            s=60,
            alpha=1.0,
            marker=".",
            color=markercolor,
            linewidths=0.8,
            edgecolors="#666666",
            zorder=2,
        )
        plt.ylabel("Rating", fontsize=12)

        header1 = " しゃろほー" + classes(highest_rate) + "  " + user_name
        header2 = "(Rating: " + str(rate_hist[-1]) + ") "
        highest = "Highest: " + str(highest_rate)
        x_high = attend_dates[rate_hist.index(highest_rate)]
        y_high = (highest_rate + y_max) / 2
        month_delta = (last_date.year - first_date.year) * 12 + (
            last_date.month - first_date.month
        )
        day_delta = (x_max - x_min).days
        high_day_delta = (x_high - x_min).days

        if high_day_delta * 2 >= day_delta:
            ha = "right"
        else:
            ha = "left"

        bbox = dict(boxstyle="square", ec="#999999", fc="#FFFFFF", alpha=0.7)
        arrowprops = dict(
            arrowstyle="-", relpos=(0.5, 0.05), edgecolor="#999999", alpha=0.7
        )
        plt.annotate(
            highest,
            xy=(x_high, highest_rate),
            xytext=(x_high, y_high),
            bbox=bbox,
            ha=ha,
            fontsize=10,
            arrowprops=arrowprops,
        )
        plt.title(header1, loc="left", color=colors(rate_hist[-1]), fontproperties=fp)
        plt.title(header2, fontsize=12, loc="right")

        if month_delta >= 12:
            months = mdates.MonthLocator()
            ax.xaxis.set_major_locator(months)

            def dateFormatter(x, pos):
                dt_ = mdates.num2date(x)
                # x_min と比較するため timezone 情報を落とす
                dt_ = pendulum.parse(str(dt_)).naive()
                month = (
                    month_name[dt_.month - 1]
                    if (
                        ((dt_.month % 3) == 1)
                        or ((dt_.month == x_min.month + 1) and (dt_.year == x_min.year))
                    )
                    else ""
                )
                year = (
                    (str(dt_.year)[2:4] + "'")
                    if (
                        (dt_.month == 1)
                        or ((dt_.month == x_min.month + 1) and (dt_.year == x_min.year))
                    )
                    else ""
                )
                return "{0}\n{1}".format(month, year)

        elif month_delta >= 2:
            months = mdates.MonthLocator()
            ax.xaxis.set_major_locator(months)

            def dateFormatter(x, pos):
                dt_ = mdates.num2date(x)
                # x_min と比較するため timezone 情報を落とす
                dt_ = pendulum.parse(str(dt_)).naive()
                month = month_name[dt_.month - 1]
                year = (
                    (str(dt_.year)[2:4] + "'")
                    if (
                        (dt_.month == 1)
                        or ((dt_.month == x_min.month + 1) and (dt_.year == x_min.year))
                    )
                    else ""
                )
                return "{0}\n{1}".format(month, year)

        else:
            days = mdates.DayLocator()
            ax.xaxis.set_major_locator(days)

            def dateFormatter(x, pos):
                dt_ = mdates.num2date(x)
                # x_min と比較するため timezone 情報を落とす
                dt_ = pendulum.parse(str(dt_)).naive()
                interval = 5 if (day_delta > 10) else 1
                day = (
                    dt_.day
                    if (
                        ((dt_.day - 1) % interval == 0)
                        and ((dt_ + dt.timedelta(days=interval - 1)).month == dt_.month)
                    )
                    else ""
                )
                month = (
                    month_name[dt_.month - 1]
                    if (
                        ((dt_.day == 1) or ((dt_ - x_min).days <= (interval - 1)))
                        and (day != "")
                    )
                    else ""
                )
                return "{0}\n{1}".format(day, month)

        formatter = FuncFormatter(dateFormatter)
        ax.xaxis.set_major_formatter(formatter)

        plt.savefig(str(save_path))
        plt.close(fig)
        return

    def draw_graph_users(self, user_names: List[str]) -> List[Path]:
        for user_name in user_names:
            self.draw_graph_and_save(user_name)
        return

    @classmethod
    def get_savepath(cls, username: str) -> Path:
        fname = f"{username}.png"
        save_path = cls.save_dir / fname
        return save_path
