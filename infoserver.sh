#!/bin/bash

SERVICE_NAME="nfsuinfoserver"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
INSTALL_SCRIPT_PATH=$(dirname "$(realpath "$0")")  # Path to the directory containing this script
SCRIPT_PATH="${INSTALL_SCRIPT_PATH}/infoserver.py"

install_service() {
    # Options after "install" go to infoserver.py, e.g. --no-holepunch / --no-board
    local args=""
    for arg in "$@"; do
        if [[ ! "$arg" =~ ^--[a-z-]+$ ]]; then
            echo "Unknown option: $arg"
            exit 1
        fi
        args+=" $arg"
    done
    echo "Installing ${SERVICE_NAME} service${args:+ with$args}..."
    
    # Create the service file
    cat << EOF | sudo tee "${SERVICE_FILE}" > /dev/null
[Unit]
Description=NFSU Info Server
After=network.target

[Service]
Type=simple
User=$(whoami)
ExecStart=/usr/bin/python3 ${SCRIPT_PATH}${args}
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}"
    sudo systemctl restart "${SERVICE_NAME}"   # restart: installing again with other options takes effect
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
        shift
        install_service "$@"
        ;;
    remove)
        remove_service
        ;;
    restart)
        restart_service
        ;;
    ban|unban)
        # board.py ban <ip> [reason] / unban <ip>; the running server picks it up
        /usr/bin/python3 "${INSTALL_SCRIPT_PATH}/board.py" "$@"
        ;;
    *)
        echo "Usage: $0 {install [--no-holepunch] [--no-board]|remove|restart|ban <ip> [reason]|unban <ip>}"
        exit 1
esac

exit 0
