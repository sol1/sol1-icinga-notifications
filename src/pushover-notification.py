#!/usr/bin/env python3


import argparse
import dataclasses
import json
import requests
import sys
import traceback
import textwrap

from lib.SettingsParser import SettingsParser
from lib.Util import initLogger

from loguru import logger


@dataclasses.dataclass
class Settings(SettingsParser):
    _exclude_all: list = dataclasses.field(default_factory=lambda: ['config_file'])

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
    notification_date_time: str = ''

    pushover_token: str = ''
    pushover_user: str = ''

    print_config: bool = False

    def __post_init__(self):
        try:
            self._exclude_from_args.extend(self._exclude_all)
            self._exclude_from_env.extend(self._exclude_all + ['print_config'])
            self._env_prefix = "NOTIFY_PUSHOVER_"
            self.loadEnvironmentVars()
            self._args = self._init_args()
            self.loadArgs(self._args)

        except Exception as e:
            print("Failed to initialize {e}")
            print(traceback.format_exc())
            sys.exit()

    def _init_args(self):
        parser = argparse.ArgumentParser(description='Icinga2 plugin to send pushover notifications')
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

def send_notification(token, user, message):
    url = "https://api.pushover.net/1/messages.json"
    headers = {
        "Content-type": "application/x-www-form-urlencoded",
    }
    payload = {
        "token": token,
        "user": user,
        "message": message,
    }

    logger.debug(f"Sending to {user} message: {message}")
    response = requests.post(url, data=payload, headers=headers)

    if response.status_code != 200:
        logger.error(f"Failed to send notification for token: {token}, user: {user}, response ({response.status_code}): {response.text}")
        raise Exception(f"Failed to send notification: {response.text}")


if __name__ == "__main__":
    config = Settings()

    if config.print_config:
        logger.debug(json.dumps(dataclasses.asdict(config), indent=2))
        config.printArguments()
        config.printEnvironmentVars()
        sys.exit(0)

    # Init logging
    if config.debug:
        initLogger(log_level='DEBUG', log_file="/var/log/icinga2/notification-pushover.log")
    else:
        initLogger(log_level='INFO', log_file="/var/log/icinga2/notification-pushover.log")

    logger.debug(json.dumps(dataclasses.asdict(config), indent=2))

    try:
        # Create the message
        if config.service_state:
            message=textwrap.dedent(f'''\
            {config.notification_type.title()}: {config.service_displayname} on {config.host_displayname}
            State: {config.service_state}
            Address: {config.host_address}

            Date/Time: {config.notification_date_time}
            Additional Info: {config.service_output}
            Comment: [{config.notification_author}] {config.notification_comment}
            ''')
        else:
            message=textwrap.dedent(f'''\
            {config.notification_type.title()}: {config.host_displayname}
            State: {config.host_state}
            Address: {config.host_address}

            Date/Time: {config.notification_date_time}
            Additional Info: {config.host_output}
            Comment: [{config.notification_author}] {config.notification_comment}
            ''')
    except Exception as e:
        logger.error(f"Message creation error: {e}")

    try:
        # Send the notification
        send_notification(config.pushover_token, config.pushover_user, message)

    except Exception as e:
        logger.error(f"Pushover send error: {e}")




