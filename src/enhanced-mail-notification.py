#!/usr/bin/env python3
# ------------
# Host notification script for Icinga2
# v.20160504 by mmarodin
#
# https://github.com/mmarodin/icinga2-plugins
#
import argparse
import ConfigParser
import dataclasses
import json
import os
import re
import requests
import smtplib
import socket
import sys

from lib.SettingsParser import SettingsParser
from lib.Util import initLogger

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage
from loguru import logger
from jinja2 import Template

# Helper to load config from file
@dataclasses.dataclass
class SettingsFile(SettingsParser):
    def __post_init__(self):
        self.loadConfigDict()
        
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
    # INFO: leave netbox base empty if you don't use netbox and it won't be included
    # INFO: no trailing / on the url. eg: http://netbox.domain.local
    url: str = ''
    token: str = 'abcdefghijklmnopqrstuvwxyz1234567890'
    api_device: str = '/api/dcim/devices'
    api_vm: str = '/api/virtualization/virtual-machines'
    api_ip: str = '/api/ipam/ip-addresses'
    _json_dict_key: str = 'netbox'

@dataclasses.dataclass
class SettingsGrafana(SettingsFile):
    # INFO: no trailing / on the url, it can generate errors. eg: http://grafana.domain.local
    url: str = ''
    api_key: str = ''
    dashboard: str = 'icinga2-with-influxdb'
    # The grafana module in icingaweb2 stores panel id for each service in a ini file
    icingaweb2_ini: str = '/etc/icingaweb2/modules/grafana/graphs.ini'
    # This is the key that grafana users to search the host name value
    var_hostname: str = 'var-hostname'
    theme: str = 'light'
    default_panel_id: str = '2'  # Usually ping
    image_height: str = '321'
    image_width: str = '640'
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
    disable_log_file: bool = False

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

    table_width: str = '640'
    column_width: str = '144'

    print_config: bool = False

    def __post_init__(self):
        self._exclude_from_args.extend(self._exclude_all)
        self._exclude_from_env.extend(self._exclude_all + ['print_config'])
        self._env_prefix = "NOTIFY_ENHANCED_MAIL_"
        self.loadEnvironmentVars()
        args = self._init_args()
        self.loadArgs(args)

        # Debug set in the config file will override the args
        self._include_from_file = ['debug', 'disable_log_file']
        self.loadConfigJsonFile()
        
        # Sensible defaults after loading everything
        if self.host_address == '':
            self.host_address = self.host_alias
        if self.netbox_host_name == '':
            self.netbox_host_name = self.host_alias
        if self.netbox_host_ip == '':
            self.netbox_host_ip = self.host_address
        if self.grafana_host_name == '':
            self.grafana_host_name = self.host_alias

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


# Classes for getting data from each external system
class Netbox:
    """Netbox object that parses data from the Netbox api
    all ivars are intialized as empty and filled if valid data is found for each type

    :ivar host: dict : api data to the host for the NETBOXBASE and host_alias
    :ivar host_url: str : url to the host for the NETBOXBASE and host_alias
    :ivar ip: dict : api data to the host ip address for the NETBOXBASE and host_alias
    :ivar ip_url: str : url to the host ip address for the NETBOXBASE and host_alias
    """

    def __init__(self):
        self.host = {}
        self.host_url = ''
        self.ip = {}
        self.ip_url = ''

        if config.netbox.url:
            self.__parse()

    def __parse(self):
        """ Search netbox for

        :return:
        """
        nb_device = self.__searchData(config.netbox.url + '/api' + config.netbox.api_device + '/?name=' + config.netbox_host_name)
        nb_vm = self.__searchData(config.netbox.url + '/api' + config.netbox.api_vm + '/?name=' + config.netbox_host_name)
        nb_host_ip = self.__searchData(config.netbox.url + '/api' + config.netbox.api_ip + '/?address=' + config.netbox_host_name)
        nb_address_ip = self.__searchData(config.netbox.url + '/api' + config.netbox.api_ip + '/?address=' + config.netbox_host_ip)

        if config.debug:
            print(json.dumps(nb_device, indent=4, sort_keys=True))
            print(json.dumps(nb_vm, indent=5, sort_keys=True))
            print(json.dumps(nb_address_ip, indent=4, sort_keys=True))

        if nb_device and not nb_vm:
            self.host = nb_device
            self.host_url = "{}/{}/".format(config.netbox.url + config.netbox.api_device, nb_device['id'])
        elif not nb_device and nb_vm:
            self.host = nb_vm
            self.host_url = "{}/{}/".format(config.netbox.url + config.netbox.api_vm, nb_vm['id'])
        elif nb_device and nb_vm:
            print("Found multiple device's or vm's that match")
        else:
            print("Found no device's or vm's that match")

        if nb_host_ip:
            self.ip = nb_host_ip
            self.ip_url = "{}/{}/".format(config.netbox.url + config.netbox.api_ip, nb_host_ip['id'])
        elif nb_address_ip:
            self.ip = nb_address_ip
            self.ip_url = "{}/{}/".format(config.netbox.url + config.netbox.api_ip, nb_address_ip['id'])

    def __getServerData(self, url):
        headers = {'Accept': 'application/json'}
        if config.netbox.token:
            headers.update({'Authorization': 'Token ' + config.netbox.token})
        try:
            response = requests.get(url, headers=headers)
            result = response.json()
            if config.debug:
                print("Netbox response: ")
                print(response)
        except Exception as e:
            print("Error getting netbox data from {} with error {}".format(url, e))
            result = {'count': 0}
        if config.debug:
            print("Netbox result: ")
            print(result)
        return result

    def __searchData(self, url):
        result = self.__getServerData(url)
        if result['count'] == 1 and result['results']:
            return result['results'][0]
        else:
            return {}

    def __getVal(self, obj, key1, key2=None):
        val = ''
        if key1 in obj:
            if key2 and key2 in obj[key1]:
                val = obj[key1][key2]
            else:
                val = obj[key1]
        return val

    def addRow(self, title, obj, key1, key2=None):
        """Generate html row containing title and value from key(s) in object
        
         Arguments:
        :arg title: str : Title for the row
        :arg obj : dict : netbox dict that we are parsing
        :arg key1 : str : key to get value for

        Keyword Arguments:
        :arg key2 : str : sub key to get value for (default: None)

        :return: str : html row if keys exist else empty string
        """
        val = self.__getVal(obj, key1, key2)
        if val:
            val = '\n<tr><th width="' + config.column_width + '">' + title + ':</th><td>' + val + '</td></tr>'
        else:
            val = ''
        return val

    def addLinkRow(self, title, obj, key1, key2=None):
        """Generate html row containing title, value and link from key(s) in object
        assumes the last key contains a key value == url

        Arguments:
        :arg title: str : Title for the row
        :arg obj : dict : netbox dict that we are parsing
        :arg key1 : str : key to get value for

        Keyword Arguments:
        :arg key2 : str : sub key to get value for (default: None)

        :return: str : html row if keys exist else empty
        """
        val = self.__getVal(obj, key1, key2)
        if val:
            val = '\n<tr><th width="' + config.column_width + '">' + title + ':</th><td><a href="' + re.sub(r"\/api\/", "/", self.__getVal(obj, key1, "url")) + '">' + val + '</a></td></tr>'
        else:
            val = ''
        return val


class Grafana:
    """Grafana object that parses icingaweb2 grafana module (optional) and data from the grafana api
    all ivars are intialized as empty and filled if valid data is found for each type
    
    :ivar png_url: str: url to the png for the GRAFANABASE, netbox_host_name and panelid
    :ivar page_url: str: url to the page for the GRAFANABASE, netbox_host_name and panelid
    :ivar png: request.get object : contains the png for the GRAFANABASE, netbox_host_name and panelid
    :ivar self.panelID: int : number representing the panelid for the service

    :ivar __icingaweb2_ini: ConfigParser.read object : contains the icingaweb2 grafana module ini settings for the GRAFANAICINGAWEB2INI
    """
    def __init__(self):
        """Get best panelid depending on service or host state then attempt to build urls and get png
        panelid prioritizes environment var over ini file of default host value

        """
        self.png_url = ''
        self.page_url = ''
        self.png = None
        self.__icingaweb2_ini = None
        self.panelID = None

        if os.path.exists(config.grafana.icingaweb2_ini):
            self.__parseIcingaweb2INI()

        if config.service_state:
            if config.grafana_panel_id:
                self.panelID = config.grafana_panel_id
            elif os.path.exists(config.grafana.icingaweb2_ini):
                self.__parseIcingaweb2INI()
                self.panelID = self.__getINIPanelID(config.service_display_name, config.service_name, config.service_command)
            else:
                print("Unable to get panel id for service from environment var GRAFANAPANELID [{0}] or from the icingaweb2 grafana module ini file {1}".format(config.grafana_panel_id, config.grafana.icingaweb2_ini))

        elif config.host_state:
            if config.grafana_panel_id:
                self.panelID = config.grafana_panel_id
            else:
                self.panelID = config.grafana.default_panel_id

        if self.panelID and config.grafana.url:
            self.png_url = config.grafana.url + '/render/dashboard-solo/db/' + config.grafana.dashboard + '?panelId=' + self.panelID + '&' + config.grafana.var_hostname + '=' + config.grafana_host_name + '&theme=' + GRAFANATHEME + '&width=' + config.table_width + '&height=' + config.grafana.image_height
            self.page_url = config.grafana.url + '/dashboard/db/' + config.grafana.dashboard + '?fullscreen&panelId=' + self.panelID + '&' + config.grafana.var_hostname + '=' + config.grafana_host_name
            self.png = self.__getPNG()

    def __parseIcingaweb2INI(self):
        if config.debug:
            print("\nGrafana ini file: {}".format(config.grafana.icingaweb2_ini))
        try:
            self.__icingaweb2_ini = ConfigParser.ConfigParser()
            self.__icingaweb2_ini.read(config.grafana.icingaweb2_ini)
        except Exception as e:
            print("Unable to parse grafana ini file ({}) with error {}".format(config.grafana.icingaweb2_ini, e))
            self.__icingaweb2_ini = None

    def __getPNG(self):
        headers = {'Authorization': 'Bearer ' + config.grafana.api_key}
        if config.debug:
            print("PNG url: " + self.png_url)
            print("PNG headers: {}".format(headers))
        try:
            response = requests.get(self.png_url, headers=headers)
            if config.debug:
                print("PNG get status code: {}".format(response.status_code))
        except Exception as e:
            print("Error getting png from {} with error {}".format(self.page_url, e))
            response = None
        return response

    def __searchINISections(self, display_name, name, command):
        pattern = None
        if display_name:
            pattern = re.compile(display_name)
        if name and pattern is None:
            pattern = re.compile(name)
        if command and pattern is None:
            pattern = re.compile(command)

        section = None
        try:
            if config.debug:
                print("\nGrafana ini sections: {}".format(self.__icingaweb2_ini.sections()))
                print("\nGrafana ini pattern: {}".format(pattern))
            if pattern:
                section = filter(pattern.match, self.__icingaweb2_ini.sections())
                if config.debug:
                    print("\nGrafana section: {}".format(section))
                if len(section) == 1:
                    section = section[0]
        except Exception as e:
            print("Error reading grafana ini file ({}) with error {}".format(config.grafana.icingaweb2_ini, e))
            section = None

        if config.debug:
            print("\nGrafana section: {}".format(section))
        return section

    def __getINIPanelID(self, display_name, name, command):
        section = self.__searchINISections(display_name, name, command)
        panel_id = None
        if section:
            panel_id = self.__icingaweb2_ini.get(section, 'panelId').replace('"', '')
        return panel_id

config = Settings()
config.mail = SettingsMail(_config_dict=config._config_dict)
config.icinga = SettingsIcinga(_config_dict=config._config_dict)
config.netbox = SettingsNetbox(_config_dict=config._config_dict)
config.grafana = SettingsGrafana(_config_dict=config._config_dict, image_width=config.table_width)

# Init logging
if config.debug:
    initLogger(log_level='DEBUG', log_file="/var/log/icinga2/notification-enhanced-email.log")
else:
    initLogger(log_level='INFO', log_file="/var/log/icinga2/notification-enhanced-email.log")

if config.print_config:
    config.printArguments
    config.printEnvironmentVars
    sys.exit(0)

# Misc
remaining_width = str(int(config.table_width) - int(config.column_width))

# With debug on each run produces a template that can be rerun for testing
cmd = "/etc/icinga2/scripts/enhanced-mail-notification.py"
for env in config._getArgVarList():
    if type(env[2]) == bool:
        cmd += f' {env[1]}'
    else:
        cmd += f' {env[1]} "{env[2]}"'
logger.info(cmd)

# initialise objects for 3rd party info
netbox = Netbox()
grafana = Grafana()

# Email subject
if config.host_state:
    email_subject = 'Host {0} - {1} is {2}'.format(config.notification_type, config.host_display_name, config.host_state)
elif config.service_state:
    email_subject = 'Service {0} - {1} service {2} is {3}'.format(config.notification_type, config.host_display_name, config.service_display_name, config.service_state)
else:
    email_subject = 'Unknown {0} - {1} service {2} (no host or service state)'.format(config.notification_type, config.host_display_name, config.service_display_name)

# Prepare mail body
plain_text_template = Template("""
***** Icinga  *****

Notification Type: {config.notification_type}

Host: {config.host_alias}
Address: {config.host_address}
Service: {config.service_display_name}
State: {config.host_state}{config.service_state}

Date/Time: {config.long_date_time}

Additional Info: {config.host_output}{config.service_output}

Comment: [{config.notification_author}] {config.notification_comment}

{% if grafana.page_url != '' %}
Grafana: {grafana.page_url}
{% endif %}

{% if netbox.host_url != '' %}
Netbox Host: {netbox.host_url}
{% endif %}
{% if netbox.ip_url != '' %}
Netbox IP: {netbox.ip_url}
{% endif %}
""")

plain_text_email = plain_text_template.render(config=config, grafana=grafana, netbox=netbox)

# TODO: migrating this to j2 template
html_email = '<html><head><style type="text/css">'
html_email += '\nbody {text-align: left; font-family: calibri, sans-serif, verdana; font-size: 10pt; color: #7f7f7f;}'
html_email += '\ntable {margin-left: auto; margin-right: auto;}'
html_email += '\na:link {color: #0095bf; text-decoration: none;}'
html_email += '\na:visited {color: #0095bf; text-decoration: none;}'
html_email += '\na:hover {color: #0095bf; text-decoration: underline;}'
html_email += '\na:active {color: #0095bf; text-decoration: underline;}'
html_email += '\nth {font-family: calibri, sans-serif, verdana; font-size: 10pt; text-align:left; white-space: nowrap; color: #535353;}'
html_email += '\nth.icinga {background-color: #0095bf; color: #ffffff; margin-left: 7px; margin-top: 5px; margin-bottom: 5px;}'
html_email += '\nth.perfdata, th.perfdata a:link, th.perfdata a:visited {background-color: #0095bf; color: #ffffff; margin-left: 7px; margin-top: 5px; margin-bottom: 5px; text-align:center;}'
html_email += '\ntd {font-family: calibri, sans-serif, verdana; font-size: 10pt; text-align:left; color: #7f7f7f;}'
html_email += '\ntd.center {text-align:center; white-space: nowrap;}'
html_email += '\ntd.UP {background-color: #44bb77; color: #ffffff; margin-left: 2px;}'
html_email += '\ntd.DOWN {background-color: #ff5566; color: #ffffff; margin-left: 2px;}'
html_email += '\ntd.UNREACHABLE {background-color: #aa44ff; color: #ffffff; margin-left: 2px;}'
html_email += '\n</style></head><body>'
html_email += '\n<table width=' + config.table_width + '>'

if os.path.exists(config.icinga.logo_path):
    html_email += '\n<tr><th colspan=2 class=icinga width=' + config.table_width + '><img src="cid:icinga2_logo"></th></tr>'

html_email += '\n<tr><th>Hostalias:</th><td><a style="color: #0095bf; text-decoration: none;" href="' + config.icinga.url + '/monitoring/host/show?host=' + config.host_alias + '">' + config.host_alias + '</a></td></tr>'
html_email += '\n<tr><th>IP Address:</th><td>' + config.host_address + '</td></tr>'
html_email += '\n<tr><th>Status:</th><td>' + config.host_state + config.service_state + '</td></tr>'
html_email += '\n<tr><th>Service Name:</th><td>' + config.service_display_name + '</td></tr>'
if config.host_state:
    html_email += '\n<tr><th>Service Data:</th><td><a style="color: #0095bf; text-decoration: none;" href="' + config.icinga.url + '/monitoring/host/services?host=' + config.host_alias + '">' + config.host_output + '</a></td></tr>'
if config.service_state:
    html_email += '\n<tr><th>Service Data:</th><td><a style="color: #0095bf; text-decoration: none;" href="' + config.icinga.url + '/monitoring/service/show?host=' + config.host_alias + '&service=' + config.service_name + '">' + config.service_output + '</a></td></tr>'
html_email += '\n<tr><th>Event Time:</th><td>' + config.long_date_time + '</td></tr>'

if config.notification_author and config.notification_comment:
    html_email += f'\n<tr><th>Comment:</th><td>{config.notification_comment} ({config.notification_author})</td></tr>'

if netbox.host:
    html_email += '\n</table><br>'
    html_email += '\n<table width=' + config.table_width + '>'
    html_email += '\n<tr><th colspan=2 class=perfdata><a href="' + netbox.host_url + '">Netbox Info for ' + config.host_alias + '</a></th></tr>'
    html_email += netbox.addRow('Display Name', netbox.host, 'display_name')
    html_email += netbox.addRow('Display Name', netbox.host, 'name')
    html_email += netbox.addLinkRow('Cluster', netbox.host, 'cluster', 'name')
    html_email += netbox.addLinkRow('Tennant', netbox.host, 'tennant', 'name')
    html_email += netbox.addLinkRow('Site', netbox.host, 'site', 'name')  # Sites use the slug
    html_email += netbox.addLinkRow('Rack', netbox.host, 'rack', 'name')
    html_email += netbox.addRow('Position', netbox.host, 'position')
    html_email += netbox.addRow('Primary IP', netbox.host, 'primary_ip')
    html_email += netbox.addRow('Primary IPv4', netbox.host, 'primary_ip4')
    html_email += netbox.addRow('Primary IPv6', netbox.host, 'primary_ip6')
    html_email += netbox.addLinkRow('Device Type', netbox.host, 'device_type', 'model')
    html_email += netbox.addRow('Status', netbox.host, 'status', 'label')

if netbox.ip:
    html_email += '\n</table><br>'
    html_email += '\n<table width=' + config.table_width + '>'
    html_email += '\n<tr><th colspan=2 class=perfdata><a href="' + netbox.ip_url + '">Netbox Info for ' + config.host_address + '</a></th></tr>'
    html_email += netbox.addRow('Display Name', netbox.ip, 'address')
    html_email += netbox.addRow('Status', netbox.ip, 'status', 'label')
    html_email += netbox.addRow('Host', netbox.ip, 'virtual_machine', 'name')
    html_email += netbox.addRow('Host', netbox.ip, 'device', 'name')

if (config.performance_data and '=' in config.performance_data) or grafana.png:
    html_email += '\n</table><br>'
    html_email += '\n<table width=' + config.table_width + '>'
    html_email += '\n<tr><th colspan=6 class=perfdata>Performance Data</th></tr>'
    if config.performance_data:
        html_email += '\n<tr><th>Label</th><th>Last Value</th><th>Warning</th><th>Critical</th><th>Min</th><th>Max</th></tr>'
        perf_data_list = config.performance_data.split(" ")
        for perf in perf_data_list:
            if '=' not in perf:
                continue

            (label, data) = perf.split("=")
            if len(data.split(";")) is 5:
                (value, warning, critical, min, max) = data.split(";")
            else:
                (value, warning, critical, min) = data.split(";")
                max = ''
            html_email += '\n<tr><td>' + label + '</td><td>' + value + '</td><td>' + warning + '</td><td>' + critical + '</td><td>' + min + '</td><td>' + max + '</td></tr>'
    else:
        html_email += '\n<tr><th width=' + config.column_width + ' colspan=1>Last Value:</th><td width=' + remaining_width + ' colspan=5>none</td></tr>'

    if grafana.png:
        html_email += '\n<tr><td colspan=6><a href="' + grafana.page_url + '"><img src="cid:grafana2_perfdata" width=' + config.table_width + ' height=' + config.grafana.image_height + '></a></td></tr>'

html_email += '\n</table><br>'
html_email += '\n<table width=' + config.table_width + '>'
html_email += '\n<tr><td class=center>Generated by Icinga 2 with data from Icinga 2'
if grafana.panelID:
    html_email += ', Grafana'

if netbox.host or netbox.ip:
    html_email += ', Netbox'

html_email += '</td></tr>'
html_email += '\n</table><br>'
html_email += '\n</body></html>'

if config.debug:
    print(html_email)

# Prepare email
msgRoot = MIMEMultipart('related')
msgRoot['Subject'] = email_subject
msgRoot['From'] = config.mail.from_address
msgRoot['To'] = config.email_to
msgRoot.preamble = 'This is a multi-part message in MIME format.'

msgAlternative = MIMEMultipart('alternative')
msgRoot.attach(msgAlternative)

msgText = MIMEText(plain_text_email)
msgAlternative.attach(msgText)

msgText = MIMEText(html_email, 'html')
msgAlternative.attach(msgText)

# Attach images
if os.path.exists(config.icinga.logo_path):
    fp = open(config.icinga.logo_path, 'rb')
    msgImage = MIMEImage(fp.read())
    fp.close()
    msgImage.add_header('Content-ID', '<icinga2_logo>')
    msgRoot.attach(msgImage)

if grafana.png:
    try:
        msgImage = MIMEImage(grafana.png.content)
        msgImage.add_header('Content-ID', '<grafana2_perfdata>')
        msgRoot.attach(msgImage)
    except Exception as e:
        print("Grafana PNG response exists but was unable to attach the content, failed with error {}".format(e))
        print(grafana.png)


# Send mail using SMTP
smtp = smtplib.SMTP()

try:
    smtp.connect(config.mail.server)
except socket.error as e:
    print("Unable to connect to SMTP server '" + config.mail.server + "': " + e.strerror)
    os.sys.exit(e.errno)

if config.mail.username and config.mail.password:
    smtp.login(config.mail.username, config.mail.password)

try:
    smtp.sendmail(config.mail.from_address, config.email_to, msgRoot.as_string())
    smtp.quit()
except Exception as e:
    print("Cannot send mail using SMTP: " + e.message)
    os.sys.exit(e.errno)

os.sys.exit(0)