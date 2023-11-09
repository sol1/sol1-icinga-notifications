#!/usr/bin/env python3

import json
import re
from enum import Enum
from loguru import logger


class DirectorCommandType(Enum):
    """Director basket vars for a commands methods_execute property
    """
    COMMAND = "PluginCommand"
    NOTIFICATION = "PluginNotification"

    def prefix(self):
        return ObjectPrefix[self.name].value

    def template(self):
        return DirectorTemplateType[self.name].value

    def label(self):
        return CommandLabel[self.name].value


class CommandLabel(Enum):
    """Labels used to identify different command objects for humans
    """
    COMMAND = "check"
    NOTIFICATION = "notification"


class DirectorTemplateType(Enum):
    """Director basket template types
    """
    COMMAND = "CommandTemplate"
    SERVICE = "ServiceTemplate"
    HOST = "HostTemplate"
    NOTIFICATION = "NotificationTemplate"


class ObjectPrefix(Enum):
    """Prefix's used in object names for different objects types
    """
    COMMAND = "cmd"
    COMMAND_TEMPLATE = "cmdt"
    SERVICE = "srv"
    SERVICE_TEMPLATE = "srvt"
    SERVICE_GROUP = "srvg"
    HOST = "hst"
    HOST_TEMPLATE = "hstt"
    HOST_GROUP = "hstg"
    NOTIFICATION = "not"
    NOTIFICATION_TEMPLATE = "nott"

class DataFieldType(Enum):
    str = "Icinga\\Module\\Director\\DataType\\DataTypeString"
    bool = "Icinga\\Module\\Director\\DataType\\DataTypeBoolean"
    int = "Icinga\\Module\\Director\\DataType\\DataTypeNumber"
    list = "Icinga\\Module\\Director\\DataType\\DataTypeArray"

DEFAULT_ARGS = {
    "host_name": {
        "icinga_value": "$host.name$",
        "description": "Host object name",
        "order": 10,
        "type": DataFieldType.str.value},
    "host_displayname": {
        "icinga_value": "$host.display_name$",
        "description": "Host display name",
        "order": 10,
        "type": DataFieldType.str.value},
    "host_display_name": {
        "icinga_value": "$host.display_name$",
        "description": "Host display name",
        "order": 10,
        "type": DataFieldType.str.value},
    "host_address": {
        "icinga_value": "$host.address$",
        "description": "Host fqdn/address",
        "order": 10,
        "type": DataFieldType.str.value},
    "host_state": {
        "icinga_value": "$host.state$",
        "description": "Host state",
        "order": 10,
        "type": DataFieldType.str.value},
    "host_state_last": {
        "icinga_value": "$host.last_state$",
        "description": "Host state before current check run",
        "order": 10,
        "type": DataFieldType.str.value},
    "host_output": {
        "icinga_value": "$host.ouptut$",
        "description": "Host output",
        "order": 10,
        "type": DataFieldType.str.value},
    "service_name": {
        "icinga_value": "$service.name$",
        "description": "Service object name",
        "order": 15,
        "type": DataFieldType.str.value},
    "service_displayname": {
        "icinga_value": "$service.display_name$",
        "description": "Service display name",
        "order": 15,
        "type": DataFieldType.str.value},
    "service_display_name": {
        "icinga_value": "$service.display_name$",
        "description": "Service display name",
        "order": 15,
        "type": DataFieldType.str.value},
    "service_state": {
        "icinga_value": "$service.state$",
        "description": "Service state",
        "order": 15,
        "type": DataFieldType.str.value},
    "service_state_last": {
        "icinga_value": "$service.last_state$",
        "description": "Service state before current check run",
        "order": 15,
        "type": DataFieldType.str.value},
    "service_output": {
        "icinga_value": "$service.output$",
        "description": "Service output",
        "order": 15,
        "type": DataFieldType.str.value},
    "notification_author": {
        "icinga_value": "$notification.author$",
        "description": "Notification Author",
        "order": 20,
        "type": DataFieldType.str.value},
    "notification_comment": {
        "icinga_value": "$notification.comment$",
        "description": "Notification comment",
        "order": 20,
        "type": DataFieldType.str.value},
    "notification_type": {
        "icinga_value": "$notification.type$",
        "description": "Notification type",
        "order": 20,
        "type": DataFieldType.str.value},
}


class DirectorBasket:
    def __init__(self, name: str, icinga_var_prefix: str = None):
        self.director_basket = {}
        # name should be something like 'Enhanced Email'
        self.name = name

        self.icinga_var_prefix = icinga_var_prefix
        if self.icinga_var_prefix is None:
            self.icinga_var_prefix = f"{self.icinga_safe_name(self.name)}"

    @staticmethod
    def icinga_safe_name(name):
        return re.sub(r'\W+', '_', name).lower()

    def command(self, command, command_name, command_type: DirectorCommandType = DirectorCommandType.COMMAND.value, timeout: str = "60"):
        if "Command" not in self.director_basket:
            self.director_basket["Command"] = {}
        self.director_basket["Command"][command_name] = {
            "arguments": {},
            "command": command,
            "fields": [],
            "methods_execute": command_type,
            "object_name": command_name,
            "object_type": "object",
            "timeout": timeout
        }

    def commandArgument(self, command_name, argument, description='', value=None, if_set=None, order: int = None, ):
        _arg = {
            "description": description,
        }
        # can only be value or if_set not both
        if value:
            _arg['value'] = f"${value}$"
        elif if_set:
            _arg['if_set'] = f"${if_set}$"

        if order:
            _arg['order'] = order

        self.director_basket["Command"][command_name]["arguments"][argument] = _arg

    def template(self, name: str, command_name, template_type: str = DirectorTemplateType.NOTIFICATION.value, imports: list = []):
        if template_type not in self.director_basket:
            self.director_basket[template_type] = {}
        self.director_basket[template_type][name] = {
            "command": command_name,
            "fields": [],
            "object_name": name,
            "object_type": "template",
            "vars": {}
        }
        if imports:
            self.director_basket[template_type][name]['imports'] = imports


    def templateFields(self, template_name, id, template_type: str = DirectorTemplateType.NOTIFICATION.value, is_required="n", var_filter="null"):
        _field = {
            "datafield_id": id,
            "is_required": is_required,
            "var_filter": var_filter
        }
        self.director_basket[template_type][template_name]['fields'].append(_field)

    def templateVars(self, template_name, var_name, value, template_type: str = DirectorTemplateType.NOTIFICATION.value):
        self.director_basket[template_type][template_name]['vars'][var_name] = value

    def datafield(self, id, arg_name, arg_caption="", arg_description = None, datatype=DataFieldType.str, format=None, visability="visible", category=None):
        if arg_caption == "":
            arg_caption = arg_name
        if "Datafield" not in self.director_basket:
            self.director_basket["Datafield"] = {}
        self.director_basket["Datafield"][id] = {
            "varname": arg_name,
            "caption": arg_caption,
            "description": arg_description,
            "datatype": datatype,
            "format": format,
            "settings": {
                "visibility": visability
            },
            "category": category
        }


class DirectorBasketNotificationCommand(DirectorBasket):
    """Creates a director basket for a notification command including command plus common, host and service templates

    Args:
        name (str): Proper name for notification eg: Enhanced Email
        icinga_var_prefix (str, optional): Prefix for icinga variables associated with the command eg: enhanced_email_notification. Defaults to None.
        command_name (str, optional): Icinga object name for the command. Defaults to None, if None will be automatically generated.
        id (int, optional): id start value used in baskets. Defaults to 1111.
    """    
    def __init__(self, name: str, icinga_var_prefix: str = None, command_name: str = None, id: int = 1111, args: list = []):
        super().__init__(name, icinga_var_prefix)
        self.command_name = command_name
        if self.command_name is None:
            self.command_name = f"{ObjectPrefix.COMMAND.value}_{DirectorCommandType.NOTIFICATION.label()}_{self.icinga_safe_name(self.name)}"
        self.id = id
        self.args = args
        self.build()

    def build(self):
        self.command(command="test.py", command_name=self.command_name, command_type=DirectorCommandType.NOTIFICATION.value)
        self.template(
            name=f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icinga_safe_name(self.name)}",
            command_name=self.command_name,
            template_type=DirectorTemplateType.NOTIFICATION.value
        )
        self.template(
            name=f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icinga_safe_name(self.name)}_host",
            template_type=DirectorTemplateType.NOTIFICATION.value,
            command_name=self.command_name, imports=[f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.name}"]
        )
        self.template(
            name=f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icinga_safe_name(self.name)}_service",
            template_type=DirectorTemplateType.NOTIFICATION.value,
            command_name=self.command_name, imports=[f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.name}"]
        )

        for arg in self.args.keys():
            logger.debug(arg)
            logger.debug(self.args[arg])
            self.commandArgument(
                command_name=self.command_name, 
                argument=self.args[arg]['arg'], 
                description=self.args[arg]['description'], 
                value=f"{self.icinga_var_prefix}_{arg}", 
                order=self.args[arg]['order']
            )
            self.datafield(
                id=self.id, 
                arg_name=f"{self.icinga_var_prefix}_{arg}",
                arg_caption=arg.replace('_', ' ').capitalize(), 
                arg_description=self.args[arg]['description'], 
                datatype=self.args[arg]['type']
            )
            if "host_state" in arg or "host_output" in arg:
                self.addtoTemplate(f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icinga_safe_name(self.name)}_host", arg)
            elif "service_" in arg:
                self.addtoTemplate(f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icinga_safe_name(self.name)}_service", arg)
            else:
                self.addtoTemplate(f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icinga_safe_name(self.name)}", arg)
            self.id += 1
    
    def addtoTemplate(self, template_name, arg):
        self.templateFields(
            template_name=template_name, 
            id=self.id,
            template_type=DirectorTemplateType.NOTIFICATION.value,
        )
        if self.args[arg].get('icinga_value', None):
            self.templateVars(
                template_name=template_name, 
                var_name=f"{self.icinga_var_prefix}_{arg}",
                value=self.args[arg]['icinga_value'],
                template_type=DirectorTemplateType.NOTIFICATION.value
            )


def getSettingsParserDict(settings):
    _args = {}
    exclude_args = ['print_config', 'build_config']
    for arg in settings._getArgVarList():
        logger.debug(arg)
        if arg[0] in exclude_args:
            logger.warning(f"Skipping argument: {arg[0]}")
        elif arg[0] in DEFAULT_ARGS:
            _args[arg[0]] = DEFAULT_ARGS[arg[0]]
            _args[arg[0]]["arg"] = settings.makeArg(arg[0])
        else:
            _args[arg[0]] = {     
                "arg": settings.makeArg(arg[0]),   
                "icinga_value": "",
                "description": "",
                "order": 25,
                "type": DataFieldType[type(arg[2]).__name__].value}
    return _args

## TODO: This requires the parser itself before parse_args() is called to get more than key and value 
# for action in parser._actions:
#     # Skip the special 'help' action
#     if action.dest != 'help':
#         print(f"Python variable name (dest): {action.dest}")
#         print(f"Description (help): {action.help}")
#         print(f"Value type: {action.type}")
# def getArgsDict(args):
#     logger.success(args)
#     _args = {}
#     exclude_args = ['print_config', 'build_config']
#     for arg in args._actions():
#         logger.debug(arg)
#         if arg[0] in exclude_args:
#             logger.warning(f"Skipping argument: {arg[0]}")
#         elif arg[0] in DEFAULT_ARGS:
#             _args[arg[0]] = DEFAULT_ARGS[arg[0]]
#             _args[arg[0]]["arg"] = settings.makeArg(arg[0])
#         else:
#             logger.debug(type(arg[2]))
#             _args[arg[0]] = {     
#                 "arg": settings.makeArg(arg[0]),   
#                 "icinga_value": "",
#                 "description": "",
#                 "order": 25,
#                 "type": DataFieldType[type(arg[2]).__name__].value}
#     return _args

