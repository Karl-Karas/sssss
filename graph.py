import json
import math
from sqlite3 import Connection
from typing import Union, List, Tuple, Dict, Optional

import numpy as np
import pandas as pd
import plotly
import plotly.express as px

from db import get_success_failure_by_player, get_critical_by_player, get_nimdir_index_by_player, get_formula_usage, \
    get_energy_usage, get_base_dices, get_count_by_player


def _histogram_data(bounded_data: List[Union[float, int]]) -> Tuple[List[int], List[Union[float, int]]]:
    counts = []
    bin_edges = []
    bounded_data = sorted(bounded_data)
    for i in range(len(bounded_data)):
        if len(bin_edges) != 0 and bin_edges[-1] == bounded_data[i]:
            counts[-1] += 1
        else:
            counts.append(1)
            bin_edges.append(bounded_data[i])
    return counts, bin_edges


def cdf_data(cdf_values: List[Union[float, int]], shadow_points_from: List[Union[int, float]] = ()) \
        -> Tuple[List[Union[float, int]], List[float]]:
    data = sorted(cdf_values)

    # Count and filter math.inf
    bounded_data = [value for value in data if value != math.inf]
    if len(bounded_data) == 0:  # Every demand file was failed
        return [], []

    counts, bin_edges = _histogram_data(bounded_data)
    cdf = np.cumsum(counts)

    cdf = (cdf / cdf[-1]) * (len(bounded_data) / len(data))  # Unsolved instances hurts the cdf
    bin_edges = list(bin_edges)
    bin_edges.insert(0, 0)
    cdf = list(cdf)
    cdf.insert(0, 0)

    new_bin_edges = []
    new_cdf = []
    current_bin_idx = 0
    for to_add in shadow_points_from:
        for i in range(current_bin_idx, len(bin_edges)):
            if to_add == bin_edges[i]:
                # Everything ok up to to_add
                new_bin_edges.append(to_add)
                new_cdf.append(cdf[i])
                current_bin_idx = i + 1
                break
            elif to_add < bin_edges[i]:
                # Create new point
                new_bin_edges.append(to_add)
                new_cdf.append(new_cdf[-1])
                break
            else:
                # Use old point
                new_bin_edges.append(bin_edges[i])
                new_cdf.append(cdf[i])
        if current_bin_idx == len(bin_edges) and new_bin_edges[-1] != to_add:
            # to_add is beyond the current range of bins
            new_bin_edges.append(to_add)
            new_cdf.append(new_cdf[-1])

    return (bin_edges, cdf) if len(shadow_points_from) == 0 else (new_bin_edges, new_cdf)


def grouped_chart(data: Dict[str, Tuple[float, float]], categories: List[str], colors: List[str],
                  group_title: str, y_label: str) -> str:
    """Returns a group chart from data of the form {'player1': (data1, data2)} in a json string"""

    df_source = {"Players": [], categories[0]: [], categories[1]: []}
    for player, value in data.items():
        df_source["Players"].append(player.split(" ")[0])
        df_source[categories[0]].append(value[0])
        df_source[categories[1]].append(value[1])
    df = pd.DataFrame.from_dict(df_source)
    df = pd.melt(df, id_vars=["Players"], var_name=group_title, value_name=y_label)

    plot = px.bar(df, x="Players", color=group_title, y=y_label, barmode="group", color_discrete_sequence=colors)
    return json.dumps(plot, cls=plotly.utils.PlotlyJSONEncoder)


def success_failure_by_player(db: Connection, campaign: str, player: Optional[str] = None,
                              test: Optional[str] = None) -> str:
    """Returns a bar plot showing success and failures percentage by player in a json string"""

    data = get_success_failure_by_player(db, campaign, player, test)
    return grouped_chart(data, ["Success Rate", "Failure Rate"], ["darkgreen", "tomato"], "Rate", "%")


def critical_by_player(db: Connection, campaign: str, player: Optional[str] = None, test: Optional[str] = None) -> str:
    """Returns a bar plot showing critical success and failures by player in a json string"""

    data = get_critical_by_player(db, campaign, player, test)
    return grouped_chart(data, ["Critical Successes", "Critical Failures"], ["darkgreen", "tomato"], "Type", "Count")


def nimdir_index_by_player(db: Connection, campaign: str, player: Optional[str] = None,
                           test: Optional[str] = None) -> str:
    """
    Returns a bar plot showing the maximum length of streaks of successes and failures by player in a json string
    """

    data = get_nimdir_index_by_player(db, campaign, player, test)
    return grouped_chart(data, ["Success Streak", "Failure Streak"], ["darkgreen", "tomato"], "Type", "Streak")


def base_dice_distributions(db: Connection, campaign: str, player: Optional[str] = None,
                            test: Optional[str] = None) -> str:
    """
    Returns a cdf of the distribution of the 2 base dices for each player
    (as well as the theoretical distribution)
    """
    data = get_base_dices(db, campaign, player, test)
    reference = "Reference"

    # Regular distribution
    for i in range(1, 7):
        for j in range(1, 7):
            data.setdefault(reference, []).append(i + j)

    # Produce DataFrame
    df_source: Dict[str, List[Union[int, float]]] = {"Sum of 2d6": [i for i in range(2, 13)]}
    df_source["Sum of 2d6"].insert(0, 0)
    reference_cdf = []
    for name, sums in sorted(list(data.items())):
        x, cdf = cdf_data(sums, shadow_points_from=df_source["Sum of 2d6"])
        if name == reference:
            reference_cdf = cdf
        df_source.setdefault(name.split(" ")[0], []).extend(cdf)
    df = pd.DataFrame.from_dict(df_source)
    df = pd.melt(df, id_vars=["Sum of 2d6"], var_name="Players", value_name="CDF")

    plot = px.line(df, x="Sum of 2d6", color="Players", y="CDF", line_shape="hv", range_x=[2, 12], range_y=[0, 1],
                   color_discrete_sequence=px.colors.qualitative.Alphabet)
    plot.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=1),
                       yaxis=dict(tickmode='array', tickvals=reference_cdf,
                                  ticktext=[f"{tick:.2f}" for tick in reference_cdf]))
    return json.dumps(plot, cls=plotly.utils.PlotlyJSONEncoder)


def formula_usage(db: Connection, campaign: str, player: Optional[str] = None, test: Optional[str] = None) -> str:
    """
    Returns a bar plot showing the usage of each formula element
    """

    data = get_formula_usage(db, campaign, player, test)

    df_source = {"Formula element": [], "Usage Count": []}
    for key, value in data.items():
        df_source["Formula element"].append(key)
        df_source["Usage Count"].append(value)
    df = pd.DataFrame.from_dict(df_source)
    plot = px.bar(df, x="Formula element", y="Usage Count", color_discrete_sequence=["black"])
    return json.dumps(plot, cls=plotly.utils.PlotlyJSONEncoder)


def energy_usage(db: Connection, campaign: str, player: Optional[str] = None, test: Optional[str] = None) -> str:
    """
    Returns a bar plot showing the usage of each energy
    """

    data = get_energy_usage(db, campaign, player, test)

    df_source = {"Energies": [], "Usage Count": []}
    for key, value in data.items():
        df_source["Energies"].append(key)
        df_source["Usage Count"].append(value)
    df = pd.DataFrame.from_dict(df_source)
    plot = px.bar(df, x="Energies", y="Usage Count", color_discrete_sequence=["black"])
    return json.dumps(plot, cls=plotly.utils.PlotlyJSONEncoder)


def roll_count(db: Connection, campaign: str, player: Optional[str] = None, test: Optional[str] = None) -> str:
    """
    Returns a bar plot showing the usage of each energy
    """

    data = get_count_by_player(db, campaign, player, test)

    df_source = {"Players": [], "Number of rolls": []}
    for key, value in data.items():
        df_source["Players"].append(key.split(" ")[0])
        df_source["Number of rolls"].append(value)
    df = pd.DataFrame.from_dict(df_source)
    plot = px.bar(df, x="Players", y="Number of rolls", color_discrete_sequence=["black"])
    return json.dumps(plot, cls=plotly.utils.PlotlyJSONEncoder)
