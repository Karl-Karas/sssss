--
-- File generated with SQLiteStudio v3.2.1 on sam. juin 26 17:30:10 2021
--
-- Text encoding used: UTF-8
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- Table: dices
DROP TABLE IF EXISTS dices;
CREATE TABLE dices (roll INTEGER REFERENCES rolls (rowid) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, type VARCHAR NOT NULL DEFAULT 'base_dices', dice_index INTEGER NOT NULL DEFAULT (0) CHECK (dice_index >= 0), dice INTEGER NOT NULL DEFAULT (1) CHECK (dice >= 1), UNIQUE (roll, type, dice_index));

-- Table: formula_elements
DROP TABLE IF EXISTS formula_elements;
CREATE TABLE formula_elements (roll INTEGER REFERENCES rolls (rowid) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, element VARCHAR NOT NULL, UNIQUE (roll, element));

-- Table: invested_energies
DROP TABLE IF EXISTS invested_energies;
CREATE TABLE invested_energies (roll INTEGER NOT NULL REFERENCES rolls (rowid) ON DELETE CASCADE ON UPDATE CASCADE, energy VARCHAR NOT NULL, UNIQUE (roll, energy));

-- Table: rolls
DROP TABLE IF EXISTS rolls;
CREATE TABLE rolls (rowid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, campaign VARCHAR NOT NULL, name VARCHAR NOT NULL, number INTEGER NOT NULL DEFAULT (2), type INTEGER NOT NULL DEFAULT (6), timestamp DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')), recording BOOLEAN NOT NULL DEFAULT (TRUE), reason VARCHAR, max_value INTEGER NOT NULL DEFAULT (0), threshold INTEGER NOT NULL DEFAULT (0), margin INTEGER NOT NULL DEFAULT (0), critical_success BOOLEAN NOT NULL DEFAULT (FALSE), critical_failure BOOLEAN NOT NULL DEFAULT (FALSE), margin_throttle INTEGER, talent_level INTEGER NOT NULL DEFAULT (0), effect TEXT, is_magic BOOLEAN NOT NULL DEFAULT (FALSE), is_power BOOLEAN NOT NULL DEFAULT (FALSE), distance VARCHAR, focus VARCHAR, duration VARCHAR, base_energy_cost INTEGER NOT NULL DEFAULT (0), black_magic TEXT, magic_resistance TEXT, critical_increase INTEGER NOT NULL DEFAULT (0), precision INTEGER NOT NULL DEFAULT (0), optional_precision INTEGER NOT NULL DEFAULT (0), power INTEGER NOT NULL DEFAULT (0), optional_power INTEGER NOT NULL DEFAULT (0), magic_power INTEGER NOT NULL DEFAULT (0), speed INTEGER NOT NULL DEFAULT (0), optional_speed INTEGER NOT NULL DEFAULT (0), incantation BOOLEAN NOT NULL DEFAULT (FALSE), somatic_component BOOLEAN NOT NULL DEFAULT (FALSE), material_component BOOLEAN DEFAULT (FALSE) NOT NULL, unease TEXT NOT NULL DEFAULT (0), armor_penalty VARCHAR, margin_modifier INTEGER NOT NULL DEFAULT (0), effect_modifier INTEGER NOT NULL DEFAULT (0), energy_investment_validated BOOLEAN NOT NULL DEFAULT (TRUE), under_value INTEGER, superpower_modifier INTEGER NOT NULL DEFAULT (0), equipment VARCHAR, expended_charge INTEGER, CONSTRAINT Energies CHECK (optional_speed >= 0 AND optional_speed <= 3 AND speed >= 0 AND speed <= 3 AND power >= 0 AND power <= 3 AND optional_power >= 0 AND optional_power <= 3 AND magic_power >= 0 AND magic_power <= 3 AND optional_precision >= 0 AND optional_precision <= 3 AND precision >= 0 AND precision <= 3));

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
