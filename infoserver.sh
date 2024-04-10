#!/bin/bash

SERVICE_NAME="nfsuinfoserver"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
INSTALL_SCRIPT_PATH=$(dirname "$(realpath "$0")")  # Path to the directory containing this script
SCRIPT_PATH="${INSTALL_SCRIPT_PATH}/infoserver.py"

install_service() {
    echo "Installing ${SERVICE_NAME} service..."
    
    # Create the service file
    cat << EOF | sudo tee "${SERVICE_FILE}" > /dev/null
[Unit]
Description=NFSU Info Server
After=network.target

[Service]
Type=simple
User=$(whoami)
ExecStart=/usr/bin/python3 ${SCRIPT_PATH}
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}"
    sudo systemctl start "${SERVICE_NAME}"
    echo "Service installed and started successfully."
}

remove_service() {
    echo "Removing ${SERVICE_NAME} service..."
    sudo systemctl stop "${SERVICE_NAME}" >/dev/null 2>&1
    sudo systemctl disable "${SERVICE_NAME}" >/dev/null 2>&1
    sudo rm -f "${SERVICE_FILE}"
    sudo systemctl daemon-reload
    echo "Service removed successfully."
}

restart_service() {
    echo "Restarting ${SERVICE_NAME} service..."
    sudo systemctl restart "${SERVICE_NAME}"
    echo "Service restarted."
}

case "$1" in
    install)
        install_service
        ;;
    remove)
        remove_service
        ;;
    restart)
        restart_service
        ;;
    *)
        echo "Usage: $0 {install|remove|restart}"
        exit 1
esac

exit 0
