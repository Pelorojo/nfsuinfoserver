#!/usr/bin/env python3
# nfsuinfocentral TCP:10881 by Redhair
import socket
import os
import time

nfsuserver_path = os.path.dirname(os.path.abspath(__file__))

CENTRAL_REGISTRY_HOST = '0.0.0.0'  # Listen on all available interfaces
CENTRAL_REGISTRY_PORT = 10881
SERVERS_FILE = f"{nfsuserver_path}/infoservers.txt"

def handle_get_public_ip_list(client_socket):
    unique_ips = set()  # Store unique IP addresses
    with open(SERVERS_FILE, 'r') as f:
        for line in f:
            parts = line.strip().split(';')
            ip_port = parts[1]
            unique_ips.add(ip_port)

    sorted_ips = sorted(unique_ips)
    response = ' '.join(sorted_ips)

    client_socket.sendall(response.encode())
    client_socket.close()

def handle_registration(client_socket, address, data):

    if " " in data:
        action, server_host, server_port = data.split()
    else:
        if data == "LIST":
            handle_get_public_ip_list(client_socket)
        return
        
    client_ip, _ = address  # Extract the client IP address

    current_timestamp = int(time.time())  # Get the current UNIX timestamp

    server_info = f"{client_ip}:{server_port}"

    if action == "GG":
        print(f"Server at {client_ip}:{server_port} deregistered")
        # Remove server from the list of registered servers in the file
        with open(SERVERS_FILE, 'r') as f:
            lines = f.readlines()
        with open(SERVERS_FILE, 'w') as f:
            for line in lines:
                parts = line.strip().split(';')
                if parts[1] != server_info:
                    f.write(line)

    elif action == "PING":
        print(f"Ping from {client_ip}:{server_port}")
        # Read existing server entries from the file
        existing_servers = {}
        with open(SERVERS_FILE, 'r') as f:
            lines = f.readlines()
            for line in lines:
                parts = line.strip().split(';')
                ip_port = parts[1]
                timestamp = int(parts[0])
                # Check if the timestamp is within the last 5 minutes
                if current_timestamp - timestamp <= 300:
                    existing_servers[ip_port] = timestamp

        # Check if the server is already registered or its IP is duplicate
        if server_info not in existing_servers:
            # Append server to the list of registered servers in the file
            with open(SERVERS_FILE, 'a') as f:
                f.write(f"{current_timestamp};{server_info}\n")
            print(f"Server at {client_ip}:{server_port} registered")
        else:
            # Update the timestamp for the server in the dictionary
            existing_servers[server_info] = current_timestamp

            # Write updated entries back to the file
            with open(SERVERS_FILE, 'w') as f:
                for ip_port, timestamp in existing_servers.items():
                    f.write(f"{timestamp};{ip_port}\n")

    else:
        print("Unknown action received")


def main():
    central_registry_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    central_registry_socket.bind((CENTRAL_REGISTRY_HOST, CENTRAL_REGISTRY_PORT))
    central_registry_socket.listen(5)
    print("Central registry server is listening...")

    while True:
        client_socket, address = central_registry_socket.accept()
        print(f"Connection from {address}")

        data = client_socket.recv(1024).decode().strip()
        if data:
            handle_registration(client_socket, address, data)
        client_socket.close()

if __name__ == "__main__":
    main()
