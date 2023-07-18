#!/usr/bin/env python3
'''Icinga2 plugin to create and track RT tickets when services and hosts go critical'''

import argparse
import dataclasses
import json
import os
import re
import requests
import sys
import traceback

from lib.SettingsParser import SettingsParser
from lib.Util import initLogger

from loguru import logger


import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# Disabled proxies for requests to localhost
os.environ['NO_PROXY'] = 'localhost'

RT_REGEX = re.compile(r'(# Ticket )(\w+)( created)')
TICKETID_REGEX = re.compile(r'(#)([0-9]+)(\])')
SESSION = requests.session()

@dataclasses.dataclass
class SettingsFile(SettingsParser):
    def __post_init__(self):
        self.loadConfigDict()
        
@dataclasses.dataclass
class SettingsRT(SettingsFile):
    name: str = 'rtInstance'
    queue: str = 'rtqueue'
    url: str = 'https://rt.example.com'
    username: str = 'rtbot'
    password: str = ''
    _json_dict_key: str = 'rt'

@dataclasses.dataclass
class SettingsIcinga(SettingsFile):
    url: str = 'https://localhost:5665'
    username: str = 'rtnotify'
    password: str = ''
    _json_dict_key: str = 'icinga'

@dataclasses.dataclass
class Settings(SettingsParser):
    rt: object = None
    icinga: object = None
    _exclude_all: list = dataclasses.field(default_factory=lambda: ['rt', 'icinga'])

    config_file: str = 'config/request-tracker-notification.json'
    debug: bool = False
    disable_log_file: bool = False

    host_name: str = ''
    host_displayname: str = ''
    host_address: str = ''
    host_state: str = ''
    host_output: str = ''
    service_name: str = ''
    service_displayname: str = ''
    service_state: str = ''
    service_output: str = ''
    notification_author: str = ''
    notification_comment: str = ''
    notification_type: str = ''

    rt_requestor: str = ''
    rt_queue: str = ''

    print_config: bool = False

    def __post_init__(self):
        try:
            self._exclude_from_args.extend(self._exclude_all)
            self._exclude_from_env.extend(self._exclude_all + ['print_config'])
            self._env_prefix = "NOTIFY_RT_"
            self.loadEnvironmentVars()
            self._args = self._init_args()
            self.loadArgs(self._args)

            # These set in the config file will override the args
            self._include_from_file = ['debug', 'disable_log_file']

            self.loadConfigJsonFile()

            # Sensible defaults after loading everything
            if self.host_address == '':
                self.host_address = self.host_displayname

        except Exception as e:
            print("Failed to initialize {e}")
            print(traceback.format_exc())
            sys.exit()

    def _init_args(self):
        parser = argparse.ArgumentParser(description='Icinga2 plugin to send enhanced email notifications with links to Grafana and Netbox')
        for arg in self._getArgVarList():
            if type(arg[2]) == bool:
                parser.add_argument(arg[1], action="store_true")
            else:
                parser.add_argument(arg[1], type=type(arg[2]), default=arg[2])
        return parser.parse_args()

    def printEnvironmentVars(self):
        print("Environment vars list is:")
        for var in self._getEnvironmentVarList():
            print(f'{var[1]} = {var[2]}')
        print('')

    def printArguments(self):
        print("Argument list is:")
        for var in self._getArgVarList():
            print(f'{var[1]} = {var[2]}')
        print('')


def authenticate_rt():
    '''Authenticates with the RT server for all subsequent requests'''
    SESSION.post(config.rt.url, data={
                 "user": config.rt.username, "pass": config.rt.password})


def create_ticket_message():
    additional_output = config.service_output or config.host_output
    state = config.service_state or config.host_state

    message = "Notification Type: {}\n \n".format(config.notification_type)
    message += " Service: {}\n".format(config.service_displayname)
    message += " Host: {}\n".format(config.host_displayname)
    message += " Address: {}\n".format(config.host_address)
    message += " State: {}\n \n".format(state)
    message += " Additional Info: {}\n \n".format(
        parse_rt_field(additional_output))
    message += " Comment: [{}] {}\n".format(
        config.notification_auth_name,
        config.notification_comment)
    return message


def create_ticket_rt(subject):
    '''Creates a ticket in RT and returns the ticket ID'''

    message = create_ticket_message()

    ticket_data = "id: ticket/new\n"
    ticket_data += "Queue: {}\n".format(config.rt_queue)
    ticket_data += "Requestor: {}\n".format(config.rt_requestor)
    ticket_data += "Subject: {}\n".format(subject)
    ticket_data += "Text: {}".format(message)

    res = SESSION.post(
        config.rt.url + "/REST/1.0/ticket/new",
        data={"content": ticket_data},
        headers=dict(Referer=config.rt.url))

    print("Message:")
    print(message)
    print("Response: ")
    print(res.text)

    return RT_REGEX.search(res.text).group(2)


def add_comment_rt(ticket_id):
    '''Add a comment to an existing RT ticket'''

    message = create_ticket_message()
    ticket_data = "id: {id}\n".format(id=ticket_id)
    ticket_data += "Action: comment\n"
    ticket_data += "Text: {text}".format(text=message)

    SESSION.post(
        config.rt.url + "/REST/1.0/ticket/{id}/comment".format(
            id=ticket_id),
        data={"content": ticket_data},
        headers=dict(Referer=config.rt.url))

    return


def set_status_rt(ticket_id, status="open"):
    '''Set rt ticket status'''

    ticket_data = "Status: {}\n".format(status)

    SESSION.post(
        config.rt.url + "/REST/1.0/ticket/{id}/edit".format(
            id=ticket_id),
        data={"content": ticket_data},
        headers=dict(Referer=config.rt.url))

    return


def set_subject_recovered_rt(ticket_id):
    '''Set rt ticket subject'''

    subject = "{} {} - Recovered".format(config.host_displayname, config.service_displayname)

    ticket_data = "Subject: {}\n".format(subject)

    SESSION.post(
        config.rt.url + "/REST/1.0/ticket/{id}/edit".format(
            id=ticket_id),
        data={"content": ticket_data},
        headers=dict(Referer=config.rt.url))

    return

class Icinga:
    def __init__(self, username, password, base_url):
        self.username = username
        self.password = password
        self.base_url = base_url

    def _get(self, url_path, payload):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8'
        }
        return SESSION.get(
            self.base_url + url_path,
            auth=(self.username, self.password),
            verify=False,
            headers=headers,
            json=payload
            )

    def _post(self, url_path, payload = None):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8'
        }

        if payload:
            return SESSION.post(
                self.base_url + url_path,
                auth=(self.username, self.password),
                verify=False,
                headers=headers,
                json=payload
                )
        else:
            return SESSION.post(
                        self.base_url + url_path,
                        auth=(self.username, self.password),
                        verify=False,
                        headers=headers
                        )

    def get_comments_icinga(self, hostname, servicename):
        '''Get all icinga comments associated with a hostname'''

        filters = 'host.name=="{}"'.format(hostname)
        filters += '&&service.name=="{}"'.format(servicename)   
        filters += '&&comment.author=="{}"'.format(self.username)

        body = {'filter': filters}

        res = self._get("/v1/objects/comments", body)

        result = json.loads(res.text)['results']
        return result


    def add_comment_icinga(self, hostname, servicename, comment_text):
        '''Create comment on an icinga service or host'''

        filters = 'host.name=="{}"'.format(hostname)
        object_type = 'Host'

        if servicename != "":
            object_type = 'Service'
            filters += '&&service.name=="{}"'.format(servicename)

        body = {
            'filter': filters,
            "type": object_type,
            "author": self.username,
            "comment": comment_text
        }

        res = self._post("/v1/actions/add-comment", body)
        return res


    def delete_comments_icinga(self, comments):
        '''Delete icinga comments associated with the current user and service/host'''
        for comment in comments:
            if comment['attrs']['author'] == self.username:
                url = f"/v1/actions/remove-comment?comment={comment['attrs']['__name']}"
                res = self._post(url)
                logger.debug(json.dumps(res.text))
        return


def parse_rt_field(field_data):
    '''Adds padding to multi-line RT Field data (Required by RT REST API)'''
    result = ""
    for line in field_data.splitlines(True):
        result += ("  " + line)

    return result

config = Settings()
config.rt = SettingsRT(_config_dict=config._config_dict)
config.icinga = SettingsIcinga(_config_dict=config._config_dict)

icinga = Icinga(base_url=config.icinga.url, username=config.icinga.username, password=config.icinga.password)

# Init logging
if config.debug:
    initLogger(log_level='DEBUG', log_file="/var/log/icinga2/notification-request-tracker.log")
else:
    initLogger(log_level='INFO', log_file="/var/log/icinga2/notification-request-tracker.log")

if config.print_config:
    logger.debug(json.dumps(dataclasses.asdict(config), indent=2))
    config.printArguments()
    config.printEnvironmentVars()
    sys.exit(0)

logger.info(dataclasses.asdict(config))

authenticate_rt()

COMMENTS = icinga.get_comments_icinga(config.host_name, config.service_name)

if not COMMENTS:
    TICKET_ID = None
else:
    # extract id from comment
    TICKET_ID = TICKETID_REGEX.search(COMMENTS[0]['attrs']['text']).group(2)

if config.notification_type != "ACKNOWLEDGEMENT":
    if config.service_state == "CRITICAL" or config.service_state == "DOWN":
        print("Service/host went down")
        if TICKET_ID is None:
            print("Create RT ticket and comment ID")

            RT_ID = create_ticket_rt(
                "{} {} went {}".format(config.host_displayname, config.service_displayname, config.service_state))
            icinga.add_comment_icinga(
                config.host_name,
                config.service_name,
                f'[{config.rt.name} #{str(RT_ID)}] - ticket created in RT')
        else:
            print("Get comment and comment on RT")
            add_comment_rt(TICKET_ID)
    elif config.host_state == "OK" or config.host_state == "UP":
        print("Server/host back up")
        add_comment_rt(TICKET_ID)
        set_subject_recovered_rt(TICKET_ID)
        set_status_rt(TICKET_ID)
        icinga.delete_comments_icinga(COMMENTS)
else:
    print("Someone acknowledged the problem")
    add_comment_rt(TICKET_ID,)
