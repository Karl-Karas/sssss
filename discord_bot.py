import asyncio
import distutils.util
import queue
import threading
import random
import re
import math

import discord

loop = asyncio.get_event_loop()
roll_queue = queue.Queue()
client = discord.Client()
stop_thread = False
thread = None
messages = {}
ordered_messages = {}
max_messages_by_server = 100

def result_printer(func):
    def wrapper (*args, **kw):
        res = func(*args, **kw)
        print(f'{func.__name__}(', ' '.join(map(lambda a: '|'+str(a)+'|', args)), ', '+' '.join(map(lambda k, v: f'|{k}={v}|', kw.items())), ') =', str(res))
        return res
    return wrapper

effect_table = {
#       0  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26
  'A': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3],
  'B': [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4],
  'C': [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5],
  'D': [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6],
  'E': [0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 4, 6, 6, 6, 6, 8, 8, 8, 8],
  'F': [0, 0, 0, 1, 2, 2, 2, 2, 2, 2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 6, 6, 6, 6, 8, 8, 8, 8],
  'G': [0, 0, 0, 1, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 5, 5, 5, 5, 7, 7, 7, 7, 9, 9, 9, 9],
  'H': [0, 0, 0, 1, 2, 2, 2, 3, 3, 3, 4, 4, 5, 5, 5, 6, 6, 6, 6, 8, 8, 8, 8, 9, 9, 9, 9],
  'I': [0, 0, 0, 1, 2, 2, 2, 4, 4, 4, 4, 4, 5, 5, 5, 6, 6, 6, 6, 8, 8, 8, 8, 10,10,10,10],
  'J': [0, 0, 0, 1, 3, 3, 3, 4, 4, 4, 5, 5, 6, 6, 6, 8, 8, 8, 8, 10,10,10,10,12,12,12,12],
  'K': [0, 0, 0, 1, 3, 3, 3, 5, 5, 5, 5, 5, 6, 6, 6, 8, 8, 8, 8, 10,10,10,10,12,12,12,12],
'inc': {'A': 1, 'B': 1, 'C': 2, 'D': 2, 'E': 2, 'F': 2, 'G': 3, 'H': 3, 'I': 4, 'J': 4, 'K': 6}
}

@result_printer
def get_effect(letter, throw, modif=None):
    if modif is not None:
        throw += modif
    if letter in effect_table and throw >= 0:
        try:
            return effect_table[letter][throw]
        except IndexError:
            return math.ceil((throw - (len(effect_table[letter])-1)) / 4) * effect_table['inc'][letter] + effect_table[letter][-1]
        except KeyError:
            pass

    return 0

pat_mr = re.compile(r'MR')
pat_effect = re.compile(r'\[\s?([ABCDEFGHIJK])\s?([+-]\s?[1-9])?\s?\]')

@result_printer
def build_effect(effect_desc, mr, effect_dices):
    effect_throw = mr + effect_dices
    effect_desc = effect_desc.replace('MR', str(mr))
    effect_desc = pat_effect.sub(
                    lambda letter: str(get_effect(  letter.group(1), 
                                                    effect_throw, 
                                                    None if letter.group(2) is None 
                                                    else int(letter.group(2).replace(' ', '')) 
                                                )
                                    ), 
                    effect_desc)
    return effect_desc

def get_emoji(name):
    emoji = discord.utils.get(client.emojis, name=name)
    if emoji is None:
        return name
    return str(emoji)

def get_dice(nmbr):
    dices = {
        '1': 'one', 
        '2': 'two', 
        '3': 'three', 
        '4': 'four', 
        '5': 'five',
        '6': 'six' }
    return get_emoji(dices[nmbr]) 

def get_result(margin=None, crit_succ=None, crit_fail=None):
    data = {
        'crit_fail': (  0xff0000,  # brigth red
                        '- Echec Critique -', 
                        ['dizzy_face', 'scream', 'sob', 'rage',
                        'face_with_symbols_over_mouth', 'exploding_head',
                        'skull', 'fire', 'skull_crossbones'],
                        'diff',
                        ['tU V€uX §U ThÉ ?', 
                         'Tu vŒufs Du tHÉ Tw@ 0u Kw4 ??'
                         'BwA In P-œufs D3 ThÉ !', 
                         'Sss@ SsÈ Biijin R4thé Sss@ !',
                         'bIn Ssà sSÈ KomþLÈt3m@N nU££ !']),
        'fail': (       0xa70101,  # dark red
                        'Echec',
                        ['pensive', 'worried', 'confused', 'persevere',
                        'disappointed', 'unamused', 'poop'],
                        'fix',
                        ["T'@s Ra-Thé !",
                         'Maître ! Maître ! iLle @ R4tHÉe !',
                         'Pr4n Un pEu d€ tHè, sS@ yRà mj-œufs',
                         'p4 gR@afF r3K0maNSs, $0f sSi Tè M0oOrTt !']),
        'success': (    0x01890a, # green 
                        '"Succès"',
                        ['smiley', 'grinning', 'blush', 'stuck_out_tongue',
                        'upside_down', 'kissing_smiling_eyes', '+1', 'clap'],
                        'CPP',
                        ['Enk0r uN3 þ3Titt Tàs$E ?',
                         'bR@vAu ! bW4 dU Thé MinTNàn !',
                         '0n dIRè k€ s$è rÉUSssi, M0n tHÉ osSI !',
                         '@vèK uN€ t4Sse d3 tHÉ ¢@ OrÈ @nK0r éthé Mi-œufs']),
        'crit_succ': (  0x00ff11, # brigth green
                        '+ Succès Critique +',
                        ['star_struck', 'partying_face', 'heart_eyes',
                        'muscle', 'fireworks', 'tada', 'trophy', 'champagne',
                        'clinking_glass'],
                        'diff',
                        ['tU B0!s Du tHé Tw@ !',
                         'Maître ! Maître ! iLle @ R€u¢I Lu! !',
                         'Ssa pR0Uvf k€ mON Thé m4RCh bi3n',
                         '@tR4Pp pA La GroO0Ss tÈTt, pRàn pLUtô dU Thé' ]),
        'simple_roll': ( 0x0066cc, # blue
                        "[𝅘𝅥𝅮 Take a chance, roll the dices! 𝅘𝅥𝅯 ]",
                        ['smiley', 'grinning', 'blush', 'stuck_out_tongue',
                        'upside_down', 'kissing_smiling_eyes', '+1', 'clap',
                        'pensive', 'worried', 'confused', 'persevere',
                        'disappointed', 'unamused', 'poop'],
                        'ini',
                        ['tU B0!s Du tHé Tw@ !', 
                         'tU V€uX §U ThÉ ?', 
                         'Tu vŒufs Du tHÉ Tw@ 0u Kw4 ??', 
                         'BwA In P-œufs D3 ThÉ !',
                         '@vèK uN€ t4Sse d3 tHÉ ¢@ OrÈ @nK0r éthé Mi-œufs']),
    }
    if crit_succ == 'true':
        return data['crit_succ']
    if crit_fail == 'true':
        return data['crit_fail']
    if margin is None:
        return data['simple_roll']
    if margin >= 1:
        return data['success']
    return data['fail']

async def wait_for_rolls():
    await client.wait_until_ready()
    while not stop_thread:
        if not roll_queue.empty():
            item = roll_queue.get()
            client.dispatch("roll", item.pop("discord_server_id"), item.pop("name"), item)
            roll_queue.task_done()
        await asyncio.sleep(1)

def build_roll_data(character, roll_details, msg_type=None):
    if msg_type is None:
        return build_roll_text(character, roll_details)
    if msg_type == 'embed':
        return build_roll_embed(character, roll_details)

def build_roll_embed(character, roll_details):
    if "margin" in roll_details:
        return build_roll_embed_normal(character, roll_details)
    return build_roll_embed_simple(character, roll_details)

def build_roll_embed_simple(character, roll_details):
    d = roll_details
    result_color, result_name, result_emojis, result_code, result_grotz = get_result(
                                                                  None,
                                                                  d['critical_success'], 
                                                                  d['critical_failure'])

    embed=discord.Embed(
        title=f"Un simple lancer",
        url="", 
        description="",
        color=result_color)

    embed.set_author(
        name=f'@{character}', 
        url="",
        icon_url="")

    embed.add_field(name="Lancer", 
                    value=' '.join(map(get_dice, d['base_dices'].split(','))), 
                    inline=True)
    
    embed.add_field(name="Résultat", 
                    value=f"{sum(map(int,d['base_dices'].split(',')))}", 
                    inline=True)

    random.shuffle(result_emojis)
    embed.add_field(value=f'```{result_code}\n{result_name}```', 
                    name=' '.join(map(lambda s: f':{s}:', 
                                      random.sample(result_emojis, 
                                                    random.choice([1, 2, 2, 3, 3, 3, 4]))
                                      + ['interrobang'])),
                    inline=False)
    
    embed.set_footer(text=f"« {random.choice(result_grotz)} »")
    
    return embed

def build_roll_embed_normal(character, roll_details):
    d = roll_details
    from pprint import pprint
    pprint(d)
    result_color, result_name, result_emojis, result_code, result_grotz = get_result(int(d['margin']),
                                                                  d['critical_success'], 
                                                                  d['critical_failure'])

    formula = ""
    for element in d["formula_elements"].split(','):
        formula += f"{get_emoji(element)} + "
    formula = formula[:-3]

    title = "Let' Roll!"
    description = f'Test sous {formula}'
    if d['reason']:
        title = f"{d['reason']} (niveau {d['talent_level']})" 
        description += f" + {d['reason']}"
    description += f" ({d['max_value']})"

    embed=discord.Embed(
        title=title,
        url="", 
        description="",
        color=result_color)

    embed.set_author(
        name=f'@{character}', 
        url="",
        icon_url="")

    embed.description = description

    embed.add_field(name="Lancer", 
                    value=' '.join(map(get_dice, d['base_dices'].split(','))), 
                    inline=True)
    embed.add_field(name="Résultat", 
                    value=f"{sum(map(int,d['base_dices'].split(',')))} sous {d['threshold']}\nMR : {d['margin']}", 
                    inline=True)
    random.shuffle(result_emojis)
    embed.add_field(value=f'```{result_code}\n{result_name}```', 
                    name=' '.join(map(lambda s: f':{s}:', 
                                      random.sample(result_emojis, 
                                                    random.choice([1, 2, 2, 3, 3, 3, 4])))),
                    inline=True)
    
    crit_dices = d['critical_dices']
    if crit_dices:
        embed.add_field(name="Dés Critiques", 
                        value=' '.join(map(get_dice, crit_dices.split(','))), 
                        inline=True)
    
    power_dices = d['power_dices']
    if power_dices:
        embed.add_field(name="Dés de Puissance", 
                        value=' '.join(map(get_dice, power_dices.split(','))), 
                        inline=True)
    
    embed.add_field(name="Dés d'Effet", 
                    value=' '.join(map(get_dice, d['effect_dices'].split(','))), 
                    inline=True)
    
    effect_dices = d['effect_dices'].split(',')
    effect_modifier = d['effect_modifier']
    if int(effect_modifier) != 0:
        effect_dices += [effect_modifier]
        embed.add_field(name="Modif. effet", 
                        value=str(effect_modifier), 
                        inline=True)

    effect_dices = sum(map(int, effect_dices))
    effect_title = 'Alea Jacta Est!'
    effect_value = random.choice([
        "*...without description,\nI can't say much*",
        "*It's a simple roll*",
        "You took a chance *and* rolled the dices!",
        "Well, *something* should have happened right ?",
        "Try again ?",
        "Are you happy ?",
    ])
    if d['effect']:
        effect_title = 'Effet'
        effect_value = build_effect(d['effect'], int(d['margin']), effect_dices)
    embed.add_field(name = effect_title, 
                    value = effect_value,
                    inline = True)
    
    embed.set_footer(text=f"« {random.choice(result_grotz)} »")
    
    return embed

def build_roll_text(character, roll_details):
    critical_success = distutils.util.strtobool(roll_details["critical_success"])
    critical_failure = distutils.util.strtobool(roll_details["critical_failure"])
    nl = "\n"
    if "margin" in roll_details:
        reason = roll_details["reason"]
        if len(reason) > 0:
            reason += ": "
        reason += roll_details["formula_elements"].replace(",", ", ")

        effect_modifier = ""
        if int(roll_details["effect_modifier"]) != 0:
            effect_modifier = f'\nModificateur d\'effet: {roll_details["effect_modifier"]}'
        text = (f'**@{character}** ({reason}):'
                f'\nMarge de {roll_details["margin"]}'
                f' pour une valeur seuil de {roll_details["threshold"]}'
                f'{nl + "Succès critique !" if critical_success else ""}'
                f'{nl + "Échec critique..." if critical_failure else ""}'
                f'\nDés d\'effet: {roll_details["effect_dices"].replace(",", ", ")}'
                f'{effect_modifier}'
                f'{nl + "Effet: " + roll_details["effect"] if len(roll_details["effect"]) > 0 else ""}')
    else:
        text = (f'**@{character}** a lancé {roll_details["number"]}d{roll_details["type"]}:'
                f'{roll_details["base_dices"].replace(",", ", ")}'
                f'{nl + "Succès critique !" if critical_success else ""}'
                f'{nl + "Échec critique..." if critical_failure else ""}')
    return text

def msg_send(msg_type, channel, character, roll_details):
    print(f"SEND MSG : {msg_type}, {channel}, {character}, {roll_details}")
    data = build_roll_data(character, roll_details, msg_type)
    if msg_type is None:
        return channel.send(content=data)
    if msg_type == 'embed':
        return channel.send(embed=data)

def msg_edit(msg_type, msg, character, roll_details):
    data = build_roll_data(character, roll_details, msg_type)
    if msg_type is None:
        return msg.edit(content=data)
    if msg_type == 'embed':
        return msg.edit(embed=data)

@client.event
async def on_roll(discord_server, character, roll_details):
    for guild in client.guilds:
        if str(guild.id) == discord_server:
            print(f"GUILD OK: {discord_server}")
            channel = None
            if roll_details["discord_channel_id"] is not None:
                channel = guild.get_channel(int(roll_details["discord_channel_id"]))
            if channel is None:
                channel = guild.text_channels[0]

            msg_type = roll_details["discord_msg_type"]
            
            msg = messages.setdefault(discord_server, {}).get(f'{character}-{roll_details["timestamp"]}')
            print(f"MSG OK: {msg}")
            if msg is None:
                print(f"MSG NEW")
                msg = await msg_send(msg_type, channel, character, roll_details)
                print(f"MSG NEW {msg}")
                key = f'{character}-{roll_details["timestamp"]}'
                messages[discord_server][key] = msg
                ordered_messages.setdefault(discord_server, []).append(key)
                if len(ordered_messages[discord_server]) > max_messages_by_server:
                    del messages[discord_server][key]
                    del ordered_messages[discord_server][0]
            else:
                await msg_edit(msg_type, msg, character, roll_details)

def init_bot(token, max_messages):
    global thread
    global max_messages_by_server
    max_messages_by_server = max_messages
    loop.create_task(client.start(token))
    client.loop.create_task(wait_for_rolls())
    thread = threading.Thread(target=loop.run_forever)
    thread.start()


def close_bot():
    global thread
    global stop_thread
    stop_thread = True
    if thread is not None:
        client.loop.stop()
        thread.join()
        thread = None
