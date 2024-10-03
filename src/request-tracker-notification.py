#!/usr/bin/env python3
'''Icinga2 plugin to create and track RT tickets when services and hosts go critical'''

import dataclasses
import json
import os
import re
import requests
import sys
import traceback

from rt.rest2 import Rt

from lib.SettingsParser import SettingsParser
from lib.Util import initLogger
from lib.IcingaUtil import getSettingsParserArgumentsDict, DirectorBasketNotificationCommand, DEFAULT_ARGS


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

    config_file: str = f'{os.path.realpath(os.path.dirname(__file__))}/config/request-tracker-notification.json'
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
    build_config: bool = False

    def __post_init__(self):
        try:
            self._exclude_from_args.extend(self._exclude_all)
            self._exclude_from_env.extend(self._exclude_all + ['print_config'])
            self._env_prefix = "NOTIFY_RT_"
            self.loadEnvironmentVars()
            self._args = self._init_args('Icinga2 plugin to create and update Request Tracker tickets', DEFAULT_ARGS)
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


class Icinga:
    def __init__(self, username, password, base_url):
        self.username = username
        self.password = password
        self.base_url = base_url

    def _get(self, url_path, payload):
        logger.debug(f'Icinga GET Request for url {self.base_url + url_path}')
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
            logger.error(f"Icinga GET Request to {self.base_url + url_path} failed with error {e}")

    def _post(self, url_path, payload = None):
        logger.debug(f'Icinga POST Request for url {self.base_url + url_path}')
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
            logger.error(f"Icinga POST Request to {self.base_url + url_path} with payload {payload} failed with error {e}")

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
        logger.debug(f'Adding Icinga comment for host {hostname}, service {servicename} with text {comment_text}')
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


class RequestTracker:
    def __init__(self) -> None:
        self.rt = None
        self.ticket_id = None
        self._initRT()

    def _initRT(self):
        if config.rt.proxy:
            self.rt = Rt(url=f"{config.rt.url}/REST/2.0/", http_auth=requests.auth.HTTPBasicAuth(config.rt.username, config.rt.password), proxy=config.rt.proxy)
        else:
            self.rt = Rt(url=f"{config.rt.url}/REST/2.0/", http_auth=requests.auth.HTTPBasicAuth(config.rt.username, config.rt.password))
        logger.debug(f"Initalized rt {self.rt}")

    def ticketMessage(self):
        additional_output = self.parseMultiLineField(f"{config.service_output}{config.host_output}")
        state = f"{config.service_state}{config.host_state}"

        message = f"Notification Type: {config.notification_type}\n \n"
        message += f" Service: {config.service_displayname}\n"
        message += f" Host: {config.host_displayname}\n"
        message += f" Address: {config.host_address}\n"
        message += f" State: {state}\n \n"
        message += f" Additional Info: {additional_output}\n \n"
        message += f" Comment: [{config.notification_author}] {config.notification_comment}\n"

        logger.debug(f"Ticket message\n{message}")
        return message

    def parseMultiLineField(self, field_data):
        '''Adds padding to multi-line RT Field data (Required by RT REST API)'''
        result = ""
        for line in field_data.splitlines(True):
            result += ("  " + line)
        return result

    def setTicket(self, rt_id):
        rt_id = str(rt_id).replace("#", "")
        if rt_id is not None and rt_id and rt_id.isnumeric():
            self.ticket_id = rt_id
            logger.info(f"Ticket ID set to {self.ticket_id}")

    def createTicket(self, subject):
        logger.debug(f"Creating RT ticket with subject {subject}")
        '''Creates a ticket in RT and returns the ticket ID'''
        result = None
        try:
            result = self.rt.create_ticket(
                queue=config.rt_queue, 
                subject=subject, 
                content=self.ticketMessage(),
                requestor=[config.rt_requestor]
                )
            self.setTicket(result)
        except Exception as e:
            logger.error(f"Error creating ticket {e}")
        logger.debug(result)

    def commentTicket(self, message = None):
        logger.debug(f"Adding RT comment to {self.ticket_id}")
        '''Add a comment to an existing RT ticket'''
        text = self.ticketMessage()
        if message is not None:
            text = f"{text}\n{self.parseMultiLineField(message)}"
        if self.ticket_id is not None:
            try:
                self.rt.comment(ticket_id=self.ticket_id, content=self.ticketMessage())
            except Exception as e:
                logger.error(f"Error adding comment to existing ticket {self.ticket_id}: {e}")
        else:
            logger.warning("Can't comment on ticket without valid ticket number")
        
            
    def editTicketSubject(self, subject, status="open"):
        logger.debug(f"Editing ticket {self.ticket_id}")
        if self.ticket_id is not None:
            try:
                self.rt.edit_ticket(
                    ticket_id=self.ticket_id, 
                    Subject=subject,
                    Status=status
                    )
                
            except Exception as e:
                logger.error(f"Error editing existing ticket {self.ticket_id}: {e}")
        else:
            logger.warning("Can't edit on ticket without valid ticket number")

config = Settings()
config.rt = SettingsRT(_config_dict=config._config_dict)
config.icinga = SettingsIcinga(_config_dict=config._config_dict)

# I should have commented this 
if not config.rt_queue:
    config.rt_queue = config.rt.queue

# Init logging
if config.debug:
    initLogger(log_level='DEBUG', log_file="/var/log/icinga2/notification-request-tracker.log")
else:
    initLogger(log_level='INFO', log_file="/var/log/icinga2/notification-request-tracker.log")

if config.build_config:
    args = getSettingsParserArgumentsDict(config)
    basket = DirectorBasketNotificationCommand("Request Tracker", command="/etc/icinga2/scripts/request-tracker-notification.py", icinga_var_prefix="rt_notification", args=args, id=1140)
    with open('director_baskets/request-tracker-notification-basket.json', 'w') as _file:
        json.dump(basket.director_basket, _file, indent=4)
    logger.debug(basket.director_basket)
    sys.exit(0)


if config.print_config:
    logger.debug(json.dumps(dataclasses.asdict(config), indent=2))
    config.printArguments()
    config.printEnvironmentVars()
    sys.exit(0)

rt = RequestTracker()

# Init Icinga
icinga = Icinga(base_url=config.icinga.url, username=config.icinga.username, password=config.icinga.password)


logger.info(dataclasses.asdict(config))

comments = icinga.get_comments_icinga(config.host_name, config.service_name)

logger.debug(f"Comments: {comments}")

if comments:
    # extract id from comment
    rt.setTicket(TICKETID_REGEX.search(comments[0]['attrs']['text']).group(2))

if config.notification_type != "ACKNOWLEDGEMENT":
    if config.service_state == "CRITICAL" or config.host_state == "DOWN":
        logger.info(f"Host: {config.host_name}, Service: {config.service_name} went down")
        # No existing comments
        if rt.ticket_id is None:
            logger.info("Creating new RT ticket and comment ID")

            rt.createTicket(f"{config.host_displayname} {config.service_displayname} went {config.host_state}{config.service_state}")
            if rt.ticket_id is not None:
                icinga.add_comment_icinga(
                    config.host_name,
                    config.service_name,
                    f'[{config.rt.name} #{str(rt.ticket_id)}] - ticket created in RT')
            else:
                logger.warning(f"Didn't get valid Ticket for {config.host_displayname} {config.service_displayname} went {config.host_state}{config.service_state}, icinga comment skipped")
        else:
            logger.info("Get comment and comment on RT")
            rt.commentTicket()
    elif config.service_state == "OK" or config.host_state == "UP":
        logger.info(f"Host: {config.host_name}, Service: {config.service_name} back up")
        rt.commentTicket()
        rt.editTicketSubject(f"RECOVERED - {config.host_displayname} {config.service_displayname} went {config.host_state}{config.service_state}")
        icinga.delete_comments_icinga(comments)
    else:
        logger.info(f"Doing nothing becuase the service state ({config.service_state}) isn't CRITICAL or DOWN and the host state ({config.host_state}) isn't OK or UP")
else:
    logger.info(f"Author {config.notification_author} acknowledged the problem")
    rt.commentTicket(f"Author {config.notification_author} acknowledged the problem")
