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
import pynetbox

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
    api_device: str = ''
    api_vm: str = ''
    api_impact: str = ''
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
    """Netbox object that parses data from the Netbox api
    all ivars are intialized as empty and filled if valid data is found for each type

    :ivar host: dict : api data to the host for the NETBOXBASE and host_name
    :ivar host_url: str : url to the host for the NETBOXBASE and host_name
    :ivar ip: dict : api data to the host ip address for the NETBOXBASE and host_name
    :ivar ip_url: str : url to the host ip address for the NETBOXBASE and host_name
    """

    def __init__(self, config):
        self.config = config
        self.host = {}
        self.host_url = ''
        self.ip_url = ''
        self.type = ''
        logger.debug(f"Initalizing the Netbox class with host: {self.config.host_name}, netbox url: {self.config.netbox.url}")

        if self.config.netbox:
            self.__parse()

    def __parse(self):
        """ Search netbox for

        :return:
        """
        nb_device = self.__searchData(self.config.netbox.url + self.config.netbox.api_device + '/?name=' + self.config.host_name)
        nb_vm = self.__searchData(self.config.netbox.url + self.config.netbox.api_vm + '/?name=' + self.config.host_name)

        logger.debug(json.dumps(nb_device, indent=4, sort_keys=True))
        logger.debug(json.dumps(dict(nb_vm), indent=4, sort_keys=True))
        if nb_device and not nb_vm:
            self.host = nb_device
            self.type = self.config.netbox.api_device.split('/api')[1].replace('/', '.')
            self.host_url = "{}/{}/".format(self.config.netbox.url + self.config.netbox.api_device, nb_device['id'])
        elif not nb_device and nb_vm:
            self.host = nb_vm
            self.type = self.config.netbox.api_vm.split('/api/')[1].replace('/', '.')
            self.host_url = "{}/{}/".format(self.config.netbox.url + self.config.netbox.api_vm, nb_vm['id'])
        elif nb_device and nb_vm:
            logger.info("Found multiple device's or vm's that match")
        else:
            logger.warning("Found no device's or vm's that match")

    def getImpactAssessment(self):
        args = {
            'url': f'{self.config.netbox.url}{self.config.netbox.api_impact}',
            'params': { 'id': self.host['id'], 'type': self.type },
            'timeout': self.config.netbox.timeout,
            'headers': {'Accept': 'application/json'}
        }
        if self.config.netbox.proxy:
            args['proxies'] = {'http': self.config.netbox.proxy, 'https': self.config.netbox.proxy}

        if self.config.netbox.token:
            args['headers'].update({'Authorization': 'Token ' + self.config.netbox.token})

        try:
            logger.debug(f"Netbox request to url: {args['url']}")
            response = requests.get(**args)
            result = response.json()
        except Exception as e:
            logger.error("Error getting netbox data from {} with error {}".format(args['url'], e))
            result = {'count': 0}
        logger.debug(f"Netbox result: {result}")
        return result

    def __getServerData(self, url):
        args = {
            'url': url,
            'timeout': self.config.netbox.timeout,
            'headers': {'Accept': 'application/json'}
        }
        if self.config.netbox.proxy:
            args['proxies'] = {'http': self.config.netbox.proxy, 'https': self.config.netbox.proxy}

        if self.config.netbox.token:
            args['headers'].update({'Authorization': 'Token ' + self.config.netbox.token})
        try:
            logger.debug(f"Netbox request to url: {url}")
            response = requests.get(**args)
            result = response.json()
        except Exception as e:
            logger.error("Error getting netbox data from {} with error {}".format(url, e))
            result = {'count': 0}
        logger.debug(f"Netbox result: {result}")
        return result

    def __searchData(self, url):
        result = self.__getServerData(url)
        if result['count'] == 1 and result['results']:
            return result['results'][0]
        else:
            return {}

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

    netbox = Netbox(config)
    impacted_paths = netbox.getImpactAssessment()

    for path in impacted_paths:
        logger.info(f"Path: {path['name']}")
        for contact in path['contacts']:
            logger.info(f"Contact: {contact['name']}")
            logger.info(f"Email: {contact['email']}")
            logger.info(f"Phone: {contact['phone']}")
        for object in path['objects']:
            if len(object['direction']) == 0:
                logger.info(f"Object: {object['name']} - {object['type']} - {object['description']}")
        

    #sms = SMS()
    #sms.bobSMS()
    # Do stuff kinda, make the class do the work
