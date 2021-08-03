"""Script to crawl the a discord channel for already encoded rolls"""
import argparse
import os
import re
from typing import Optional, Tuple

import discord
from discord import TextChannel, Embed

from db import init_db_connection, insert_roll, create_db, boolean_fields

client = discord.Client()

color_critical_mapping = {
    # color_code: (is_success, is_critical_success, is_critical_failure)
    0xff0000: (False, False, True),
    0xa70101: (False, False, False),
    0x01890a: (True, False, False),
    0x00ff11: (True, True, False),
    0x0066cc: (True, False, False)
}

emoji_to_db_value = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6
}

emoji_str = re.compile(r"<:(\w+):\d+>")


def parse_args():
    parser = argparse.ArgumentParser(description='Crawl through all rolls of a discord channel and save them'
                                                 ' to a database')
    parser.add_argument('token', help='The bot token for discord')
    parser.add_argument('discord_server_id', help='The server ID for discord')
    parser.add_argument('discord_channel_id', help='The channel ID for discord')
    parser.add_argument('campaign_id', help='The campaign ID for the server')
    parser.add_argument('database_path', help='The path to the database to save the rolls')
    return parser.parse_args()


def parse_emojis(emoji: str) -> str:
    name = emoji.split(":")[1]
    return emoji_to_db_value.get(name, name)


def parse_dice_emojis(dice_list: str) -> str:
    return ",".join([str(parse_emojis(dice)) for dice in dice_list.split(" ")])


def parse_title(title: str) -> Tuple[Optional[str], int]:
    if " (niveau " not in title:
        return None, 0
    split_text = title.split(" (niveau ")
    return split_text[0], int(split_text[-1].split(")")[0])


def parse_description(description: str) -> Tuple[str, int]:
    if len(description) == 0:
        return "", 0
    split_text = description.split("(")
    max_value = int(split_text[-1].split(")")[0])
    formula = [match.group(1) for match in emoji_str.finditer(split_text[0])]
    return ",".join(formula), max_value


def parse_result_text(result_text: str) -> Tuple[int, int]:
    if "sous" not in result_text:
        return 0, 0
    split_text = result_text.split("\nMR : ")
    margin = int(split_text[-1])
    return int(split_text[0].split(" sous ")[-1]), margin


@client.event
async def on_ready():
    nbr_rolls = 0
    for guild in client.guilds:
        if str(guild.id) == args.discord_server_id:
            print(f"GUILD OK: {args.discord_server_id}")
            channel: Optional[TextChannel] = None
            if args.discord_channel_id is not None:
                channel = guild.get_channel(int(args.discord_channel_id))
            if channel is None:
                channel = guild.text_channels[0]

            init = True
            before_message = None
            count = 0
            with init_db_connection(args.database_path) as db:
                while init or count != 0:  # do while until no message is retrieved
                    init = False
                    count = 0
                    async for message in channel.history(limit=1000, before=before_message):
                        # Look by chunk of 1000 messages
                        count += 1
                        roll_data = {}
                        before_message = message
                        if len(message.embeds) == 1:  # We have one embed
                            embed: Embed = message.embeds[0]
                            if not embed.author:  # No author
                                continue
                            roll_data["name"] = embed.author.name[1:]
                            roll_data["timestamp"] = message.created_at.strftime("%c")
                            roll_data["recording"] = 0

                            _, roll_data["critical_success"], roll_data["critical_failure"] = \
                                color_critical_mapping.get(embed.colour.value, (None, None, None))
                            if roll_data["critical_success"] is None \
                                    or not roll_data["name"] or not roll_data["timestamp"]:
                                print(f"Cannot parse {embed}")
                                continue  # Not a parsable embed

                            roll_data["reason"], roll_data['talent_level'] = parse_title(embed.title)
                            roll_data['formula_elements'], roll_data['max_value'] = \
                                parse_description(embed.description)

                            for field in embed.fields:
                                key = field.name
                                value = field.value

                                if key == "Lancer":
                                    roll_data["base_dices"] = parse_dice_emojis(value)
                                    roll_data["number"] = len(roll_data["base_dices"].split(","))
                                    roll_data["type"] = 6  # XXX Cannot spot focus rolls
                                elif key == "Dés d'Effet":
                                    roll_data["effect_dices"] = parse_dice_emojis(value)
                                elif key == "Dés de Puissance":
                                    roll_data["power_dices"] = parse_dice_emojis(value)
                                    # Add 1 power as invested energy by number of power_dices
                                    roll_data["optional_power"] = len(roll_data["power_dices"].split(","))
                                    roll_data["invested_energies"] = "optional-power"
                                elif key == "Dés Critiques":
                                    roll_data["critical_dices"] = parse_dice_emojis(value)
                                elif key == "Modif. effet":
                                    roll_data['effect_modifier'] = int(value)
                                elif key == "Résultat":
                                    roll_data['threshold'], roll_data["margin"] = parse_result_text(value)
                                elif key == "Effet":
                                    roll_data['effect'] = value  # MR and columns are already replaced

                            # Check the consistency of the data
                            if "base_dices" not in roll_data:  # Required for any roll
                                print("base_dices invalid :", roll_data)
                                continue  # Discard because no roll was made
                            if "threshold" in roll_data and roll_data["threshold"] != 0 \
                                    and ("effect_dices" not in roll_data or roll_data["critical_success"]
                                         and "critical_dices" not in roll_data or not roll_data["critical_success"]
                                         and "critical_dices" in roll_data):
                                print("THESH invalid :", roll_data)
                                continue  # Discard because invalid

                            # Make boolean filed match POST data for insert method
                            for field in boolean_fields:
                                if field in roll_data:
                                    roll_data[field] = "true" if bool(roll_data[field]) else "false"

                            # Insert in the database
                            print(roll_data)
                            insert_roll(db, args.campaign_id, roll_data)

                            nbr_rolls += 1

                    print(f"Messages until {before_message.created_at.strftime('%c')} retrieved")
                print("All messages parsed", nbr_rolls)
                break

    # Kill the bot connection
    await client.logout()


args = parse_args()
if not os.path.exists(args.database_path):
    create_db(args.database_path)
client.run(args.token)
