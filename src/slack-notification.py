#!/usr/bin/env python3

import dataclasses
import json
import requests
import sys
import traceback
import urllib.parse

from lib.SettingsParser import SettingsParser
from lib.Util import initLogger

from datetime import datetime
from loguru import logger

from lib.IcingaUtil import getSettingsParserDict, DirectorBasketNotificationCommand, DEFAULT_ARGS


@dataclasses.dataclass
class Settings(SettingsParser):
    _exclude_all: list = dataclasses.field(default_factory=lambda: ['config_file'])

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

    slack_channel: str = '#alerts'
    slack_webhook_url: str = ''
    slack_botname: str = 'icinga2'
    slack_max_message_length: int = 1000
    icingaweb2_url: str = ''

    slack_layout_footer: bool = False
    slack_layout_host_and_service: bool = False

    print_config: bool = False
    build_config: bool = False

    def __post_init__(self):
        try:
            self._exclude_from_args.extend(self._exclude_all)
            self._exclude_from_env.extend(self._exclude_all + ['print_config'])
            self._env_prefix = "NOTIFY_SLACK_"
            self.loadEnvironmentVars()
            self._args = self._init_args('Icinga2 plugin to send slack notifications', DEFAULT_ARGS)
            self.loadArgs(self._args)

            # Sensible defaults after loading everything
            if self.host_address == '':
                self.host_address = self.host_displayname

        except Exception as e:
            print("Failed to initialize {e}")
            print(traceback.format_exc())
            sys.exit()

        self.icingaweb2_url = self.icingaweb2_url.rstrip('/')


class Slack:
    def __init__(self) -> None:
        self.headers = {
            'Content-Type': 'application/json'
        }

    @staticmethod
    def colors(icinga_state, notification_type):
        icinga_state = str(icinga_state).upper()
        if str(notification_type).upper() in ["ACKNOWLEDGEMENT", "DOWNTIMESTART", "DOWNTIMEEND"]:
            return ("#7F7F7F", "")
        elif icinga_state == "CRITICAL" or icinga_state == "DOWN":
            return ("#FF5566", ":red_circle: ")
        elif icinga_state == "WARNING":
            return ("#FFAA44", ":large_yellow_circle: ")
        elif icinga_state == "OK" or icinga_state == "UP":
            return ("#44BB77", ":large_green_circle: ")
        elif icinga_state == "UNKNOWN":
            return ("#800080")
        else:
            return ("", "")

    @classmethod
    def payload(cls):
        state = config.host_state
        state_last = config.host_state_last
        name = f"{config.host_displayname}"
        output = f"{config.host_output}"
        check_type = "Host"
        link = f"{config.icingaweb2_url}/icingaweb2/icingadb/host?name={urllib.parse.quote(config.host_name)}"
        if config.service_state:
            state = config.service_state
            state_last = config.service_state_last
            name = f"{config.host_displayname} - {config.service_displayname}"
            output = f"{config.service_output}"
            check_type = "Service"
            link = f"{config.icingaweb2_url}/icingaweb2/icingadb/service?host.name={urllib.parse.quote(config.host_name)}&name={urllib.parse.quote(config.service_name)}"
        (color, icon) = cls.colors(state, config.notification_type)
        logger.debug(
            f"color = {color}, icon = {icon} from state = {state}, notification_type = {config.notification_type})")

        update_string = f"is {state}"
        if (config.service_state == '' and config.host_state != config.host_state_last) or config.service_state != config.service_state_last:
            update_string = f"transitioned from {state_last} to {state}"

        payload = {
            "channel": config.slack_channel,
            "username": config.slack_botname,
            "attachments": [
                {
                    "fallback": f"{config.notification_type} - {state}: {name}",
                    "color": color,
                    "text": f"```{output[:config.slack_max_message_length]}```",
                    "title": f"{icon}{config.notification_type}: {check_type} <{link}|{name}> {update_string}",
                }
            ]
        }

        if config.slack_layout_footer:
            payload['attachments'][0]['footer'] = "Icinga Alerts"
            payload['attachments'][0]['ts'] = datetime.timestamp(datetime.now())

        if config.slack_layout_host_and_service:
            payload['attachments'][0]['fields'] = {
                "title": "Host",
                "value": f"<{config.icingaweb2_url}/icingaweb2/icingadb/host?name={urllib.parse.quote(config.host_name)}|{config.host_displayname}>",
                "short": True
            }

            if config.service_state:
                payload['attachments'][0]['fields'].append({
                    "title": "Service",
                    "value": f"<{link}|{config.service_displayname}>",
                    "short": True
                })

        logger.debug(payload)
        return payload

    def post(self):
        response = requests.post(url=config.slack_webhook_url, headers=self.headers, json=self.payload())
        if response.status_code not in [200, 201, 300, 301]:
            logger.error(
                f"Post to slack url {config.slack_webhook_url} failed.\n Response code: {response.status_code}\n Response text: \n{response.text}")
        else:
            logger.success(f"Successfully posted to Slack")


if __name__ == "__main__":
    config = Settings()

    if config.build_config:
        args = getSettingsParserDict(config)
        basket = DirectorBasketNotificationCommand("Slack", icinga_var_prefix="slack_notification", args=args, id=1160)
        with open('slack-notification-basket.json', 'w') as _file:
            json.dump(basket.director_basket, _file, indent=4)
        logger.debug(basket.director_basket)
        sys.exit(0)

    if config.print_config:
        logger.debug(json.dumps(dataclasses.asdict(config), indent=2))
        config.printArguments()
        config.printEnvironmentVars()
        sys.exit(0)

    # Init logging
    if config.debug:
        initLogger(log_level='DEBUG', log_file="/var/log/icinga2/notification-slack.log")
    else:
        initLogger(log_level='INFO', log_file="/var/log/icinga2/notification-slack.log")

    logger.debug(json.dumps(dataclasses.asdict(config), indent=2))

    slack = Slack()
    slack.post()
