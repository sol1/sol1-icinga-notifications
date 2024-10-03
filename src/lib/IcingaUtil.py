#!/usr/bin/env python3

import argparse
import re
from enum import Enum
from loguru import logger


class DirectorCommandType(Enum):
    """Director basket vars for a commands methods_execute property
    """
    COMMAND = "PluginCommand"
    NOTIFICATION = "PluginNotification"
    # EVENT = "PluginEvent"

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
    # EVENT = "event"


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
    """Director Data Field Types Helper
    """
    # from director:register-hooks.php
    bool = "Icinga\\Module\\Director\\DataType\\DataTypeBoolean"
    datalist = "Icinga\\Module\\Director\\DataType\\DataTypeDatalist"
    dict = "Icinga\\Module\\Director\\DataType\\DataTypeDictionary"
    director_obj = "Icinga\\Module\\Director\\DataType\\DataTypeDirectorObject"
    int = "Icinga\\Module\\Director\\DataType\\DataTypeNumber"
    float = "Icinga\\Module\\Director\\DataType\\DataTypeNumber"
    list = "Icinga\\Module\\Director\\DataType\\DataTypeArray"
    array = "Icinga\\Module\\Director\\DataType\\DataTypeArray"
    sql_query = "Icinga\\Module\\Director\\DataType\\DataTypeSqlQuery"
    sql = "Icinga\\Module\\Director\\DataType\\DataTypeSqlQuery"
    str = "Icinga\\Module\\Director\\DataType\\DataTypeString"


# A set of values for commonly used values when interacting with icinga
DEFAULT_ARGS = {
    "debug": {
        "icinga_value": "",
        "description": "Sets logging to debug",
        "order": 5,
        "type": DataFieldType.bool.value},
    "disable_log_file": {
        "icinga_value": "Disables the log file",
        "description": "",
        "order": 5,
        "type": DataFieldType.bool.value},
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
        "icinga_value": "$host.output$",
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
    """Icinga Director basket builder
    """

    def __init__(self):
        self.director_basket = {}
        # name should be something like 'Enhanced Email'

    @staticmethod
    def icingaSafeName(name: str) -> str:
        """Sanatize strings into a Icinga Object safe format

        Args:
            name (str): name you want to sanatize

        Returns:
            str: sanatized string of the passed in name
        """
        return re.sub(r'\W+', '_', name).lower()

    def command(self,
                command,
                command_name: str,
                command_type: str = DirectorCommandType.COMMAND.value,
                timeout: str = "60",
                disabled: bool = False
                ):
        """Adds a command to the director basket

        Args:
            command (_type_): The command script
            command_name (str): Icinga object name for the command
            command_type (str, optional): Icinga command methods_execute type string. Defaults to DirectorCommandType.COMMAND.value.
            timeout (str, optional): Timeout for command. Defaults to "60".
            disabled (bool, optional): Is the command disabled. Defaults to False.
        """

        if "Command" not in self.director_basket:
            self.director_basket["Command"] = {}

        self.director_basket["Command"][command_name] = {
            "arguments": {},
            "command": command,
            "disabled": disabled,
            "fields": [],
            "methods_execute": command_type,
            "object_name": command_name,
            "object_type": "object",
            "timeout": timeout
        }

    def commandArgument(self,
                        command_name: str,
                        argument: str,
                        description: str = '',
                        value: str = None,
                        if_set: str = None,
                        order: int = None,
                        skip_key: bool = False,
                        repeat_key: bool = False
                        ):
        """Adds an argument to an existing command

        Args:
            command_name (str): Icinga object name for the command
            argument (str): Argument name
            description (str, optional): Argument Description. Defaults to ''.
            value (str, optional): Name of the Icinga variable to assign this check. Defaults to None.
            if_set (str, optional): Name of the Icinga variable to assign this check for key only arguments. Defaults to None.
            order (int, optional): Order for the argument. Defaults to None.
            skip_key (bool, optional): Icinga will use the argument value only skipping the key. Defaults to False.
            repeat_key (bool, optional): Icinga will take arrays and use the key with each item individually. Defaults to False.
        """
        _arg = {
            "description": description,
            'skip_key': skip_key,
            'repeat_key': repeat_key
        }
        # can only be value or if_set not both
        if value:
            _arg['value'] = f"${value}$"
        elif if_set:
            _arg['set_if'] = f"${if_set}$"

        if order:
            _arg['order'] = order

        self.director_basket["Command"][command_name]["arguments"][argument] = _arg

    def template(self, name: str, command_name, disabled: bool = False, imports: list = [], template_type: str = DirectorTemplateType.NOTIFICATION.value, imports: list = [], timeout: str = None):
        if template_type not in self.director_basket:
            self.director_basket[template_type] = {}

        self.director_basket[template_type][name] = {
            "command": command_name,
            "disabled": disabled,
            "fields": [],
            "imports": imports,
            "object_name": name,
            "object_type": "template",
            "timeout": timeout,
            "vars": {},
        }
        if imports:
            self.director_basket[template_type][name]['imports'] = imports

    def templateFields(self, template_name, id, template_type: str = DirectorTemplateType.NOTIFICATION.value, is_required="n", var_filter="null"):
        _field = {
            "datafield_id": id,
            "is_required": is_required,
            "var_filter": var_filter
        }
        self.director_basket[template_type][template_name]['fields'].append(
            _field)

    def templateVars(self, template_name, var_name, value, template_type: str = DirectorTemplateType.NOTIFICATION.value):
        self.director_basket[template_type][template_name]['vars'][var_name] = value

    def datafield(self, id: int, arg_name, arg_caption="", arg_description=None, datatype=DataFieldType.str, format=None, visability="visible", category=None):
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
    """Creates a director basket for a notification command including command plus datafields, host and service templates

    Args:
        name (str): Proper name for notification eg: Enhanced Email
        icinga_var_prefix (str, optional): Prefix for icinga variables associated with the command eg: enhanced_email_notification. Defaults to None.
        command_name (str, optional): Icinga object name for the command. Defaults to None, if None will be automatically generated.
        id (int, optional): id start value used in baskets. Defaults to 1111.
    """

    def __init__(self, name: str, icinga_var_prefix: str = None, command: str = '', command_name: str = None, id: int = 1111, args: list = []):
        super().__init__()
        self.name = name

        self.icinga_var_prefix = icinga_var_prefix
        if self.icinga_var_prefix is None:
            self.icinga_var_prefix = f"{self.icingaSafeName(self.name)}"

        self.command_name = command_name
        if self.command_name is None:
            self.command_name = f"{ObjectPrefix.COMMAND.value}_{DirectorCommandType.NOTIFICATION.label()}_{self.icingaSafeName(self.name)}"
        self.id = id
        self.args = args
        self.command_path = command
        self.build()

    def build(self):
        self.command(command=self.command_path,
                     command_name=self.command_name,
                     command_type=DirectorCommandType.NOTIFICATION.value)
        self.template(
            name=f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icingaSafeName(self.name)}",
            command_name=self.command_name,
            template_type=DirectorTemplateType.NOTIFICATION.value
        )
        self.template(
            name=f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icingaSafeName(self.name)}_host",
            template_type=DirectorTemplateType.NOTIFICATION.value,
            imports=[f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.name}"]
        )
        self.template(
            name=f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icingaSafeName(self.name)}_service",
            template_type=DirectorTemplateType.NOTIFICATION.value,
            imports=[f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.name}"]
        )

        for arg in self.args.keys():
            logger.debug(arg)
            logger.debug(self.args[arg])
            command_dict = self.args[arg][0]
            self.commandArgument(
                command_name=self.command_name,
                argument=command_dict['arg'],
                description=command_dict.get('help', command_dict.get('description', '')),
                value=f"{self.icinga_var_prefix}_{arg}" if command_dict.get('type', None) != 'bool' else '',
                if_set=f"{self.icinga_var_prefix}_{arg}" if command_dict.get('type', None) == 'bool' else '',
                order=command_dict.get('order', ""),
                skip_key=command_dict.get('skip_key', False)
            )
            self.datafield(
                id=self.id,
                arg_name=f"{self.icinga_var_prefix}_{arg}",
                arg_caption=arg.replace('_', ' ').capitalize(),
                arg_description=command_dict['description'],
                datatype=DataFieldType[command_dict.get('type', 'str')].value
            )
            if "host_state" in arg or "host_output" in arg:
                self.addtoTemplate(
                    f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icingaSafeName(self.name)}_host", arg, command_dict.get('icinga_value', None))
            elif "service_" in arg:
                self.addtoTemplate(
                    f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icingaSafeName(self.name)}_service", arg, command_dict.get('icinga_value', None))
            else:
                self.addtoTemplate(
                    f"{ObjectPrefix.NOTIFICATION_TEMPLATE.value}_{self.icingaSafeName(self.name)}", arg, command_dict.get('icinga_value', None))
            self.id += 1

    def addtoTemplate(self, template_name, arg, value):
        self.templateFields(
            template_name=template_name,
            id=self.id,
            template_type=DirectorTemplateType.NOTIFICATION.value,
        )
        # If there is a template value then set a template var with that value
        if value:
            self.templateVars(
                template_name=template_name,
                var_name=f"{self.icinga_var_prefix}_{arg}",
                value=value,
                template_type=DirectorTemplateType.NOTIFICATION.value
            )

class DirectorBasketCheckCommand(DirectorBasket):
    """Creates a director basket for a check command including command plus datafields, host and service templates

    Args:
        name (str): Proper name for check eg: Enhanced Email
        icinga_var_prefix (str, optional): Prefix for icinga variables associated with the command eg: enhanced_email_notification. Defaults to None.
        command_name (str, optional): Icinga object name for the command. Defaults to None, if None will be automatically generated.
        id (int, optional): id start value used in baskets. Defaults to 1111.
    """

    def __init__(self, name: str, icinga_var_prefix: str = None, command: str = '', command_name: str = None, id: int = 1111, args: list = []):
        super().__init__()
        self.name = name

        self.icinga_var_prefix = icinga_var_prefix
        if self.icinga_var_prefix is None:
            self.icinga_var_prefix = f"{self.icingaSafeName(self.name)}"

        self.command_name = command_name
        if self.command_name is None:
            self.command_name = f"{ObjectPrefix.COMMAND.value}_{DirectorCommandType.COMMAND.label()}_{self.icingaSafeName(self.name)}"
        self.id = id
        self.args = args
        self.command_path = command
        self.build()

    def build(self):
        self.command(command=self.command_path,
                     command_name=self.command_name,
                     command_type=DirectorCommandType.COMMAND.value)

        self.template(
            name=f"{ObjectPrefix.SERVICE_TEMPLATE.value}_{self.icingaSafeName(self.name)}",
            command_name=self.command_name,
            template_type=DirectorTemplateType.SERVICE.value
        )

        groups = []
        for arg in self.args.keys():
            for group in self.args[arg]:
                if group.get('group', None):
                    groups.append(group['group'])
        
        for group in list(set(groups)):
            self.template(
                name=f"{ObjectPrefix.SERVICE_TEMPLATE.value}_{self.icingaSafeName(self.name)}_{group}",
                template_type=DirectorTemplateType.SERVICE.value,
                imports=[f"{ObjectPrefix.SERVICE_TEMPLATE.value}_{self.icingaSafeName(self.name)}"]
            )


        for arg in self.args.keys():
            logger.debug(arg)
            logger.debug(self.args[arg])
            command_dict = self.args[arg][0]
            self.commandArgument(
                command_name=self.command_name,
                argument=command_dict['arg'],
                description=command_dict.get('help', command_dict.get('description', '')),
                value=f"{self.icinga_var_prefix}_{arg}" if command_dict.get('type', None) != 'bool' else '',
                if_set=f"{self.icinga_var_prefix}_{arg}" if command_dict.get('type', None) == 'bool' else '',
                order=command_dict.get('order', ""),
                skip_key=command_dict.get('skip_key', False)
            )
            self.datafield(
                id=self.id,
                arg_name=f"{self.icinga_var_prefix}_{arg}",
                arg_caption=arg.replace('_', ' ').capitalize(),
                arg_description=command_dict['description'],
                datatype=DataFieldType[command_dict.get('type', 'str')].value
            )
            for group_dict in self.args[arg]:
                if group_dict.get('group', None):
                    self.addtoTemplate(
                        f"{ObjectPrefix.SERVICE_TEMPLATE.value}_{self.icingaSafeName(self.name)}_{group}", 
                        arg, 
                        command_dict.get('icinga_value', None)
                        )
                else:
                    self.addtoTemplate(
                        f"{ObjectPrefix.SERVICE_TEMPLATE.value}_{self.icingaSafeName(self.name)}", 
                        arg, 
                        command_dict.get('icinga_value', None)
                        )
            self.id += 1
       
    def addtoTemplate(self, template_name, arg, value):
        self.templateFields(
            template_name=template_name,
            id=self.id,
            template_type=DirectorTemplateType.SERVICE.value,
        )
        # If there is a template value then set a template var with that value
        if value:
            self.templateVars(
                template_name=template_name,
                var_name=f"{self.icinga_var_prefix}_{arg}",
                value=value,
                template_type=DirectorTemplateType.SERVICE.value
            )


def getSettingsParserArgumentsDict(settings, exclude_args: list = ['print_config', 'build_config']) -> dict:
    """ Generate an Argument Dictionary from a SettingsParser class

    Args:
        settings (SettingsParser): Initialized SettingsParser class
        exclude_args (list): list of argument names to exclude. Defaults to ['print_config', 'build_config']

    Returns:
        dict: Formated dict with keys of each argument and fields DirectorBasketNotificationCommand and DirectorBasketCheckCommand expect
    """    
    _args = {}
    for arg in settings._getArgVarList():
        logger.debug(arg)
        if arg[0] in exclude_args:
            logger.warning(f"Skipping argument: {arg[0]}")
        else:
            _args.update(
                makeDirectorArg(name=arg[0],
                                arg=settings.makeArg(arg[0]),
                                order=DEFAULT_ARGS.get(arg[0], {}).get('order', 25),    # make the default win if it is set else 25
                                field_type=type(arg[2]).__name__,
                                defaults=DEFAULT_ARGS.get(arg[0], {})
                                )
            )
    return _args

def getArgparseParserArgumentsDict(parser: argparse.ArgumentParser, exclude_args: list = ['help']) -> dict:
    """Create a arguments dict from argparse. Each element in the dict contains a list of arguments as you can have duplicate arguments.

    Args:
        parser (argparse.ArgumentParser): Argparse parser before parse_args() is called
        exclude_args (list, optional): List of argument dest's to exclude. Defaults to ['help'].

    Returns:
        dict: { argument_name: [{ argument_values }]}
    """    
    _args = {}
    order = 10
    def _getActions(_parser, order, group = ""):
        nonlocal _args
        for action in _parser._actions:
            logger.debug(vars(action))
            if action.dest in exclude_args:
                logger.warning(f"Skipping argument: {action.dest}")
            else:
                if action.dest not in _args:
                    _args[action.dest] = []    
                _args[action.dest].append(
                    makeDirectorArg(name=action.dest,
                                    arg=sorted(action.option_strings, key=len, reverse=True)[0] if len(action.option_strings) > 0 else '',
                                    help=action.help,
                                    order=order,
                                    field_type=action.type.__name__ if action.type is not None else '',
                                    defaults=DEFAULT_ARGS.get(action.dest, {}),
                                    group=group,
                                    skip_key=False if action.type is not None else True
                                    )
                )

    # Get the default actions
    _getActions(parser, order)
    order += 10
    # Get the subparser actions, could contain duplicates
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, subparser in action.choices.items():
                _getActions(subparser, order, name)
    return _args


def makeDirectorArg(name: str, field_type: str = None, arg: str = None, icinga_value: str = '', description: str = '', help: str = '', order: int = None, group: str = "", skip_key: bool = False, defaults: dict = {}) -> dict:
    """Create a dict of argument values

    Args:
        name (str): Argument pythonic name: eg hello_world
        field_type (str, optional): Data Field Type. Defaults to None.
        arg (str, optional): command argument: eg --hello-world. Defaults to None.
        icinga_value (str, optional): Value to assign argument in templates: eg $host_name$. Defaults to ''.
        description (str, optional): Short field desciption. Defaults to ''.
        help (str, optional): Help information. Defaults to ''.
        order (int, optional): argument order. Defaults to None.
        defaults (dict, optional): Dictionary containing default values for this arg only, passed in values override defaults. Defaults to {}.

    Returns:
        dict: Formated dict with fields DirectorBasketNotificationCommand and DirectorBasketCheckCommand expect
    """    
    
    _arg = defaults
    if "arg" not in _arg or arg:
        _arg["arg"]: arg
    if "description" not in _arg or description:
        _arg["description"] = description
    if "group" not in _arg or group:
        _arg["group"] = group
    if "help" not in _arg or help:
        _arg["help"] = help
    if "icinga_value" not in _arg or icinga_value:
        _arg["icinga_value"] = icinga_value
    if "order" not in _arg or order:
        _arg["order"] = order
    if "type" not in _arg or order:
        _arg["type"] = field_type
    if "skip_key" not in _arg or skip_key:
        _arg["skip_key"] = skip_key
    return _arg


