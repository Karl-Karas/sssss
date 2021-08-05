import math
import os
from sqlite3 import DatabaseError, Connection, connect
from typing import Union, List, Dict, Tuple, Optional

integer_fields = ["number", "type", "max_value", "threshold", "margin", "margin_throttle", "talent_level",
                  "base_energy_cost", "critical_increase", "precision", "optional_precision", "power", "optional_power",
                  "magic_power", "speed", "optional_speed", "margin_modifier", "effect_modifier", "under_value",
                  "superpower_modifier", "unease", "expended_charge"]
boolean_fields = ["recording", "critical_success", "critical_failure", "is_magic", "is_power", "incantation",
                  'somatic_component', "material_component", "energy_investment_validated"]
text_fields = ["name", "timestamp", "reason", "effect", "distance", "focus", "duration",
               "black_magic", "magic_resistance", "armor_penalty", "equipment"]
dice_fields = ["base_dices", "critical_dices", "effect_dices", "localisation_dices", "power_dices", "margin_dices",
               "precision_dices"]
ignored_fields = ["labels", "tooltips", "equipment_id"]
formula_field = "formula_elements"
invested_energies = "invested_energies"


def create_db(path: str) -> None:
    with init_db_connection(path) as db:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "db.sql")) as file_obj:
            db.executescript(file_obj.read())


def init_db_connection(path: str) -> Connection:
    db = connect(path)
    # Activate foreign keys
    db.execute("PRAGMA foreign_keys = 1")
    return db


def insert_roll(db: Connection, campaign: str, post_data: Dict[str, Union[List, int, float, str]]) -> None:
    insert_data = [("campaign", campaign)]
    dices = []
    formula = []
    energies = []
    name = None
    timestamp = None
    for key, value in post_data.items():
        if key in integer_fields:
            insert_data.append((key, int(value) if value != "NaN" else None))
        elif key in boolean_fields:
            insert_data.append((key, value == "true"))
        elif key in text_fields:
            if key == "name":
                name = value
            elif key == "timestamp":
                timestamp = value
            insert_data.append((key, value if value is not None and len(value) > 0 else None))
        elif key in dice_fields:
            dices.extend([(key, i, int(dice)) for i, dice in enumerate(value.split(",") if len(value) > 0 else [])])
        elif key == formula_field:
            formula.extend([v for v in (value.split(",") if len(value) > 0 else [])])
        elif key == invested_energies:
            energies.extend([v for v in (value.split(",") if len(value) > 0 else [])])
        elif key not in ignored_fields:
            print(f"Cannot insert '{key}: {value}' into database")

    if len(insert_data) > 0 and len(dices) > 0:
        cur = db.cursor()
        try:
            # Remove old data if any to update
            if name and timestamp:
                cur.execute(f"delete from rolls where campaign=? and name=? and timestamp=?",
                            [campaign, name, timestamp])

            columns = ','.join(['"' + k + '"' for k, _ in insert_data])
            cmd = f"insert into rolls({columns}) values ({','.join(['?' for _ in insert_data])})"
            cur.execute(cmd, [v for k, v in insert_data])
            cur.execute("select max(rowid) from rolls")
            roll_id = cur.fetchone()[0]
            cmd = f'insert into dices(roll, "type", dice_index, dice) values (:roll, :type, :dice_index, :dice)'
            cur.executemany(cmd, [{"roll": roll_id, "type": dice_type, "dice_index": dice_index, "dice": dice}
                                  for dice_type, dice_index, dice in dices])
            if len(formula) > 0:
                cmd = f'insert into formula_elements(roll, element) values (:roll, :element)'
                cur.executemany(cmd, [{"roll": roll_id, "element": element} for element in formula])
            if len(energies) > 0:
                cmd = f'insert into invested_energies(roll, energy) values (:roll, :energy)'
                cur.executemany(cmd, [{"roll": roll_id, "energy": energy} for energy in energies])
        except DatabaseError as e:
            print(f"Cannot insert roll {post_data} in database: {e}")
            raise e
        finally:
            cur.close()
    else:
        print(f"The roll data {post_data} does not contain actual roll")


def get_players(db: Connection, campaign: str) -> List[str]:
    """Return the list of players"""
    cur = db.cursor()
    try:
        cur.execute('select "name" from rolls where campaign=? group by "name"', [campaign])
        return sorted([row[0] for row in cur.fetchall()])
    finally:
        cur.close()


def get_count_by_player(db: Connection, campaign: str, filter_player: Optional[str] = None,
                        filter_test: Optional[str] = None) -> Dict[str, Tuple[float, float]]:
    """Return by player their total number of rolls"""
    counts = {}

    cur = db.cursor()
    params = [campaign]
    if filter_player:
        params.append(filter_player)
    if filter_test:
        params.append(filter_test)
    try:
        cur.execute('select "name",'
                    ' count(rowid)'
                    ' from rolls where campaign=? and threshold > 0'
                    + (' and name=?' if filter_player else '')
                    + (' and reason=?' if filter_test else '')
                    + ' group by "name"', params)
        for row in cur.fetchall():
            counts[row[0]] = row[1]
    finally:
        cur.close()

    return counts


def get_success_failure_by_player(db: Connection, campaign: str, filter_player: Optional[str] = None,
                                  filter_test: Optional[str] = None) -> Dict[str, Tuple[float, float]]:
    """Return by player a tuple containing the success and the failure rate in order"""
    rates = {}

    cur = db.cursor()
    params = [campaign]
    if filter_player:
        params.append(filter_player)
    if filter_test:
        params.append(filter_test)
    try:
        cur.execute('select "name",'
                    ' count(case when ((margin > 0 or critical_success) and not critical_failure) then 1 end),'
                    ' count(rowid)'
                    ' from rolls where campaign=? and threshold > 0'
                    + (' and name=?' if filter_player else '')
                    + (' and reason=?' if filter_test else '')
                    + ' group by "name"', params)
        for row in cur.fetchall():
            rates[row[0]] = (row[1] / row[2] * 100, (row[2] - row[1]) / row[2] * 100)
    finally:
        cur.close()

    return rates


def get_critical_by_player(db: Connection, campaign: str, filter_player: Optional[str] = None,
                           filter_test: Optional[str] = None) -> Dict[str, Tuple[int, int]]:
    """Return by player a tuple containing the number of critical successes and failures in order"""
    data = {}

    cur = db.cursor()
    params = [campaign]
    if filter_player:
        params.append(filter_player)
    if filter_test:
        params.append(filter_test)
    try:
        cur.execute('select "name",'
                    ' count(case when critical_success then 1 end), count(case when critical_failure then 1 end)'
                    ' from rolls where campaign=? and threshold > 0'
                    + (' and name=?' if filter_player else '')
                    + (' and reason=?' if filter_test else '')
                    + ' group by "name"', params)
        for row in cur.fetchall():
            data[row[0]] = (row[1], row[2])
    finally:
        cur.close()

    return data


def get_nimdir_index_by_player(db: Connection, campaign: str, filter_player: Optional[str] = None,
                               filter_test: Optional[str] = None) -> Dict[str, Tuple[int, int]]:
    """Return by player a tuple containing the streak of successes and the streak of failures in order"""
    failures = {}
    successes = {}
    streaks = {}

    cur = db.cursor()
    params = [campaign]
    if filter_player:
        params.append(filter_player)
    if filter_test:
        params.append(filter_test)
    try:
        cur.execute('select "name", ((margin > 0 or critical_success) and not critical_failure)'
                    ' from rolls where campaign=? and threshold > 0'
                    + (' and name=?' if filter_player else '')
                    + (' and reason=?' if filter_test else '')
                    + ' order by rowid asc', params)
        for row in cur.fetchall():
            streak = streaks.setdefault(row[0], (True, 0))
            if bool(row[1]) == streak[0]:
                streaks[row[0]] = (streak[0], streak[1] + 1)
            else:
                data = successes if streak[0] else failures
                if data.get(row[0], 0) < streak[1]:
                    data[row[0]] = streak[1]
                streaks[row[0]] = (bool(row[1]), 1)

        for name, streak in streaks.items():
            data = successes if streak[0] else failures
            if data.get(name, 0) < streak[1]:
                data[name] = streak[1]
    finally:
        cur.close()

    return {name: (successes.get(name, 0), failures.get(name, 0))
            for name in sorted(list(set(list(successes.keys()) + list(failures.keys()))))}


def get_thresholds_by_player(db: Connection, campaign: str, filter_player: Optional[str] = None,
                             filter_test: Optional[str] = None) -> Dict[str, int]:
    """Return by player a list of all the thresholds he/she attempted"""
    thresholds = {}

    cur = db.cursor()
    params = [campaign]
    if filter_player:
        params.append(filter_player)
    if filter_test:
        params.append(filter_test)
    try:
        cur.execute('select "name", "threshold" from rolls where campaign=? and threshold > 0'
                    + (' and name=?' if filter_player else '')
                    + (' and reason=?' if filter_test else '')
                    + ' order by "name" asc', params)
        for row in cur.fetchall():
            thresholds.setdefault(row[0], []).append(row[1])
    finally:
        cur.close()

    return thresholds


def get_margins_by_player(db: Connection, campaign: str, filter_player: Optional[str] = None,
                          filter_test: Optional[str] = None) -> Dict[str, int]:
    """Return by player a list of all the obtained margins"""
    margins = {}

    cur = db.cursor()
    params = [campaign]
    if filter_player:
        params.append(filter_player)
    if filter_test:
        params.append(filter_test)
    try:
        cur.execute('select "name", "margin" from rolls where campaign=? and threshold > 0'
                    + (' and name=?' if filter_player else '')
                    + (' and reason=?' if filter_test else '')
                    + ' order by "name" asc', params)
        for row in cur.fetchall():
            margins.setdefault(row[0], []).append(row[1])
    finally:
        cur.close()

    return margins


def get_base_dices(db: Connection, campaign: str, filter_player: Optional[str] = None,
                   filter_test: Optional[str] = None) -> Dict[str, List[int]]:
    """
    Returns in a dictionary, the list of sums of 2 base dices obtained for each player
    """
    sums = {}

    cur = db.cursor()
    params = [campaign]
    if filter_player:
        params.append(filter_player)
    if filter_test:
        params.append(filter_test)
    try:
        cur.execute("select R.name, sum(dice) from dices D inner join rolls R on D.roll=R.rowid"
                    " where R.campaign=? and D.type='base_dices' and R.type=6 and R.number=2 and R.threshold > 0"
                    + (' and name=?' if filter_player else '')
                    + (' and reason=?' if filter_test else '')
                    + " group by D.roll", params)
        for row in cur.fetchall():
            sums.setdefault(row[0], []).append(row[1])
    finally:
        cur.close()

    return sums


def get_formula_usage(db: Connection, campaign: str, filter_player: Optional[str] = None,
                      filter_test: Optional[str] = None) -> Dict[str, int]:
    """Return the usage of each component, means and realm"""
    data = {}
    cur = db.cursor()
    params = [campaign]
    if filter_player:
        params.append(filter_player)
    if filter_test:
        params.append(filter_test)
    try:
        cur.execute('select F.element, count(*) from formula_elements F inner join rolls R on F.roll=R.rowid'
                    ' where R.campaign=?'
                    + (' and name=?' if filter_player else '')
                    + (' and reason=?' if filter_test else '')
                    + ' group by F.element', params)
        for row in cur.fetchall():
            data[row[0]] = row[1]
    finally:
        cur.close()
    return data


def get_energy_usage(db: Connection, campaign: str, filter_player: Optional[str] = None,
                     filter_test: Optional[str] = None) -> Dict[str, int]:
    """Return the usage of each energy"""
    data = {}
    cur = db.cursor()
    params = [campaign]
    if filter_player:
        params.append(filter_player)
    if filter_test:
        params.append(filter_test)
    try:
        cur.execute('select E.energy, count(*) from invested_energies E inner join rolls R on E.roll=R.rowid'
                    ' where R.campaign=?'
                    + (' and name=?' if filter_player else '')
                    + (' and reason=?' if filter_test else '')
                    + ' group by E.energy', params)
        for row in cur.fetchall():
            base_energy = row[0].split("-")[-1]
            data[base_energy] = data.get(base_energy, 0) + row[1]
    finally:
        cur.close()
    return data


def get_stats_by_test(db: Connection, campaign: str, filter_player: Optional[str] = None,
                      filter_test: Optional[str] = None) -> List[Tuple[str, int, float, float]]:
    """Return, for each test, its frequency, its average margin and its margin stddev"""
    data = []
    cur = db.cursor()
    params = [campaign, campaign]
    if filter_player:
        params.append(filter_player)
    if filter_test:
        params.append(filter_test)
    try:
        cur.execute('select R.reason, count(rowid) as c, s.a, avg((R.margin - s.a) * (R.margin - s.a)) as var'
                    ' from rolls R inner join'
                    ' (select reason, avg(margin) AS a FROM rolls where campaign=? and threshold > 0 group by reason) s'
                    ' on R.reason=s.reason'
                    ' where campaign=? and threshold > 0'
                    + (' and name=?' if filter_player else '')
                    + (' and R.reason=?' if filter_test else '')
                    + ' group by R.reason order by c desc', params)
        for row in cur.fetchall():
            data.append((row[0], row[1], row[2], math.sqrt(row[3])))
    finally:
        cur.close()
    return data
