#!/bin/bash

# Initialize boolean switches as false
ALL=false
ENHANCED_EMAIL=false
REQUEST_TRACKER=false
ICINGA2_SCRIPT_DIR="/etc/icinga2/scripts"
ICINGA2_USER="nagios"


# Check the provided arguments
for arg in "$@"; do
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

install_requirements() {
    python3 -m pip install -r requirements.txt
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

if $ALL || $ENHANCED_EMAIL; then
    echo "Deploying Enhanced Email Notifications"
    deploy_enhanced_email
fi

if $ALL || $REQUEST_TRACKER; then
    echo "Deploying Request Tracker Notifications"
    deploy_request_tracker
fi

if $ALL || $SLACK; then
    echo "Deploying Slack Notifications"
    deploy_slack
fi

if $ALL || $ENHANCED_EMAIL || $REQUEST_TRACKER; then
    deploy_library
    install_requirements
fi

