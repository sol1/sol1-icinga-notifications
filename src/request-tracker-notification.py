#!/usr/bin/env python3
'''Icinga2 plugin to create and track RT tickets when services and hosts go critical'''

import os
import sys
import re
import json
import argparse
import traceback

import dataclasses
from lib.SettingsParser import SettingsParser
from loguru import logger

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


RT_REGEX = re.compile(r'(# Ticket )(\w+)( created)')
TICKETID_REGEX = re.compile(r'(#)([0-9]+)(\])')
SESSION = requests.session()

@dataclasses.dataclass
class Settings(SettingsParser):
    rt_name: str = 'rtInstance'
    rt_addr: str = 'https://rt.example.com'
    rt_user: str = 'rtbot'
    rt_pass: str = ''
    icinga_addr: str = 'https://localhost:5665'
    icinga_user: str = 'rtnotify'
    icinga_pass: str = ''
    host_name: str = None
    host_displayname: str = None
    host_address: str = None
    host_state: str = None
    host_output: str = None
    service_name: str = None
    service_displayname: str = None
    service_state: str = None
    service_output: str = None
    notification_auth_name: str = None
    notification_comment: str = None
    notification_type: str = None
    # log stuff can only be in the config file
    log_file: str = '/var/log/icinga2/notify_rt.log'
    log_disable: bool = False
    log_rotate: str = '1 day'
    log_retention: str = '1 week'
    # can only debug from command line, easier to see if it is left on
    debug: bool = False
    print_config: bool = False

    def __post_init__(self):
        try:
            self._env_prefix: str = "NOTIFY_RT_"
            self.config_file = '/etc/icinga2/scripts/notify_rt.json'
            self._exclude_from_args = [
                'log_file', 'log_disable', 'log_rotate', 'log_retention']
            self._exclude_from_file = ['debug', 'print_config']
            self._exclude_from_env = [
                'debug', 'log_file', 'log_disable', 'log_rotate', 'log_retention', 'print_config']

            args = self.__initArgs()
            self.loadArgs(args)
            # self.loadConfigFile()
            self.loadEnvironmentVars()
        except Exception as e:
            print("Failed to initialize {e}")
            print(traceback.format_exc())
            sys.exit()

    def __initArgs(self):
        parser = argparse.ArgumentParser(
            description='Icinga2 plugin to create and track RT tickets when services and hosts go critical')
        for key, value in dataclasses.asdict(self).items():
            # if 'log_' in key:
            #     continue
            if type(key) == bool:
                parser.add_argument(f'--{key}', action="store_true")
            else:
                parser.add_argument(
                    f'--{key}', type=type(key), help='', default=f'{value}')
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


def authenticate_rt(username, password):
    '''Authenticates with the RT server for all subsequent requests'''
    SESSION.post(config.rt_addr, data={
                 "user": config.rt_user, "pass": config.rt_pass})


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
    ticket_data += "Requestor: {}\n".format(config.requestor)
    ticket_data += "Subject: {}\n".format(subject)
    ticket_data += "Text: {}".format(message)

    res = SESSION.post(
        config.rt_addr + "/REST/1.0/ticket/new",
        data={"content": ticket_data},
        headers=dict(Referer=config.rt_addr))

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
        config.rt_addr + "/REST/1.0/ticket/{id}/comment".format(
            id=ticket_id),
        data={"content": ticket_data},
        headers=dict(Referer=config.rt_addr))

    return


def set_status_rt(ticket_id, status="open"):
    '''Set rt ticket status'''

    ticket_data = "Status: {}\n".format(status)

    SESSION.post(
        config.rt_addr + "/REST/1.0/ticket/{id}/edit".format(
            id=ticket_id),
        data={"content": ticket_data},
        headers=dict(Referer=config.rt_addr))

    return


def set_subject_recovered_rt(ticket_id):
    '''Set rt ticket subject'''

    subject = "{} {} - Recovered".format(config.host, config.service)

    ticket_data = "Subject: {}\n".format(subject)

    SESSION.post(
        config.rt_addr + "/REST/1.0/ticket/{id}/edit".format(
            id=ticket_id),
        data={"content": ticket_data},
        headers=dict(Referer=config.rt_addr))

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

    def _post(self, url_path, payload):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8'
        }

        return SESSION.post(
            self.base_url + url_path,
            auth=(self.username, self.password),
            verify=False,
            headers=headers,
            json=payload
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
                url = "/v1/actions/remove-comment?comment={}".format(
                    comment['attrs']['__name'])

                res = SESSION.post(
                    config.icinga_addr + url,
                    auth=(username, password),
                    verify=False,
                    headers=headers)

                logger.debug(json.dumps(res.text))

        return


def parse_rt_field(field_data):
    '''Adds padding to multi-line RT Field data (Required by RT REST API)'''
    result = ""
    for line in field_data.splitlines(True):
        result += ("  " + line)

    return result


def initLogger():
    format = "<blue>{time:YYYY-MM-DD HH:mm:ss.SSS}</blue> <level>{level}</level>: {message}",
    level = "INFO"
    if config.debug:
        format = "<blue>{time:YYYY-MM-DD HH:mm:ss.SSS}</blue> <cyan>{function}</cyan>:<cyan>{line}</cyan> <level>{level}</level>: {message}",
        level = "DEBUG"
    else:
        logger.remove()
    if not config.log_disable:
        logger.add(config.log_file,
                   colorize=True,
                   format=format,
                   level=level,
                   rotation=config.log_rotate,
                   retention=config.log_retention,
                   compression="gz"
                   )


config = Settings()
initLogger()
if config.print_config:
    config.printArguments
    config.printEnvironmentVars
    sys.exit(0)

logger.info(dataclasses.asdict(config))

authenticate_rt()

COMMENTS = get_comments_icinga(
    config.icinga_user,
    config.icinga_pass,
    config.host,
    config.service)

if not COMMENTS:
    TICKET_ID = None
else:
    # extract id from comment
    TICKET_ID = TICKETID_REGEX.search(COMMENTS[0]['attrs']['text']).group(2)

if config.type != "ACKNOWLEDGEMENT":
    if config.state == "CRITICAL" or config.state == "DOWN":
        print("Service/host went down")
        if TICKET_ID is None:
            print("Create RT ticket and comment ID")

            RT_ID = create_ticket_rt(
                "{} {} went {}".format(config.host, config.service, config.state))
            add_comment_icinga(
                config.icinga_user,
                config.icinga_pass,
                config.host,
                config.service,
                '[{} #{}] - ticket created in RT'.format(config.rt_name, str(RT_ID)))
        else:
            print("Get comment and comment on RT")
            add_comment_rt(TICKET_ID)
    elif config.state == "OK" or config.state == "UP":
        print("Server/host back up")
        add_comment_rt(TICKET_ID)
        set_subject_recovered_rt(TICKET_ID)
        set_status_rt(TICKET_ID)
        delete_comments_icinga(
            config.icinga_user,
            config.icinga_pass,
            COMMENTS)
else:
    print("Someone acknowledged the problem")
    add_comment_rt(TICKET_ID,)
