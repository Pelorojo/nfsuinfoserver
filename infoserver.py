#!/usr/bin/env python3
# nfsuinfoserver TCP:10880 by Redhair
import socket
import os
import struct
import signal
import asyncio

nfsuserver_path = os.path.dirname(os.path.abspath(__file__))

CENTRAL_REGISTRY_HOST = 'nfs.onl'
CENTRAL_REGISTRY_PORT = 10881
PING_INTERVAL = 60  # Ping interval in seconds

async def ping_central_registry(server_host, server_port):
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((CENTRAL_REGISTRY_HOST, CENTRAL_REGISTRY_PORT))
                data = f"PING {server_host} {server_port}"
                s.sendall(data.encode())
        except Exception:
            pass
        
        await asyncio.sleep(PING_INTERVAL)

def deregister_from_central_registry(server_host, server_port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((CENTRAL_REGISTRY_HOST, CENTRAL_REGISTRY_PORT))
            message = f"GG {server_host} {server_port}"
            s.sendall(message.encode())
    except Exception:
        pass

track_ids = {
    1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008,
    1102, 1103, 1104, 1105, 1106, 1107, 1108, 1109,
    1201, 1202, 1206, 1210, 1207, 1214,
    1301, 1302, 1303, 1304, 1305, 1306, 1307, 1308
}

game_types = {
    "circuit": "Circ",
    "sprint": "Sprint",
    "drift": "Drift",
    "drag": "Drag",
    "all": "All"
}

def handle_request(request):
    if request == "ping":
        return "pong"

    parts = request.split(":", 1)  
    if len(parts) != 2:
        return  

    command, parameter = parts

    if command == "perf":

        output_data = handle_perf_request(parameter)
        return output_data  

    elif command == "rank":

        output_data = handle_rank_request(parameter)
        return output_data  

    else:
        return  

def handle_perf_request(parameter_track):
    track_type = int(str(parameter_track)[:2])

    if not int(parameter_track) in track_ids:
        return  

    filename = f"{nfsuserver_path}/s{parameter_track}.dat"
    if not os.path.exists(filename):
        return "Error opening file."

    field_names = ["Nick", "Result", "CarID", "Rev"]
    data_array = []

    with open(filename, 'rb') as file:
        while True:
            block = file.read(28)
            if not block:
                break

            name = block[:block.find(b'\0')].decode('utf-8')
            values = struct.unpack('iii', block[16:])
            
            if (values[0] > 0): # Skip empty scores/times
                entry = [name] + list(values)
                data_array.append(entry)

    if track_type == 13: # drift
        data_array.sort(key=lambda x: x[1], reverse=True)
    else:
        data_array.sort(key=lambda x: x[1])

    output_data = data_array[:200]

    csv_data = '~'.join(['|'.join(map(str, row)) for row in output_data])
    return csv_data

def handle_rank_request(parameter_type):
    if parameter_type not in game_types:
        return  

    filename = f"{nfsuserver_path}/stat.dat"
    if not os.path.exists(filename):
        return "Error opening file."

    field_names = [
        "Name", "Rating_All", "Wins_All", "Loses_All", "Disc_All", "REP_All", "OppsREP_All", "OppsRating_All",
        "Rating_Circ", "Wins_Circ", "Loses_Circ", "Disc_Circ", "REP_Circ", "OppsREP_Circ", "OppsRating_Circ",
        "Rating_Sprint", "Wins_Sprint", "Loses_Sprint", "Disc_Sprint", "REP_Sprint", "OppsREP_Sprint", "OppsRating_Sprint",
        "Rating_Drag", "Wins_Drag", "Loses_Drag", "Disc_Drag", "REP_Drag", "OppsREP_Drag", "OppsRating_Drag",
        "Rating_Drift", "Wins_Drift", "Loses_Drift", "Disc_Drift", "REP_Drift", "OppsREP_Drift", "OppsRating_Drift"
    ]

    data_array = []
    with open(filename, 'rb') as file:
        while True:
            block = file.read(156)
            if not block:
                break

            name = block[:block.find(b'\0')].decode('utf-8')
            values = struct.unpack('i'*35, block[16:])
            entry = dict(zip(field_names, [name] + list(values)))
            data_array.append(entry)

    sorted_array = sorted(data_array, key=lambda x: x['REP_' + game_types[parameter_type]], reverse=True)

    output_data = []
    count = 0
    for entry in sorted_array:
        total_games = entry['Wins_' + game_types[parameter_type]] + entry['Loses_' + game_types[parameter_type]]
        if total_games > 0:
            count += 1
            if count > 200:
                break
            entry_data = [
                entry['Name'], entry['Rating_' + game_types[parameter_type]], entry['Wins_' + game_types[parameter_type]],
                entry['Loses_' + game_types[parameter_type]], entry['Disc_' + game_types[parameter_type]],
                entry['REP_' + game_types[parameter_type]], entry['OppsREP_' + game_types[parameter_type]],
                entry['OppsRating_' + game_types[parameter_type]]
            ]
            output_data.append(entry_data)

    csv_data = '~'.join(['|'.join(map(str, row)) for row in output_data])
    return csv_data

async def handle_client(reader, writer):
    data = await reader.read(1024)
    request = data.decode().strip()
    addr = writer.get_extra_info('peername')
    print(f"Received request from {addr}: {request}")

    response = handle_request(request)

    if response is not None:
        writer.write(response.encode())
    else:
        # Handle the case where response is None (e.g., unrecognized request)
        error_response = "Error: Unrecognized request"
        writer.write(error_response.encode())

    await writer.drain()
    writer.close()

async def main():
    host = '0.0.0.0'
    port = 10880
    try:
        # Start pinging the central registry in the background
        ping_task = asyncio.create_task(ping_central_registry(host, port))
        
        server = await asyncio.start_server(handle_client, host, port)
        print(f"TCP server is listening on {host}:{port}")  
            
        async with server:
            await server.serve_forever()
    finally:
        # Deregister from the central registry
        deregister_from_central_registry(host, port)
        print("Deregistered from central registry")

if __name__ == "__main__":
    asyncio.run(main())
