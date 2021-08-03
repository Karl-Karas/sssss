import math
from io import StringIO
from sqlite3 import Connection
from typing import Union, List, Tuple

import matplotlib as mpl
import numpy as np
from matplotlib.axes import Subplot
from matplotlib.ticker import FormatStrFormatter

mpl.use('svg')
import matplotlib.pyplot as plt
from matplotlib.pyplot import Figure

from db import get_success_failure_by_player, get_critical_by_player, get_nimdir_index_by_player, get_formula_usage, \
    get_energy_usage, get_base_dices

FONTSIZE = 14

def get_svg(fig: Figure) -> str:
    svg = StringIO()
    fig.tight_layout()
    fig.savefig(svg, format='svg')
    svg.seek(0)
    return svg.read()

def common_settings(subplot: Subplot, integer: bool = True, labels: bool = True, xlabel: str = "Players") -> None:
    if labels:
        subplot.legend(loc="best")
    if integer:
        subplot.yaxis.get_major_locator().set_params(integer=True)
    subplot.set_xlabel(xlabel, fontsize=FONTSIZE)
    subplot.set_ylim(bottom=0)

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

def cdf_data(cdf_values: List[Union[float, int]], origin: bool = True) -> Tuple[List[Union[float, int]], List[float]]:
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
    return bin_edges, cdf

def success_failure_by_player(db: Connection, campaign: str) -> str:
    """Returns a bar plot showing success and failures percentage by player in a the svg encoded as a string"""

    data = get_success_failure_by_player(db, campaign)

    fig = plt.figure()
    fig.tight_layout()
    subplot = fig.add_subplot(111)

    # Data
    players = sorted(list(data.keys()))
    x = np.arange(len(players))
    width = 0.35
    subplot.bar(x - width / 2, [data[player][0] for player in players], width, color="darkgreen", label="Success rate")
    subplot.bar(x + width / 2, [data[player][1] for player in players], width, color="tomato", label="Failure rate")

    # Parameters
    subplot.set_ylabel("% of rolls")
    subplot.set_yticks([0, 25, 50, 75, 100])
    subplot.set_xticks(x)
    subplot.set_xticklabels([p.split(" ")[0] for p in players], rotation=45)
    common_settings(subplot, False)

    return get_svg(fig)

def critical_by_player(db: Connection, campaign: str) -> str:
    """Returns a bar plot showing critical success and failures by player in a the svg encoded as a string"""

    data = get_critical_by_player(db, campaign)

    fig = plt.figure()
    fig.tight_layout()
    subplot = fig.add_subplot(111)

    # Data
    players = sorted(list(data.keys()))
    x = np.arange(len(players))
    width = 0.35
    subplot.bar(x - width / 2, [data[player][0] for player in players], width, color="darkgreen",
                label="Critical successes")
    subplot.bar(x + width / 2, [data[player][1] for player in players], width, color="tomato",
                label="Critical failures")

    # Parameters
    subplot.set_ylabel("Number of rolls")
    subplot.set_xticks(x)
    subplot.set_xticklabels([p.split(" ")[0] for p in players], rotation=45)
    common_settings(subplot)

    return get_svg(fig)

def nimdir_index_by_player(db: Connection, campaign: str) -> str:
    """
    Returns a bar plot showing the maximum length of streaks of successes and failures by player in a the svg
    encoded as a string
    """

    data = get_nimdir_index_by_player(db, campaign)

    fig = plt.figure()
    fig.tight_layout()
    subplot = fig.add_subplot(111)

    # Data
    players = sorted(list(data.keys()))
    x = np.arange(len(players))
    width = 0.35
    subplot.bar(x - width / 2, [data[player][0] for player in players], width, color="darkgreen",
                label="Streak of successes")
    subplot.bar(x + width / 2, [data[player][1] for player in players], width, color="tomato",
                label="Streak of failures")

    # Parameters
    subplot.set_ylabel("Number of rolls")
    subplot.set_xticks(x)
    subplot.set_xticklabels([p.split(" ")[0] for p in players], rotation=45)
    common_settings(subplot)

    return get_svg(fig)

def base_dice_distributions(db: Connection, campaign: str) -> str:
    """
    Returns a cdf of the distribution of the 2 base dices for each player
    (as well as the theoretical distribution)
    """
    data = get_base_dices(db, campaign)
    reference = "Reference"

    # Regular distribution
    for i in range(1, 7):
        for j in range(1, 7):
            data.setdefault(reference, []).append(i + j)

    fig = plt.figure()
    fig.tight_layout()
    subplot = fig.add_subplot(111)

    # Data
    reference_cdf = []
    for name, sums in data.items():
        x, cdf = cdf_data(sums, origin=False)
        subplot.step(x + [12], cdf + [1], label=name.split(" ")[0], where="post", linewidth=3)
        if name == reference:
            reference_cdf = cdf

    # Parameters
    subplot.set_ylabel("CDF")
    subplot.set_ylim(bottom=0, top=1)
    subplot.set_xlim(left=2, right=12)
    subplot.set_xticks([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    subplot.set_yticks(reference_cdf)
    subplot.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
    subplot.grid()
    common_settings(subplot, xlabel="Sum of 2d6", integer=False)

    return get_svg(fig)

def formula_usage(db: Connection, campaign: str) -> str:
    """
    Returns a bar plot showing the usage of each formula element
    """

    data = get_formula_usage(db, campaign)

    fig = plt.figure()
    fig.tight_layout()
    subplot = fig.add_subplot(111)

    # Data
    elements = sorted(list(data.keys()))
    x = np.arange(len(elements))
    width = 0.35
    subplot.bar(x, [data[element] for element in elements], width, color="black")

    # Parameters
    subplot.set_ylabel("Number of rolls")
    subplot.set_xticks(x)
    subplot.set_xticklabels(elements, rotation=45)
    common_settings(subplot, labels=False, xlabel="Formula element")

    return get_svg(fig)

def energy_usage(db: Connection, campaign: str) -> str:
    """
    Returns a bar plot showing the usage of each energy
    """

    data = get_energy_usage(db, campaign)

    fig = plt.figure()
    fig.tight_layout()
    subplot = fig.add_subplot(111)

    # Data
    elements = sorted(list(data.keys()))
    x = np.arange(len(elements))
    width = 0.35
    subplot.bar(x, [data[element] for element in elements], width, color="black")

    # Parameters
    subplot.set_ylabel("Number of rolls")
    subplot.set_xticks(x)
    subplot.set_xticklabels(elements, rotation=45)
    common_settings(subplot, labels=False, xlabel="Invested energy")

    return get_svg(fig)
