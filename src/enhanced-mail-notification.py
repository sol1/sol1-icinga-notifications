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

from lib.SettingsParser import SettingsParser

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage

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
    # eg: http://netbox.domain.local
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

config = Settings()
config.mail = SettingsMail(_config_dict=config._config_dict)
config.icinga = SettingsIcinga(_config_dict=config._config_dict)
config.netbox = SettingsNetbox(_config_dict=config._config_dict)
config.grafana = SettingsGrafana(_config_dict=config._config_dict)



###############
# Static Vars #
###############
# User customization here
# Email
EMAILFROM = 'icinga@domain.local'
EMAILSERVER = 'localhost'
EMAILUSERNAME = ''
EMAILPASSWORD = ''

## Icinga ##
# INFO: no trailing / on the url, it can generate errors
ICINGA2BASE = 'http://icinga.domain.local/icingaweb2'
ICINGA2LOGOPATH = '/usr/share/icingaweb2/public/img/icinga-logo.png'

## Netbox ##
# INFO: leave netbox base empty if you don't use netbox and it won't be included
# INFO: no trailing / on the url, it can generate errors
NETBOXBASE = 'http://netbox.domain.local'
NETBOXTOKEN = 'abcdefghijklmnopqrstuvwxyz1234567890'

NETBOXPATHDEVICES = '/dcim/devices'
NETBOXPATHVMS = '/virtualization/virtual-machines'
NETBOXPATHIPS = '/ipam/ip-addresses'

## Grafana ##
# INFO: no trailing / on the url, it can generate errors
GRAFANABASE = 'http://grafana.domain.local'
GRAFANADASHBOARD = 'icinga2-with-influxdb'
# The grafana module in icingaweb2 stores panel id for each service in a ini file
GRAFANAICINGAWEB2INI = '/etc/icingaweb2/modules/grafana/graphs.ini'
# This is the key that grafana users to search the host name value
GRAFANAVARHOST = 'var-hostname'
GRAFANATHEME = 'light'
GRAFANAAPIKEY = 'abcdefghijklmnopqrstuvwxyz1234567890'
GRAFANADEFAULTHOSTPANELID = '2'  # Usually ping

# Misc
WIDTH = '640'
HEIGHT = '321'
COLUMN = '144'
DIFFERENCE = str(int(WIDTH) - int(COLUMN))

DEBUG = os.getenv('DEBUG')
# DEBUG = True

#################
# External Vars #
#################
notification_type = os.getenv('NOTIFICATIONTYPE', '')
host_alias = os.getenv('HOSTALIAS', '')
host_display_name = os.getenv('HOSTDISPLAYNAME', '')
host_address = os.getenv('HOSTADDRESS', host_alias)
host_state = os.getenv('HOSTSTATE', '')
host_output = os.getenv('HOSTOUTPUT', '')
service_name = os.getenv('SERVICENAME', '')
service_display_name = os.getenv('SERVICEDISPLAYNAME', '')
service_command = os.getenv('SERVICECOMMAND', '')
service_state = os.getenv('SERVICESTATE', '')
service_output = os.getenv('SERVICEOUTPUT', '')
long_date_time = os.getenv('LONGDATETIME', '')
notification_author = os.getenv('NOTIFICATIONAUTHORNAME', '')
notification_comment = os.getenv('NOTIFICATIONCOMMENT', '')
email_to = os.getenv('USEREMAIL', '')
performance_data = os.getenv('PERFDATA', '')
netbox_host_name = os.getenv('NETBOXHOSTNAME', host_alias)
if netbox_host_name == '':
    # If the env is set but empty
    netbox_host_name = host_alias

netbox_host_ip = os.getenv('NETBOXHOSTIP', host_address)
if netbox_host_name == '':
    # If the env is set but empty
    netbox_host_name = host_address

grafana_host_name = host_alias
grafana_panel_id = os.getenv('GRAFANAPANELID', None)

# If the host_address is set to nothing use the alias
if not host_address:
    host_address = host_alias

# With debug on each run produces a template that can be rerun for testing
if DEBUG:
    with open("/tmp/enhanced-mail.sh", "w+") as f:
        f.write("#!/bin/bash")
        f.write("\n")
        f.write('\nexport NOTIFICATIONTYPE="{}"'.format(notification_type))
        f.write('\nexport HOSTALIAS="{}"'.format(host_alias))
        f.write('\nexport HOSTDISPLAYNAME="{}"'.format(host_display_name))
        f.write('\nexport HOSTADDRESS="{}"'.format(host_address))
        f.write('\nexport HOSTSTATE="{}"'.format(host_state))
        f.write('\nexport HOSTOUTPUT="{}"'.format(host_output))
        f.write('\nexport SERVICENAME="{}"'.format(service_name))
        f.write('\nexport SERVICEDISPLAYNAME="{}"'.format(service_display_name))
        f.write('\nexport SERVICECOMMAND="{}"'.format(service_command))
        f.write('\nexport SERVICESTATE="{}"'.format(service_state))
        f.write('\nexport SERVICEOUTPUT="{}"'.format(service_output))
        f.write('\nexport LONGDATETIME="{}"'.format(long_date_time))
        f.write('\nexport NOTIFICATIONAUTHORNAME="{}"'.format(notification_author))
        f.write('\nexport NOTIFICATIONCOMMENT="{}"'.format(notification_comment))
        f.write('\nexport USEREMAIL="{}"'.format(email_to))
        f.write('\nexport PERFDATA="{}"'.format(performance_data))
        f.write('\nexport NETBOXHOSTNAME="{}"'.format(netbox_host_name))
        f.write('\nexport NETBOXHOSTIP="{}"'.format(netbox_host_ip))
        f.write('\nexport GRAFANAHOSTNAME="{}"'.format(grafana_host_name))
        f.write('\nexport GRAFANAPANELID="{}"'.format(grafana_panel_id))
        f.write("\n")
        f.write("\n/etc/icinga2/scripts/enhanced-mail-notification.py")
    f.close()


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

        if NETBOXBASE:
            self.__parse()

    def __parse(self):
        """ Search netbox for

        :return:
        """
        nb_device = self.__searchData(NETBOXBASE + '/api' + NETBOXPATHDEVICES + '/?name=' + netbox_host_name)
        nb_vm = self.__searchData(NETBOXBASE + '/api' + NETBOXPATHVMS + '/?name=' + netbox_host_name)
        nb_host_ip = self.__searchData(NETBOXBASE + '/api' + NETBOXPATHIPS + '/?address=' + netbox_host_name)
        nb_address_ip = self.__searchData(NETBOXBASE + '/api' + NETBOXPATHIPS + '/?address=' + netbox_host_ip)

        if DEBUG:
            print(json.dumps(nb_device, indent=4, sort_keys=True))
            print(json.dumps(nb_vm, indent=5, sort_keys=True))
            print(json.dumps(nb_address_ip, indent=4, sort_keys=True))

        if nb_device and not nb_vm:
            self.host = nb_device
            self.host_url = "{}/{}/".format(NETBOXBASE + NETBOXPATHDEVICES, nb_device['id'])
        elif not nb_device and nb_vm:
            self.host = nb_vm
            self.host_url = "{}/{}/".format(NETBOXBASE + NETBOXPATHVMS, nb_vm['id'])
        elif nb_device and nb_vm:
            print("Found multiple device's or vm's that match")
        else:
            print("Found no device's or vm's that match")

        if nb_host_ip:
            self.ip = nb_host_ip
            self.ip_url = "{}/{}/".format(NETBOXBASE + NETBOXPATHIPS, nb_host_ip['id'])
        elif nb_address_ip:
            self.ip = nb_address_ip
            self.ip_url = "{}/{}/".format(NETBOXBASE + NETBOXPATHIPS, nb_address_ip['id'])

    def __getServerData(self, url):
        headers = {'Accept': 'application/json'}
        if NETBOXTOKEN:
            headers.update({'Authorization': 'Token ' + NETBOXTOKEN})
        try:
            response = requests.get(url, headers=headers)
            result = response.json()
            if DEBUG:
                print("Netbox response: ")
                print(response)
        except Exception as e:
            print("Error getting netbox data from {} with error {}".format(url, e))
            result = {'count': 0}
        if DEBUG:
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
            val = '\n<tr><th width="' + COLUMN + '">' + title + ':</th><td>' + val + '</td></tr>'
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
            val = '\n<tr><th width="' + COLUMN + '">' + title + ':</th><td><a href="' + re.sub(r"\/api\/", "/", self.__getVal(obj, key1, "url")) + '">' + val + '</a></td></tr>'
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

        if os.path.exists(GRAFANAICINGAWEB2INI):
            self.__parseIcingaweb2INI()

        if service_state:
            if grafana_panel_id:
                self.panelID = grafana_panel_id
            elif os.path.exists(GRAFANAICINGAWEB2INI):
                self.__parseIcingaweb2INI()
                self.panelID = self.__getINIPanelID(service_display_name, service_name, service_command)
            else:
                print("Unable to get panel id for service from environment var GRAFANAPANELID [{0}] or from the icingaweb2 grafana module ini file {1}".format(grafana_panel_id, GRAFANAICINGAWEB2INI))

        elif host_state:
            if grafana_panel_id:
                self.panelID = grafana_panel_id
            else:
                self.panelID = GRAFANADEFAULTHOSTPANELID

        if self.panelID and GRAFANABASE:
            self.png_url = GRAFANABASE + '/render/dashboard-solo/db/' + GRAFANADASHBOARD + '?panelId=' + self.panelID + '&' + GRAFANAVARHOST + '=' + grafana_host_name + '&theme=' + GRAFANATHEME + '&width=' + WIDTH + '&height=' + HEIGHT
            self.page_url = GRAFANABASE + '/dashboard/db/' + GRAFANADASHBOARD + '?fullscreen&panelId=' + self.panelID + '&' + GRAFANAVARHOST + '=' + grafana_host_name
            self.png = self.__getPNG()

    def __parseIcingaweb2INI(self):
        if DEBUG:
            print("\nGrafana ini file: {}".format(GRAFANAICINGAWEB2INI))
        try:
            self.__icingaweb2_ini = ConfigParser.ConfigParser()
            self.__icingaweb2_ini.read(GRAFANAICINGAWEB2INI)
        except Exception as e:
            print("Unable to parse grafana ini file ({}) with error {}".format(GRAFANAICINGAWEB2INI, e))
            self.__icingaweb2_ini = None

    def __getPNG(self):
        headers = {'Authorization': 'Bearer ' + GRAFANAAPIKEY}
        if DEBUG:
            print("PNG url: " + self.png_url)
            print("PNG headers: {}".format(headers))
        try:
            response = requests.get(self.png_url, headers=headers)
            if DEBUG:
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
            if DEBUG:
                print("\nGrafana ini sections: {}".format(self.__icingaweb2_ini.sections()))
                print("\nGrafana ini pattern: {}".format(pattern))
            if pattern:
                section = filter(pattern.match, self.__icingaweb2_ini.sections())
                if DEBUG:
                    print("\nGrafana section: {}".format(section))
                if len(section) == 1:
                    section = section[0]
        except Exception as e:
            print("Error reading grafana ini file ({}) with error {}".format(GRAFANAICINGAWEB2INI, e))
            section = None

        if DEBUG:
            print("\nGrafana section: {}".format(section))
        return section

    def __getINIPanelID(self, display_name, name, command):
        section = self.__searchINISections(display_name, name, command)
        panel_id = None
        if section:
            panel_id = self.__icingaweb2_ini.get(section, 'panelId').replace('"', '')
        return panel_id

# initalise objects for 3rd party info
netbox = Netbox()
grafana = Grafana()

# Email subject
if host_state:
    email_subject = 'Host {0} - {1} is {2}'.format(notification_type, host_display_name, host_state)
elif service_state:
    email_subject = 'Service {0} - {1} service {2} is {3}'.format(notification_type, host_display_name, service_display_name, service_state)
else:
    email_subject = 'Unknown {0} - {1} service {2} (no host or service state)'.format(notification_type, host_display_name, service_display_name)

# Prepare mail body
email_plain_text = '***** Icinga  *****'
email_plain_text += '\n'
email_plain_text += '\nNotification Type: {0}'.format(notification_type)
email_plain_text += '\n'
email_plain_text += '\nHost: {0}'.format(host_alias)
email_plain_text += '\nAddress: {0}'.format(host_address)
email_plain_text += '\nService: {0}'.format(service_display_name)
email_plain_text += '\nState: {0}{1}'.format(host_state, service_state)
email_plain_text += '\n'
email_plain_text += '\nDate/Time: {0}'.format(long_date_time)
email_plain_text += '\n'
email_plain_text += '\nAdditional Info: {0}{1}'.format(host_output, service_output)
email_plain_text += '\n'
email_plain_text += '\nComment: [{0}] {1}'.format(notification_author, notification_comment)
if grafana.page_url:
    email_plain_text += '\n'
    email_plain_text += '\nGrafana: {0}'.format(grafana.page_url)
if netbox.host_url:
    email_plain_text += '\n'
    email_plain_text += '\nNetbox Host: {0}'.format(netbox.host_url)
if netbox.ip_url:
    email_plain_text += '\n'
    email_plain_text += '\nNetbox IP: {0}'.format(netbox.ip_url)
email_plain_text += '\n'

email_html = '<html><head><style type="text/css">'
email_html += '\nbody {text-align: left; font-family: calibri, sans-serif, verdana; font-size: 10pt; color: #7f7f7f;}'
email_html += '\ntable {margin-left: auto; margin-right: auto;}'
email_html += '\na:link {color: #0095bf; text-decoration: none;}'
email_html += '\na:visited {color: #0095bf; text-decoration: none;}'
email_html += '\na:hover {color: #0095bf; text-decoration: underline;}'
email_html += '\na:active {color: #0095bf; text-decoration: underline;}'
email_html += '\nth {font-family: calibri, sans-serif, verdana; font-size: 10pt; text-align:left; white-space: nowrap; color: #535353;}'
email_html += '\nth.icinga {background-color: #0095bf; color: #ffffff; margin-left: 7px; margin-top: 5px; margin-bottom: 5px;}'
email_html += '\nth.perfdata, th.perfdata a:link, th.perfdata a:visited {background-color: #0095bf; color: #ffffff; margin-left: 7px; margin-top: 5px; margin-bottom: 5px; text-align:center;}'
email_html += '\ntd {font-family: calibri, sans-serif, verdana; font-size: 10pt; text-align:left; color: #7f7f7f;}'
email_html += '\ntd.center {text-align:center; white-space: nowrap;}'
email_html += '\ntd.UP {background-color: #44bb77; color: #ffffff; margin-left: 2px;}'
email_html += '\ntd.DOWN {background-color: #ff5566; color: #ffffff; margin-left: 2px;}'
email_html += '\ntd.UNREACHABLE {background-color: #aa44ff; color: #ffffff; margin-left: 2px;}'
email_html += '\n</style></head><body>'
email_html += '\n<table width=' + WIDTH + '>'

if os.path.exists(ICINGA2LOGOPATH):
    email_html += '\n<tr><th colspan=2 class=icinga width=' + WIDTH + '><img src="cid:icinga2_logo"></th></tr>'

email_html += '\n<tr><th>Hostalias:</th><td><a style="color: #0095bf; text-decoration: none;" href="' + ICINGA2BASE + '/monitoring/host/show?host=' + host_alias + '">' + host_alias + '</a></td></tr>'
email_html += '\n<tr><th>IP Address:</th><td>' + host_address + '</td></tr>'
email_html += '\n<tr><th>Status:</th><td>' + host_state + service_state + '</td></tr>'
email_html += '\n<tr><th>Service Name:</th><td>' + service_display_name + '</td></tr>'
if host_state:
    email_html += '\n<tr><th>Service Data:</th><td><a style="color: #0095bf; text-decoration: none;" href="' + ICINGA2BASE + '/monitoring/host/services?host=' + host_alias + '">' + host_output + '</a></td></tr>'
if service_state:
    email_html += '\n<tr><th>Service Data:</th><td><a style="color: #0095bf; text-decoration: none;" href="' + ICINGA2BASE + '/monitoring/service/show?host=' + host_alias + '&service=' + service_name + '">' + service_output + '</a></td></tr>'
email_html += '\n<tr><th>Event Time:</th><td>' + long_date_time + '</td></tr>'

if notification_author and notification_comment:
    email_html += '\n<tr><th>Comment:</th><td>{0} ({1})</td></tr>'.format(notification_comment, notification_author)

if netbox.host:
    email_html += '\n</table><br>'
    email_html += '\n<table width=' + WIDTH + '>'
    email_html += '\n<tr><th colspan=2 class=perfdata><a href="' + netbox.host_url + '">Netbox Info for ' + host_alias + '</a></th></tr>'
    email_html += netbox.addRow('Display Name', netbox.host, 'display_name')
    email_html += netbox.addRow('Display Name', netbox.host, 'name')
    email_html += netbox.addLinkRow('Cluster', netbox.host, 'cluster', 'name')
    email_html += netbox.addLinkRow('Tennant', netbox.host, 'tennant', 'name')
    email_html += netbox.addLinkRow('Site', netbox.host, 'site', 'name')  # Sites use the slug
    email_html += netbox.addLinkRow('Rack', netbox.host, 'rack', 'name')
    email_html += netbox.addRow('Position', netbox.host, 'position')
    email_html += netbox.addRow('Primary IP', netbox.host, 'primary_ip')
    email_html += netbox.addRow('Primary IPv4', netbox.host, 'primary_ip4')
    email_html += netbox.addRow('Primary IPv6', netbox.host, 'primary_ip6')
    email_html += netbox.addLinkRow('Device Type', netbox.host, 'device_type', 'model')
    email_html += netbox.addRow('Status', netbox.host, 'status', 'label')

if netbox.ip:
    email_html += '\n</table><br>'
    email_html += '\n<table width=' + WIDTH + '>'
    email_html += '\n<tr><th colspan=2 class=perfdata><a href="' + netbox.ip_url + '">Netbox Info for ' + host_address + '</a></th></tr>'
    email_html += netbox.addRow('Display Name', netbox.ip, 'address')
    email_html += netbox.addRow('Status', netbox.ip, 'status', 'label')
    email_html += netbox.addRow('Host', netbox.ip, 'virtual_machine', 'name')
    email_html += netbox.addRow('Host', netbox.ip, 'device', 'name')

if (performance_data and '=' in performance_data) or grafana.png:
    email_html += '\n</table><br>'
    email_html += '\n<table width=' + WIDTH + '>'
    email_html += '\n<tr><th colspan=6 class=perfdata>Performance Data</th></tr>'
    if performance_data:
        email_html += '\n<tr><th>Label</th><th>Last Value</th><th>Warning</th><th>Critical</th><th>Min</th><th>Max</th></tr>'
        perf_data_list = performance_data.split(" ")
        for perf in perf_data_list:
            if '=' not in perf:
                continue

            (label, data) = perf.split("=")
            if len(data.split(";")) is 5:
                (value, warning, critical, min, max) = data.split(";")
            else:
                (value, warning, critical, min) = data.split(";")
                max = ''
            email_html += '\n<tr><td>' + label + '</td><td>' + value + '</td><td>' + warning + '</td><td>' + critical + '</td><td>' + min + '</td><td>' + max + '</td></tr>'
    else:
        email_html += '\n<tr><th width=' + COLUMN + ' colspan=1>Last Value:</th><td width=' + DIFFERENCE + ' colspan=5>none</td></tr>'

    if grafana.png:
        email_html += '\n<tr><td colspan=6><a href="' + grafana.page_url + '"><img src="cid:grafana2_perfdata" width=' + WIDTH + ' height=' + HEIGHT + '></a></td></tr>'

email_html += '\n</table><br>'
email_html += '\n<table width=' + WIDTH + '>'
email_html += '\n<tr><td class=center>Generated by Icinga 2 with data from Icinga 2'
if grafana.panelID:
    email_html += ', Grafana'

if netbox.host or netbox.ip:
    email_html += ', Netbox'

email_html += '</td></tr>'
email_html += '\n</table><br>'
email_html += '\n</body></html>'

if DEBUG:
    print(email_html)

# Prepare email
msgRoot = MIMEMultipart('related')
msgRoot['Subject'] = email_subject
msgRoot['From'] = EMAILFROM
msgRoot['To'] = email_to
msgRoot.preamble = 'This is a multi-part message in MIME format.'

msgAlternative = MIMEMultipart('alternative')
msgRoot.attach(msgAlternative)

msgText = MIMEText(email_plain_text)
msgAlternative.attach(msgText)

msgText = MIMEText(email_html, 'html')
msgAlternative.attach(msgText)

# Attach images
if os.path.exists(ICINGA2LOGOPATH):
    fp = open(ICINGA2LOGOPATH, 'rb')
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
    smtp.connect(EMAILSERVER)
except socket.error as e:
    print("Unable to connect to SMTP server '" + EMAILSERVER + "': " + e.strerror)
    os.sys.exit(e.errno)

if EMAILUSERNAME and EMAILPASSWORD:
    smtp.login(EMAILUSERNAME, EMAILPASSWORD)

try:
    smtp.sendmail(EMAILFROM, email_to, msgRoot.as_string())
    smtp.quit()
except Exception as e:
    print("Cannot send mail using SMTP: " + e.message)
    os.sys.exit(e.errno)

os.sys.exit(0)
