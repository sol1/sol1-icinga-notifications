#!/usr/bin/env python3

import argparse
import dataclasses
import sys
import traceback
import requests
import json

from lib.SettingsParser import SettingsParser
from lib.Util import initLogger

from loguru import logger


@dataclasses.dataclass
class SettingsFile(SettingsParser):
    def __post_init__(self):
        self.loadConfigDict()


@dataclasses.dataclass
class SettingsSlack(SettingsFile):
    icingaweb2_url: str = ''
    webhook_url: str = ''
    botname: str = 'icinga2'
    _json_dict_key: str = 'slack'


@dataclasses.dataclass
class Settings(SettingsParser):
    slack: object = None
    icinga: object = None
    _exclude_all: list = dataclasses.field(default_factory=lambda: ['slack'])

    config_file: str = 'config/slack-notification.json'
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

    slack_channel: str = '#alerts'

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


class Slack:
    def __init__(self, channel) -> None:
        self.channel = channel
        self.headers = {
            'Content-Type': 'application/json'
        }

    @staticmethod
    def color(icinga_state, notification_type):
        if notification_type in ["ACKNOWLEDGEMENT", "DOWNTIMESTART", "DOWNTIMEEND"]:
            return "#7F7F7F"
        elif icinga_state == "CRITICAL":
            return "#FF5566"
        elif icinga_state == "WARNING":
            return "#FFAA44"
        elif icinga_state == "OK":
            return "#44BB77"
        elif icinga_state == "UNKNOWN":
            return "#800080"
        else:
            return ""

    def payload(self):
        state = config.host_state
        name = f"{config.host_displayname}"
        output = f"{config.host_output}"
        if config.service_state:
            state = config.service_state
            name = f"{config.host_displayname} - {config.service_displayname}"
            output = f"{config.service_output}"

        payload = {
            "channel": self.channel,
            "username": config.slack.botname,
            "attachments": [
                {
                    "fallback": f"{config.notification_type} - {state}: {name}",
                    "color": self.color(state, config.notification_type),
                    "fields": [
                        {
                            "title": "Type",
                            "value": config.notification_type,
                            "short": True
                        },
                        {
                            "title": "State",
                            "value": state,
                            "short": True
                        },
                        {
                            "title": "Host",
                            "value": f"<{config.slack.icingaweb2_url}/monitoring/host/services?host={config.host_name}|{config.host_displayname}>",
                            "short": True
                        },
                        {
                            "title": "Information",
                            "value": output,
                            "short": False
                        },
                    ]
                }
            ]
        }

        if config.service_state:
            payload['attachments'][0]['fields'].append({
                            "title": "Service",
                            "value": f"{config.slack.icingaweb2_url}/monitoring/service/show?host={config.host_name}&service={config.service_name}|{config.service_displayname}>",
                            "short": True
                        })
            
        logger.debug(payload)
        return payload

    def post(self):
        response = requests.post(url=config.slack.webhook_url, headers=self.headers, json=self.payload())
        if response.status_code not in [200,201,300,301]:
            logger.error(f"Post to slack url {config.slack.webhook_url} failed.\n Response code: {response.status_code}\n Response text: \n{response.text}")
        else:
            logger.success(f"Successfully posted to Slack")



if __name__ == "__main__":
    config = Settings()
    config.slack = SettingsSlack(_config_dict=config._config_dict)

    logger.debug(json.dumps(dataclasses.asdict(config), indent=2))

    # Init logging
    if config.debug:
        initLogger(log_level='DEBUG', log_file="/var/log/icinga2/notification-slack.log")
    else:
        initLogger(log_level='INFO', log_file="/var/log/icinga2/notification-slack.log")

    if config.print_config:
        logger.debug(json.dumps(dataclasses.asdict(config), indent=2))
        config.printArguments()
        config.printEnvironmentVars()
        sys.exit(0)

    slack = Slack(config.slack_channel)
    slack.post()
