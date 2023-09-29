#!/usr/bin/env python3

import argparse
import dataclasses
import json
import requests
import sys
import traceback
import urllib.parse

from lib.SettingsParser import SettingsParser
from lib.Util import initLogger

from loguru import logger

# Helper to load config from file
@dataclasses.dataclass
class SettingsFile(SettingsParser):
    def __post_init__(self):
        self.loadConfigDict()

@dataclasses.dataclass
class SettingsNetbox(SettingsFile):
    # INFO: leave netbox base empty if you don't use netbox and it won't be included
    # INFO: no trailing / on the url. eg: http://netbox.domain.local
    url: str = ''
    token: str = 'abcdefghijklmnopqrstuvwxyz1234567890'
    proxy: str = ''
    timeout: str = 20
    _json_dict_key: str = 'netbox'

@dataclasses.dataclass
class Settings(SettingsParser):
    netbox: object = None
    _exclude_all: list = dataclasses.field(default_factory=lambda: ['netbox'])

    # config_file: str = 'config/slack-notification.json'
    debug: bool = False
    disable_log_file: bool = False

    host_name: str = ''
    host_displayname: str = ''
    host_address: str = ''
    host_state: str = ''
    host_state_last: str = ''
    host_output: str = ''
    service_name: str = ''
    service_displayname: str = ''
    service_state: str = ''
    service_state_last: str = ''
    service_output: str = ''
    notification_author: str = ''
    notification_comment: str = ''
    notification_type: str = ''

    sms_provider: str = ''
    sms_number: str = ''

    print_config: bool = False

    def __post_init__(self):
        try:
            self._exclude_from_args.extend(self._exclude_all)
            self._exclude_from_env.extend(self._exclude_all + ['print_config'])
            self._env_prefix = "NOTIFY_NETBOX_PATH_IMPACT_"
            self.loadEnvironmentVars()
            self._args = self._init_args()
            self.loadArgs(self._args)

            # Debug set in the config file will override the args
            self._include_from_file = ['debug', 'disable_log_file']
            self.loadConfigJsonFile()

        except Exception as e:
            print("Failed to initialize {e}")
            print(traceback.format_exc())
            sys.exit()

    def _init_args(self):
        parser = argparse.ArgumentParser(description='Icinga2 plugin to send slack notifications')
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


class Netbox:
    def __init__(self) -> None:
        self.headers = {
            'Content-Type': 'application/json'
        }

class SMS:
    def __init__(self, token, url) -> None:
        self.token = token
        self.url = url

    # knows how to send bob sms
    def bobSMS(self):
        requests.post(url=config.sms.url, headers=config.sms.token, payload=config.sms_number)


if __name__ == "__main__":
    config = Settings()
    config.netbox = SettingsNetbox(_config_dict=config._config_dict)
 

    if config.print_config:
        logger.debug(json.dumps(dataclasses.asdict(config), indent=2))
        config.printArguments()
        config.printEnvironmentVars()
        sys.exit(0)

    # Init logging
    if config.debug:
        initLogger(log_level='DEBUG', log_file="/var/log/icinga2/notification-netbox-path.log")
    else:
        initLogger(log_level='INFO', log_file="/var/log/icinga2/notification-netbox-path.log")

    logger.debug(json.dumps(dataclasses.asdict(config), indent=2))

    netbox = Netbox()
    sms = SMS()
    sms.bobSMS()
    # Do stuff kinda, make the class do the work
