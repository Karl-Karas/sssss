#!env python3
# coding: utf-8

# @author: K4r1K4r45
# 12/2020

# this code is public domain

import unittest
import tempfile
import os
import os.path
import string
import random
from pathlib import Path

from dmview import app, get_config, setup as app_setup

ENV_CONFIG = 'DMVIEW_CONFIGFILE'
COMMON_SECTION = 'Common'
ENCODING = 'UTF-8'

def random_string(l=10):
    out = ''
    for i in range(l):
        out += random.choice(string.ascii_letters + string.digits + '-_')
    return out

class BaseTest(unittest.TestCase):

    def setUp(self):
        self.root_dir = tempfile.TemporaryDirectory()
        self.bind_ip = '127.0.0.1'
        self.port = '8080'
        self.base_url = 'http://' + self.bind_ip + ':' + self.port
        self.campaign_dir = random_string()
        self.campaign_id = random_string()
        self.empty_campaign = random_string(40)
        self.no_such_campaign = random_string(40)
        self.no_such_sheet = random_string(40)

        self.test_config = {}
        self.test_config['bind_ip'] = self.bind_ip
        self.test_config['port'] = self.port
        self.test_config['root_directory'] = self.root_dir.name
        self.test_config['campaign_directory'] = self.campaign_dir
        self.test_config['empty_campaign_msg'] = self.empty_campaign
        self.test_config['no_such_campaign_msg'] = self.no_such_campaign
        self.test_config['no_such_sheet_msg'] = self.no_such_sheet
        self.test_config['form_name_field'] = 'name'
        self.test_config['form_page_field'] = 'page'

        self.config_fn = os.path.join(self.root_dir.name, random_string())

        with open(self.config_fn, 'w') as config:
            config.write(f'[{COMMON_SECTION}]\n')
            for k, v in self.test_config.items():
                config.write(k + ' = ' + v + '\n')

        os.environ[ENV_CONFIG] = self.config_fn

    def tearDown(self):
        self.root_dir.cleanup()
        del self.root_dir
        del os.environ[ENV_CONFIG]

class SetupTest(BaseTest):

    def test_get_config(self):
        config = get_config()
        for k, v in self.test_config.items():
            assert v == config[k]

    def test_setup(self):
        app_setup(app, config=get_config())
        assert os.path.isdir(self.root_dir.name)
        assert os.access(self.root_dir.name, os.W_OK)
        campaign_dir = os.path.join(self.root_dir.name, self.campaign_dir)
        assert os.path.isdir(campaign_dir)
        assert os.access(campaign_dir, os.W_OK)

class RestTest(BaseTest):

    def setup_campaign(self, campaign_id=None, nmb_empty_sheets=0, sheets=()):
        c_id = self.campaign_id if campaign_id is None else campaign_id
        try:
            c_path = os.path.join(self.root_dir.name,
                                  self.campaign_dir, 
                                  c_id)
            os.mkdir(c_path)
            for i in range(nmb_empty_sheets):
                Path(os.path.join(c_path, random_string())).touch()
            for s_id, s_content in sheets:
                Path(os.path.join(c_path, s_id)).write_text(s_content,
                                                            encoding=ENCODING)
            return os.listdir(c_path)
        except:
            raise Exception('Problem during working directory setup')

    def setUp(self):
        super().setUp()
        app_setup(app, config=get_config())
        self.client = app.test_client()

    def get_html(self, url):
        return self.client.get(url).data.decode(ENCODING)

    def post_html(self, url, data=None, **kw):
        return self.client.post(url, data=data, **kw).data.decode(ENCODING)

    def test_view_nocampaign(self):
        content = self.get_html('/view/' + self.campaign_id)
        assert self.no_such_campaign in content
        assert self.campaign_id in content

    def test_view_badcampaign(self): # should ignore bad characters
        bad_campaign_id = \
            ''.join([c+random.choice('!"$()*+,.;<=>@[]^`{|}~ \'')
                        for c in self.campaign_id])
        content = self.get_html('/view/' + bad_campaign_id)
        assert self.no_such_campaign in content
        assert self.campaign_id in content

    def test_view_empty_campaign(self):
        self.setup_campaign()
        content = self.get_html('/view/' + self.campaign_id)
        assert self.empty_campaign in content
        assert self.campaign_id in content

    def test_view_campaign(self):
        sheets = self.setup_campaign(nmb_empty_sheets=5)
        content = self.get_html('/view/' + self.campaign_id)
        assert self.campaign_id in content
        for sheet_id in sheets:
            assert sheet_id in content

    def test_view_nocampaign_sheet(self):
        sheets = self.setup_campaign(nmb_empty_sheets=5)
        no_campaign_id = random_string()
        content = self.get_html('/view' + 
                                '/' + no_campaign_id +
                                '/' + random.choice(sheets))
        assert self.no_such_campaign in content
        assert no_campaign_id in content

    def test_view_badcampaign_sheet(self):
        no_campaign_id = random_string()
        bad_campaign_id = \
            ''.join([c+random.choice('!"$()*+,.;<=>@[]^`{|}~ \'')
                        for c in no_campaign_id])
        sheets = self.setup_campaign(nmb_empty_sheets=5)
        content = self.get_html('/view' + 
                                '/' + no_campaign_id +
                                '/' + random.choice(sheets))
        assert self.no_such_campaign in content
        assert no_campaign_id in content
    
    def test_view_nosheet(self):
        self.setup_campaign()
        sheet_id = random_string()
        content = self.get_html('/view/' + self.campaign_id + '/' + sheet_id)
        assert self.no_such_sheet in content
        assert sheet_id in content
        assert self.campaign_id in content

    def test_view_badsheet(self):
        sheets = self.setup_campaign(nmb_empty_sheets=5)
        sheet_id = random.choice(sheets)
        bad_sheet_id = \
            ''.join([c+random.choice('!"$()*+,.;<=>@[]^`{|}~ \'')
                        for c in sheet_id])
        content = self.get_html('/view/' + self.campaign_id + '/' + bad_sheet_id)
        assert self.no_such_sheet in content
        assert self.campaign_id in content

    def test_view_sheet(self):
        sheet_content = random_string(500)
        sheet_id = random_string(30)
        sheets = self.setup_campaign(nmb_empty_sheets=5, 
                                     sheets = ((sheet_id, sheet_content),))
        content = self.get_html('/view/' + self.campaign_id + '/' + sheet_id)
        assert content == sheet_content

    def test_push_new_sheet_into_campaign(self):
        sheets = self.setup_campaign(nmb_empty_sheets=5)
        sheet_id = random_string(25)
        while sheet_id in sheets:
            sheet_id = random_string(25)
        content = self.get_html('/view/' + self.campaign_id + '/' + sheet_id)
        assert self.no_such_sheet in content

        sheet_content = random_string(500)
        content = self.post_html('/push/' + self.campaign_id + '/' + sheet_id,
                                 data=dict(
                                    name=sheet_id, 
                                    page=sheet_content), 
                                 follow_redirects=True)

        content = self.get_html('/view/' + self.campaign_id + '/' + sheet_id)
        assert content == sheet_content

    def test_push_new_sheet_no_campaign(self):
        sheet_id = random_string(25)
        content = self.get_html('/view/' + self.campaign_id + '/' + sheet_id)
        assert self.no_such_campaign in content

        sheet_content = random_string(500)
        content = self.post_html(url='/push/' + self.campaign_id + '/' + sheet_id,
                                 data=dict(
                                    name=sheet_id, 
                                    page=sheet_content),
                                 follow_redirects=True)

        content = self.get_html('/view/' + self.campaign_id + '/' + sheet_id)
        assert content == sheet_content

    def test_update_sheet(self):
        sheet_id = random_string(25)
        sheet_content = random_string(500)
        content = self.post_html(url='/push/' + self.campaign_id + '/' + sheet_id,
                                 data=dict(
                                    name=sheet_id, 
                                    page=sheet_content),
                                 follow_redirects=True)

        content = self.get_html('/view/' + self.campaign_id + '/' + sheet_id)
        assert content == sheet_content

        sheet_content = random_string(500)
        content = self.post_html(url='/push/' + self.campaign_id + '/' + sheet_id,
                                 data=dict(
                                    name=sheet_id, 
                                    page=sheet_content),
                                 follow_redirects=True)

        content = self.get_html('/view/' + self.campaign_id + '/' + sheet_id)
        assert content == sheet_content

##
##    def test_remove_sheet(self):
##        pass
##
##    def test_remove_campaign(self):
##        pass
##
##    def test_remove_nocampaign(self):
##        pass
##
##    def test_remove_nosheet(self):
##        pass
##
