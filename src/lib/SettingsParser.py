import argparse
import dataclasses
import json
import os
import sys


@dataclasses.dataclass
class SettingsParser:
    """SettingParser library used to read arguments, environment variables and config files into attributes set in a child class
    Usage: 
    @dataclasses.dataclass
    class Settings(SettingsParser):
        username: str = None
        password: str = None
        debug: bool = False
        
    def __post_init__(self):
        try:
            self._env_prefix: str = "NOTIFY_RT_"
            self.config_file = "/root/settings.json"
            self.loadEnvironmentVars()
            self.loadConfigFile()
        except Exception as e:
            print("Failed to initialize {e}")
            print(traceback.format_exc())
            sys.exit()

    settings = Settings()
    print(settings.username)


    Parent Attributes:
        Important: All attributes beginning with '_' are excluded as are any attributes added to the _exclude or _include lists below
        
        Attributes added to the exclude lists are excluded from the available attributes
            _exclude_from_args (list): Default []
            _exclude_from_file (list): Default []
            _exclude_from_env (list): Default []
        
        Attributes not added to the include lists are excluded from the available attributes unless the include list is empty, Default is empty ([])
            _include_from_args (list): Default []
            _include_from_file (list): Default []
            _include_from_env (list): Default []
            
        Prefix for environment variables: eg SettingsParser.foo = env SETTINGS_FOO        
            _env_prefix: str = "SETTINGS_"

        Prefix for arguments: eg SettingsParser.foo = argparse --my-foo        
            _args_prefix: str = "my-"

        Key name if the arguments are in a nested dictionary: eg SettingsParser.foo = { "my": { "foo": 123 } }        
            _json_dict_key: str = "my"

        Path to config file, can be left empty if you don't have a config file
            config_file: str = ''

        Config as a dict
            _config_dict: dict = ''
    """    
    # All attributes beginning with '_' are excluded as are any args added to the lists below for each part
    _exclude_from_args: list = dataclasses.field(default_factory=list)
    _exclude_from_file: list = dataclasses.field(default_factory=list)
    _exclude_from_env: list = dataclasses.field(default_factory=list)
    _include_from_args: list = dataclasses.field(default_factory=list)
    _include_from_file: list = dataclasses.field(default_factory=list)
    _include_from_env: list = dataclasses.field(default_factory=list)
    _env_prefix: str = "SETTINGS_"
    _args_prefix: str = ''
    _json_dict_key: str = None
    config_file: str = ''
    _config_dict: dict = ''

    # implied args format (class var, switch, value) (foo_bar, --foo-bar, value)
    def _getArgVarList(self):
        """Generates a list of tuples in the format (class attribute, switch, value) for valid arguments

        Returns:
            list: list of tuples (class attribute, switch, value)
        """        
        _list = []
        for key, value in dataclasses.asdict(self).items():
            if key in self._exclude_from_args or key.startswith('_'):
                continue
            if self._include_from_args and key not in self._include_from_args:
                continue
            _list.append((key, f'--{self._args_prefix}{key.replace("_", "-")}', value))
        return _list

    def loadArgs(self, args):
        """Iterates through the list of valid Class attributes arguments and if found in the 'args' parameter will set the Class attribute to the arg's value 

        Args:
            args (object): argparse object or other object which contain attributes matching Class attributes
        """
        for key in self._getArgVarList():
            if hasattr(args, key[0]):
                # Set class var from args var
                setattr(self, key[0], getattr(args, key[0]))

    # implied config format (class var, json var, value) (foo_bar, foo_bar, value)
    def _getConfigVarList(self):
        """Generates a list of tuples in the format (class attribute, json key, value) for valid config options

        Returns:
            list: list of tuples (class attribute, json key, value)
        """        
        _list = []
        for key, value in dataclasses.asdict(self).items():
            if key in self._exclude_from_file or key.startswith('_'):
                continue
            if self._include_from_file and key not in self._include_from_file:
                continue
            _list.append((key, key, value))
        return _list

    def loadConfigDict(self):
        """Load configuration from a Dictonary file then iterates through the list of valid Class attributes json keys and updates values if the Class attribute keys exist in the json
        """
        # if the _json_dict_key is set change the config to be the nested value if the _json_dict_key exists
        config = self._config_dict
        if self._json_dict_key:
            config = config.get(self._json_dict_key, {})
        for key in self._getConfigVarList():
            if key[1] in config:
                # Set class var with config key value
                setattr(self, key[0], config[key[1]])

    def loadConfigJsonFile(self):
        """Iterates through the list of valid Class attributes json keys and updates values if the Class attribute keys exist in the config dictionary
        """
        print(os.getcwd())
        print(self.config_file)
        if not os.path.exists(self.config_file):
            print(f"Error: The file '{self.config_file}' does not exist.")
            sys.exit(1)
        try:
            with open(self.config_file, 'r') as file:
                self._config_dict = json.load(file)
                self.loadConfigDict()
        except IOError as e:
            print(f"Error: Failed to open '{self.config_file}': {e}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse '{self.config_file}' as JSON: {e}")
            sys.exit(1)

    # implied config format (class var, env prefix + var upper, value) (foo_bar, SETTING_FOO_BAR, value)
    def _getEnvironmentVarList(self):
        """Generates a list of tuples in the format (class attribute, environment var, value) for valid environment variables

        Returns:
            list: list of tuples (class attribute, environment var, value)
        """        
        _list = []
        for key, value in dataclasses.asdict(self).items():
            if key in self._exclude_from_env or key.startswith('_'):
                continue
            if self._include_from_env and key not in self._include_from_env:
                continue
            _list.append((key, f'{self._env_prefix}{key.upper()}', value))
        return _list

    def loadEnvironmentVars(self):
        """Iterates through the list of valid Class attributes environment vars and tries to read them from the environment
        """
        for var in self._getEnvironmentVarList():
            # Set class var with env value or class var default
            setattr(self, var[0], os.getenv(var[1], var[2]))

    # Some helper functions to provide information about arguments and values
    def printEnvironmentVars(self, values = True):
        self._printList(self._getEnvironmentVarList(), values)

    def printArguments(self, values = True):
        self._printList(self._getArgVarList(), values)

    def _printList(self, var_list, values = True):
        for var in var_list:
            if values:
                print(f'{var[1]} = {var[2]}')
            else:
                print(var[1])

    def _init_args(self, description):
        parser = argparse.ArgumentParser(description=description)
        for arg in self._getArgVarList():
            if type(arg[2]) == bool:
                parser.add_argument(arg[1], action="store_true")
            else:
                parser.add_argument(arg[1], type=type(arg[2]), default=arg[2])
        return parser.parse_args()