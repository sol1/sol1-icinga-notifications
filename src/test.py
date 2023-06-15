#!/usr/bin/env python3

import argparse
import dataclasses
import json

from lib.SettingsParser import SettingsParser

@dataclasses.dataclass
class SettingsFile(SettingsParser):
    def __post_init__(self):
        self.loadConfigFile()
        
@dataclasses.dataclass
class SettingsMail(SettingsFile):
    from_address: str = 'icinga@domain.local'
    server: str = 'localhost'
    username: str = ''
    password: str = ''
    _json_dict_key: str = 'mail'

@dataclasses.dataclass
class SettingsIcinga(SettingsFile):
    url: str = 'http://icinga.domain.local/icingaweb2'
    logo_path: str = '/usr/share/icingaweb2/public/img/icinga-logo.png'
    _json_dict_key: str = 'icinga'

@dataclasses.dataclass
class SettingsNetbox(SettingsFile):
    # eg: http://netbox.domain.local
    url = ''
    token = 'abcdefghijklmnopqrstuvwxyz1234567890'
    api_device = '/api/dcim/devices'
    api_vm = '/api/virtualization/virtual-machines'
    api_ip = '/api/ipam/ip-addresses'
    _json_dict_key: str = 'netbox'

@dataclasses.dataclass
class SettingsGrafana(SettingsFile):
    # INFO: no trailing / on the url, it can generate errors. eg: http://grafana.domain.local
    url = ''
    api_key = ''
    dashboard = 'icinga2-with-influxdb'
    # The grafana module in icingaweb2 stores panel id for each service in a ini file
    icingaweb2_ini = '/etc/icingaweb2/modules/grafana/graphs.ini'
    # This is the key that grafana users to search the host name value
    var_hostname = 'var-hostname'
    theme = 'light'
    default_panel_id = '2'  # Usually ping
    _json_dict_key: str = 'grafana'

@dataclasses.dataclass
class Settings(SettingsParser):
    mail: object = None
    icinga: object = None
    netbox: object = None
    grafana: object = None
    _exclude_all: list = dataclasses.field(default_factory=lambda: ['mail', 'icinga', 'netbox', 'grafana'])
    
    config_file: str = 'config/enhanced-mail-notification.json'
    debug: bool = False

    notification_type: str = ''
    host_alias: str = ''
    host_display_name: str = ''
    host_address: str = ''
    host_state: str = ''
    host_output: str = ''
    service_name: str = ''
    service_display_name: str = ''
    service_command: str = ''
    service_state: str = ''
    service_output: str = ''
    long_date_time: str = ''
    notification_author: str = ''
    notification_comment: str = ''
    email_to: str = ''
    performance_data: str = ''
    netbox_host_name: str = ''
    netbox_host_ip: str = ''
    grafana_host_name: str = ''
    grafana_panel_id: str = ''

    def __post_init__(self):
        self._exclude_from_args.extend(self._exclude_all)
        self._exclude_from_env.extend(self._exclude_all)
        self.loadEnvironmentVars()
        args = self._init_args()
        self.loadArgs(args)

        # Debug set in the config file will override the args
        self._include_from_file = ['debug']
        self.loadConfigFile()
        
        # Sensible defaults after loading everything
        if self.host_address == '':
            self.host_address = self.host_alias
        if self.netbox_host_name == '':
            self.netbox_host_name = self.host_alias
        if self.netbox_host_ip == '':
            self.netbox_host_ip = self.host_address
        if self.grafana_host_name == '':
            self.grafana_host_name = self.host_alias

        # Now get the config from file for other stuff because we have the config file from args, perhaps
        self.mail = SettingsMail(config_file=self.config_file)
        self.icinga = SettingsIcinga(config_file=self.config_file)
        self.netbox = SettingsNetbox(config_file=self.config_file)
        self.grafana = SettingsGrafana(config_file=self.config_file)


    def _init_args(self):
        parser = argparse.ArgumentParser(description='Icinga2 plugin to send enhanced email notifications with links to Grafana and Netbox')
        for arg in self._getArgVarList():
            if type(arg[2]) == bool:
                parser.add_argument(arg[1], action="store_true")
            else:
                parser.add_argument(arg[1], type=type(arg[2]), default=arg[2])
        return parser.parse_args()

config = Settings()
print(json.dumps(dataclasses.asdict(config), indent=4))
print(config.netbox.token)