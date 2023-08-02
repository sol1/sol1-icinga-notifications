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
    proxy: str = ''
    timeout: str = 20
    _json_dict_key: str = 'rt'

@dataclasses.dataclass
class SettingsIcinga(SettingsFile):
    url: str = 'https://localhost:5665'
    username: str = 'rtnotify'
    password: str = ''
    proxy: str = ''
    timeout: str = 20
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

def _postRT(url, headers = None, data = None):
    args = {
        'url': url,
        'timeout': config.rt.timeout
        }
    if headers is not None:
        args['headers'] = headers
    if data is not None:
        args['data'] = data
    if config.rt.proxy:
        args['proxies'] = {'http': config.rt.proxy, 'https': config.rt.proxy}
    try:
        logger.debug(f"request args: {args}")
        response = SESSION.post(**args)
        return response
    except Exception as e:
        logger.error(f'RT POST to {url} failed with {e}')
        return None    

def authenticate_rt():
    logger.debug(f"Auth RT with user {config.rt.username}")
    '''Authenticates with the RT server for all subsequent requests'''
    result = _postRT(url=config.rt.url, data={"user": config.rt.username, "pass": config.rt.password})
    logger.debug(f'Auth RT request status code: {result.status_code}')


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
        config.notification_author,
        config.notification_comment)
    logger.debug(f"Ticket message\n{message}")
    return message


def create_ticket_rt(subject):
    logger.debug(f"Creating RT ticket with subject {subject}")
    '''Creates a ticket in RT and returns the ticket ID'''

    message = create_ticket_message()

    ticket_data = "id: ticket/new\n"
    ticket_data += f"Queue: {config.rt_queue}\n"
    ticket_data += f"Requestor: {config.rt_requestor}\n"
    ticket_data += f"Subject: {subject}\n"
    ticket_data += f"Text: {message}"

    logger.debug(ticket_data)

    result = _postRT(
        url = f"{config.rt.url}/REST/1.0/ticket/new",
        data = {"content": ticket_data},
        headers = dict(Referer=config.rt.url)
        )
    
    logger.info(f"Message: {message}")
    logger.info(f"Response: {result.text}")

    return RT_REGEX.search(result.text).group(2)


def add_comment_rt(ticket_id):
    logger.debug(f"Adding RT comment {ticket_id}")
    '''Add a comment to an existing RT ticket'''

    message = create_ticket_message()
    ticket_data = "id: {id}\n".format(id=ticket_id)
    ticket_data += "Action: comment\n"
    ticket_data += "Text: {text}".format(text=message)

    logger.debug(ticket_data)

    result = _postRT(
        url = f"{config.rt.url}/REST/1.0/ticket/{ticket_id}/comment",
        data={"content": ticket_data},
        headers=dict(Referer=config.rt.url)
        )
 
    if result is not None:
        logger.debug(f'Adding RT comment request status code: {result.status_code}, text: {result.text}')
    else:
        logger.info("Failed to add comment to existing ticket, no response from request")
    return


def set_status_rt(ticket_id, status="open"):
    logger.debug(f"Setting RT status for {ticket_id} to {status}")
    '''Set rt ticket status'''

    ticket_data = "Status: {}\n".format(status)

    try:
        result = _postRT(
            url = f"{config.rt.url}/REST/1.0/ticket/{ticket_id}/edit",
            data={"content": ticket_data},
            headers=dict(Referer=config.rt.url),
            )
    except Exception as e:
        logger.error(f'Setting RT status failed with {e}')    

    if result is not None:
        logger.debug(f'Setting RT status request status code: {result.status_code}, text: {result.text}')
    else:
        logger.info("Failed to set RT status to existing ticket, no response from request")
    return


def set_subject_recovered_rt(ticket_id):
    logger.debug(f"Setting RT subject for {ticket_id}")
    '''Set rt ticket subject'''

    subject = "{} {} - Recovered".format(config.host_displayname, config.service_displayname)

    ticket_data = "Subject: {}\n".format(subject)

    try:
        result = _postRT(
            url = f"{config.rt.url}/REST/1.0/ticket/{id}/edit",
            data={"content": ticket_data},
            headers=dict(Referer=config.rt.url)
            )
    except Exception as e:
        logger.error(f'Creating RT ticket failed with {e}')    

    if result is not None:
        logger.debug(f'Setting RT subject request status code: {result.status_code}, text: {result.text}')
    else:
        logger.info("Failed to set RT subject to existing ticket, no response from request")
    return

class Icinga:
    def __init__(self, username, password, base_url):
        self.username = username
        self.password = password
        self.base_url = base_url

    def _get(self, url_path, payload):
        logger.debug(f'Request GET for url {self.base_url + url_path}')
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8'
        }
        try:
            result = SESSION.get(
                self.base_url + url_path,
                auth=(self.username, self.password),
                verify=False,
                headers=headers,
                json=payload,
                timeout=20
                )
            return result
        except Exception as e:
            logger.error(f"Icinga GET to {self.base_url + url_path} failed with error {e}")

    def _post(self, url_path, payload = None):
        logger.debug(f'Request POST for url {self.base_url + url_path}')
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8'
        }

        try:
            if payload:
                result = SESSION.post(
                    self.base_url + url_path,
                    auth=(self.username, self.password),
                    verify=False,
                    headers=headers,
                    json=payload,
                    timeout=15
                    )
            else:
                result = SESSION.post(
                            self.base_url + url_path,
                            auth=(self.username, self.password),
                            verify=False,
                            headers=headers
                            )
            return result
        except Exception as e:
            logger.error(f"Icinga POST to {self.base_url + url_path} with payload {payload} failed with error {e}")

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
        logger.debug(f'Assing comment for host {hostname}, service {servicename} with text {comment_text}')
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

if not config.rt_queue:
    config.rt_queue = config.rt.queue

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

comments = icinga.get_comments_icinga(config.host_name, config.service_name)

logger.debug(f"Comments: {comments}")

if not comments:
    ticket_id = None
else:
    # extract id from comment
    ticket_id = TICKETID_REGEX.search(comments[0]['attrs']['text']).group(2)

logger.info(f"Ticket ID: {ticket_id}")

if config.notification_type != "ACKNOWLEDGEMENT":
    if config.service_state == "CRITICAL" or config.host_state == "DOWN":
        logger.info(f"Host: {config.host_name}, Service: {config.service_name} went down")
        if ticket_id is None:
            logger.info("Creating new RT ticket and comment ID")

            rt_id = create_ticket_rt(
                f"{config.host_displayname} {config.service_displayname} went {config.host_state}{config.service_state}")
            icinga.add_comment_icinga(
                config.host_name,
                config.service_name,
                f'[{config.rt.name} #{str(rt_id)}] - ticket created in RT')
        else:
            logger.info("Get comment and comment on RT")
            add_comment_rt(ticket_id)
    elif config.service_state == "OK" or config.host_state == "UP":
        logger.info(f"Host: {config.host_name}, Service: {config.service_name} back up")
        add_comment_rt(ticket_id)
        set_subject_recovered_rt(ticket_id)
        set_status_rt(ticket_id)
        icinga.delete_comments_icinga(comments)
    else:
        logger.info(f"Doing nothing becuase the service state ({config.service_state}) isn't CRITICAL or DOWN and the host state ({config.host_state}) isn't OK or UP")
else:
    logger.info(f"Author {config.notification_author} acknowledged the problem")
    add_comment_rt(ticket_id,)
