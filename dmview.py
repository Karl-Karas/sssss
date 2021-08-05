#!env python3
# coding: utf-8

# @author: K4r1K4r45
# 12/2020

# this code is public domain

import os, os.path
import sys
import configparser
import collections as col
import string
from pathlib import Path

from flask import Flask, current_app, request, Response, render_template, abort
from markupsafe import escape

from db import init_db_connection, insert_roll, create_db, get_stats_by_test, get_players
from discord_bot import roll_queue, init_bot, close_bot

from graph import success_failure_by_player, critical_by_player, nimdir_index_by_player, base_dice_distributions, \
    formula_usage, energy_usage, roll_count, magins_distributions, thresholds_distributions

## config meta data ##
default_section = 'Common'
campaign_section = r'[a-zA-Z0-9]{1,30}'
ConfigField = col.namedtuple('ConfigField', ['name',
                                             'type',
                                             'required',
                                             'default_value'])

bind_ip = ConfigField('bind_ip', 'str', False, '127.0.0.1')
port = ConfigField('port', 'int', False, '8080')
root_dir = ConfigField('root_directory', 'str', True, None)
campaign_dir = ConfigField('campaign_directory', 'str', False, 'campaigns')
empty_campaign_msg = ConfigField('empty_campaign_msg', 'str', False,
                                 'This campaign is empty.')
no_such_campaign_msg = ConfigField('no_such_campaign_msg', 'str', False,
                                   'No such campaign!')
no_such_sheet_msg = ConfigField('no_such_sheet_msg', 'str', False,
                                   'No such sheet!')
form_name = ConfigField('form_name_field', 'str', False, 'name')
form_page = ConfigField('form_page_field', 'str', False, 'page')
discord_bot_token = ConfigField('discord_bot_token', 'str', False, None)
discord_server_id = ConfigField('discord_server_id', 'str', False, None)
max_discord_messages_by_server = ConfigField('max_discord_messages_by_server', 'int', False, 100)
discord_channel_id = ConfigField('discord_channel_id', 'str', False, None)
discord_msg_type = ConfigField('discord_msg_type', 'str', False, None)
database_path = ConfigField('database_path', 'str', False, "roll.sqlite3")

config_meta = {
                default_section: [
                    bind_ip,
                    port,
                    root_dir,
                    campaign_dir,
                    empty_campaign_msg,
                    no_such_campaign_msg,
                    no_such_sheet_msg,
                    form_name,
                    form_page,
                    discord_bot_token,
                    max_discord_messages_by_server,
                    database_path
                ],

                campaign_section : [
                    discord_server_id,
                    discord_channel_id,
                    discord_msg_type,
                ],
            }
## end config meta data ##
def get_config():
    """
        Get the file path from os.environ DMVIEW_CONFIGFILE; read that file.
        returns a dict object with the configuration
    """
    config = configparser.ConfigParser()
    try:
        config_filepath = os.environ["DMVIEW_CONFIGFILE"]
        config.read(config_filepath)
        return dict(config)
    except:
        return None

def setup(app, config=None):
    """
        Setup the config
        Add local-config attribute to the app
    """
    if not config:
        return None
    try:
        root_path = config[default_section][root_dir.name]
        campaign_path = os.path.join(root_path, config[default_section][campaign_dir.name])
        for path in [root_path, campaign_path]:
            if not os.path.isdir(path):
                os.mkdir(path)
        campaign_configs = dict(config)
        campaign_configs.pop(default_section)
    except:
        print('ERROR: problem during setup!', file=sys.stderr)
        raise
    app.local_config = config[default_section]
    app.campaign_configs = campaign_configs
    token = app.local_config.get(discord_bot_token.name)
    max_messages = int(app.local_config.get(max_discord_messages_by_server.name,
                                            max_discord_messages_by_server.default_value))
    # Setup database
    db_path = app.local_config.get(database_path.name, database_path.default_value)
    if not os.path.exists(db_path):
        create_db(db_path)
    if token is not None:
        init_bot(token, max_messages)
    return app

def run(app):
    app.run(host=app.local_config[bind_ip.name],
            port=app.local_config[port.name],
            debug=True)
    token = app.local_config.get(discord_bot_token.name)
    if token is not None:
        close_bot()

def sanitize(data):
    """
        Returns data without any non alphanum(+[-_]) character
    """
    return ''.join([c for c in data
                    if c in string.ascii_letters + string.digits + '-_'])

def get_campaign_path(campaign_id, config):
    """
        Return the path to a campaign with respect to config
    """
    campaign_id = sanitize(campaign_id)
    return os.path.join(config[root_dir.name],
                               config[campaign_dir.name],
                               campaign_id)

def get_campaign(path):
    """
        Returns the list of sheet in the campaign or None if the campaign does
        not exist
    """
    if os.path.isdir(path):
        return os.listdir(path)
    return None

def get_sheet_path(campaign_id, sheet_id, config):
    campaign_id = sanitize(campaign_id)
    sheet_id = sanitize(sheet_id)
    return os.path.join(get_campaign_path(campaign_id, config), sheet_id)

def get_file_content(path):
    return Path(path).read_text()

def create_campaign(path):
    """
        For now, just create the directory
    """
    if not os.path.isdir(path):
        try:
            os.mkdir(path)
        except:
            print('ERROR: problem during campaign setup!', file=sys.stderr)
            raise
    return True

## setup app, Flask style, before routing definitions as we need <app> ##
app = setup(Flask(__name__), get_config())
## end setup app ##

@app.route('/view/<campaign_id>')
def view_campaign(campaign_id):
    campaign_id = sanitize(campaign_id)
    campaign_path = get_campaign_path(campaign_id, app.local_config)
    campaign_list = get_campaign(campaign_path)
    if campaign_list is None:
        return app.local_config[no_such_campaign_msg.name] + ' ' + campaign_id
    if len(campaign_list) == 0:
        return app.local_config[empty_campaign_msg.name] + ' ' + campaign_id
    out = '<html><body><h1>' + campaign_id + '</h1>\n<ul>'
    for sheet in campaign_list:
        out += f'<li><a href="/view/{campaign_id}/{sheet}" target="_blank">' + sheet + '</a></li>\n'
    return out + '</ul></body></html>'

@app.route('/view/<campaign_id>/<sheet_id>')
def view_sheet(campaign_id, sheet_id):
    campaign_id = sanitize(campaign_id)
    san_sheet_id = sanitize(sheet_id)
    if san_sheet_id != sheet_id:
        return app.local_config[no_such_sheet_msg.name] + ' ' + campaign_id
    campaign_path = get_campaign_path(campaign_id, app.local_config)
    campaign_list = get_campaign(campaign_path)
    if campaign_list is None:
        return app.local_config[no_such_campaign_msg.name] + ' ' + campaign_id
    if sheet_id in campaign_list:
        return get_file_content(
                    get_sheet_path(campaign_id, sheet_id, app.local_config))
    return app.local_config[no_such_sheet_msg.name] + ' ' + sheet_id + ' ' + campaign_id

@app.route('/push/<campaign_id>/<sheet_id>', methods=['POST'])
def push_sheet(campaign_id, sheet_id):
    campaign_path = get_campaign_path(campaign_id, app.local_config)
    if not create_campaign(campaign_path):
        return ''
    sheet_path = get_sheet_path(campaign_id, sheet_id, app.local_config)
    f_name = app.local_config[form_name.name]
    f_page = app.local_config[form_page.name]
    Path(sheet_path).write_text(request.form[f_page])
    resp = Response("OK")
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/roll/<campaign_id>', methods=['POST'])
def push_roll(campaign_id):
    # Save the roll in database
    with init_db_connection(app.local_config.get(database_path.name, database_path.default_value)) as db:
        insert_roll(db, campaign_id, dict(request.form))
    # Get discord server, if any, matching the campaign
    server_id = app.campaign_configs.get(campaign_id, {}).get(discord_server_id.name)
    print(f"SERVER OK: {server_id}")
    if server_id is not None:
        channel_id = app.campaign_configs.get(campaign_id, {}).get(discord_channel_id.name)
        msg_type = app.campaign_configs.get(campaign_id, {}).get(discord_msg_type.name)
        item = dict(request.form)
        item[discord_server_id.name] = server_id
        item[discord_channel_id.name] = channel_id
        item[discord_msg_type.name] = msg_type
        roll_queue.put(item)
    resp = Response("OK")
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/graphs/<campaign>', methods=['GET'])
def view_graph_page(campaign):
    player = request.args.get("player")
    test = request.args.get("test")
    with init_db_connection(app.local_config.get(database_path.name, database_path.default_value)) as db:
        players = get_players(db, campaign)
        return render_template("graphs.html", campaign=campaign, filter_player=player, filter_test=test,
                               players=get_players(db, campaign),
                               test_stats=get_stats_by_test(db, campaign, filter_player=player, filter_test=test),
                               success_failure_by_player=success_failure_by_player(db, campaign, player=player,
                                                                                   test=test),
                               critical_by_player=critical_by_player(db, campaign, player=player, test=test),
                               nimdir_index_by_player=nimdir_index_by_player(db, campaign, player=player, test=test),
                               base_dice_distributions=base_dice_distributions(db, campaign, player=player, test=test),
                               formula_usage=formula_usage(db, campaign, player=player, test=test),
                               energy_usage=energy_usage(db, campaign, player=player, test=test),
                               roll_count=roll_count(db, campaign, player=player, test=test),
                               thresholds_distributions=thresholds_distributions(db, campaign, player=player,
                                                                                 test=test) if players else {},
                               magins_distributions=magins_distributions(db, campaign, player=player,
                                                                         test=test) if players else {})


if __name__ == '__main__':
    run(app)
