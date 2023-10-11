#!/bin/bash

# Initialize boolean switches as false
ALL=false
ENHANCED_EMAIL=false
REQUEST_TRACKER=false
SLACK=false
PUSHOVER=false
REQUIREMENTS=false
# default icinga2 user
ICINGA2_USER="nagios"

# hardcode the script dir, change this if you want another base directory
ICINGA2_SCRIPT_DIR="/etc/icinga2/scripts"


# Check the provided arguments
while [[ "$#" -gt 0 ]]; do
    arg="$1"
    case $arg in
        -a|--all)
        ALL=true
        shift # Remove --enhanced-email from processing
        ;;
        -e|--enhanced-email)
        ENHANCED_EMAIL=true
        shift # Remove --enhanced-email from processing
        ;;
        -r|--request-tracker)
        REQUEST_TRACKER=true
        shift # Remove --request-tracker from processing
        ;;
        -s|--slack)
        SLACK=true
        shift # Remove --slack from processing
        ;;
        -s|--pushover)
        PUSHOVER=true
        shift # Remove --pushover from processing
        ;;
        -p|--requirements)
        REQUIREMENTS=true
        shift # Remove --requirements from processing
        ;;
        -u|--icinga2-user)
        ICINGA2_USER=$2
        shift # Remove --icinga-user from processing
        shift # Remove --icinga-user from value
        ;;
        *)
        # Unknown option
        echo "Unknown argument: $arg"
        exit 1
        ;;
    esac
done

deploy_library() {
    mkdir -p "$ICINGA2_SCRIPT_DIR/lib/"
    echo "  copying ./src/lib/* to $ICINGA2_SCRIPT_DIR/lib/" 
    cp ./src/lib/* "$ICINGA2_SCRIPT_DIR/lib/" 
    chown $ICINGA2_USER:$ICINGA2_USER "$ICINGA2_SCRIPT_DIR/lib/*"
}

install_all_requirements() {
    python3 -m pip install -r requirements.txt
}

install_enhanced_email_requirements() {
    python3 -m pip install -r requirements-enhanced-email.txt
}

install_request_tracker_requirements() {
    python3 -m pip install -r requirements-request-tracker.txt
}

install_slack_requirements() {
    python3 -m pip install -r requirements-slack.txt
}

install_pushover_requirements() {
    python3 -m pip install -r requirements-pushover.txt
}

deploy_config() {
    file=$1
    file_name=$(basename "$file")
    if [[ ! -f "$ICINGA2_SCRIPT_DIR/config/$file_name" ]]; then 
        echo "  copying $file to $ICINGA2_SCRIPT_DIR/config/$file_name" 
        cp "$file" "$ICINGA2_SCRIPT_DIR/config/"
        chown $ICINGA2_USER:$ICINGA2_USER "$ICINGA2_SCRIPT_DIR/config/*"
    else
        echo "  config $file_name exists in $ICINGA2_SCRIPT_DIR/config/" 
    fi
}

deploy_enhanced_email() {
    deploy_library
    deploy_config ./src/config/enhanced-mail-notification.json
    cp ./src/enhanced-mail-notification.py "$ICINGA2_SCRIPT_DIR" 
    chown $ICINGA2_USER:$ICINGA2_USER "$ICINGA2_SCRIPT_DIR/enhanced-mail-notification.py"
    chmod +x "$ICINGA2_SCRIPT_DIR/enhanced-mail-notification.py"
}

deploy_request_tracker() {
    deploy_config ./src/config/request-tracker-notification.json
    cp ./src/request-tracker-notification.py "$ICINGA2_SCRIPT_DIR" 
    chown $ICINGA2_USER:$ICINGA2_USER "$ICINGA2_SCRIPT_DIR/request-tracker-notification.py"
    chmod +x "$ICINGA2_SCRIPT_DIR/request-tracker-notification.py"
}

deploy_slack() {
    cp ./src/slack-notification.py "$ICINGA2_SCRIPT_DIR" 
    chown $ICINGA2_USER:$ICINGA2_USER "$ICINGA2_SCRIPT_DIR/slack-notification.py"
    chmod +x "$ICINGA2_SCRIPT_DIR/slack-notification.py"
}

deploy_pushover() {
    cp ./src/pushover-notification.py "$ICINGA2_SCRIPT_DIR" 
    chown $ICINGA2_USER:$ICINGA2_USER "$ICINGA2_SCRIPT_DIR/pushover-notification.py"
    chmod +x "$ICINGA2_SCRIPT_DIR/pushover-notification.py"
}

if $ALL || $ENHANCED_EMAIL; then
    echo "Deploying Enhanced Email Notifications"
    deploy_enhanced_email
    if $REQUIREMENTS; then
        install_enhanced_email_requirements
    fi
fi

if $ALL || $REQUEST_TRACKER; then
    echo "Deploying Request Tracker Notifications"
    deploy_request_tracker
    if $REQUIREMENTS; then
        install_request_tracker_requirements
    fi
fi

if $ALL || $SLACK; then
    echo "Deploying Slack Notifications"
    deploy_slack
    if $REQUIREMENTS; then
        install_slack_requirements
    fi
fi

if $ALL || $PUSHOVER; then
    echo "Deploying Pushover Notifications"
    deploy_pushover
    if $REQUIREMENTS; then
        install_pushover_requirements
    fi
fi

if $ALL || $ENHANCED_EMAIL || $REQUEST_TRACKER || $SLACK || $PUSHOVER; then
    deploy_library
    if $REQUIREMENTS; then
        install_all_requirements
    fi
fi

