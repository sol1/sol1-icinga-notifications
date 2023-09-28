# Icinga Notifications

This repository contains Icinga Notification scripts for 
- Enhanced Email
- Request Tracker
- Slack

These notification scripts have been created to work with Icinga configuration on disk or in Director. They pull their configuration from arguments, environment variables and on disk configuration.

This repository contains the notification scripts, shared libraries, dependant python libaries, an installation script, config examples for Icinga2 and Icingaweb2 Director import baskets.


## Installation
`deploy.sh` can be used to install the Notifications from this repository. 

It performs the following actions
- Installs repository shared libraries, always overrides existing, and sets permissions(destination: `/etc/icinga2/scripts/lib/`) 
- Installs python libraries with `python3 -m pip install`
- Copies default config if config doesn't exist and sets permissions (destination: `/etc/icinga2/scripts/config/`)
- Copies notification script, always overrides existing script, and sets permissions (destination: `/etc/icinga2/scripts/`)


### `Deploy.sh` Usage
Deploy Everything
```
deploy.sh --all
```

Deploy just a single Notification type
```
deploy.sh --enhanced-email
deploy.sh --request-tracker
deploy.sh --slack
```

Deploy everything for a specified user (default user: `nagios`)
```
deploy.sh --all --icinga2-user icinga2
```


## Configuration
### Enhanced Email
Once installed you will find the Enhanced Email Notification configuration in the `/etc/icinga2/scripts/config/` directory.

The configuration of settings for email, Icinga, Netbox and Grafana can be found in this file.

For configuration of the Notification command in Icinga itself refer to the `./icinga_conf/` examples or import the director baskets `./director_baskets/` available in this repository. 

### Request Tracker
Once installed you will find the Request Tracker Notification configuration in the `/etc/icinga2/scripts/config/` directory.

The configuration of connection settings to Request Tracker and Icinga can be found in this file.

For configuration of the Notification command in Icinga itself refer to the `./icinga_conf/` examples or import the director baskets `./director_baskets/` available in this repository. 

### Slack
There is no configuration files by default with slack notifications, the script will still look for configuration in `config/slack-notification.json` though.

For configuration of the Notification command in Icinga itself refer to the `./icinga_conf/` examples or import the director baskets `./director_baskets/` available in this repository. 

## Contributing
We welcome improvements to this project.

The best way to contribute is Create a ticket explaining the problem you are solving then submit a pull request. 

Please note that these Notification scripts are used by Sol1 in multiple production environments so any changes submitted that aren't backwards compatible are unlikely to be accepted as is.


## License
yes
