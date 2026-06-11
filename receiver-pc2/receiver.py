import socket
import json
import time

SERVER_IP = "10.234.210.247"
PORT = 5050

print("--- PC2 Client Script Started ---")

while True:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print(f"Attempting connection to {SERVER_IP}:{PORT}...")
            
            # 1. Enforce a connection timeout
            s.settimeout(5.0)
            s.connect((SERVER_IP, PORT))
            
            # 2. Enforce a read timeout for the blocking recv() call
            s.settimeout(5.0) 
            print("Connected! Listening for Modbus payload stream...\n")
            
            buffer = ""
            
            while True:
                # If no data arrives in 5 seconds, this throws a socket.timeout exception
                data = s.recv(1024).decode('utf-8')
                
                if not data:
                    print("Connection dropped cleanly by gateway.")
                    break  
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():  # Ignore empty lines
                        payload = json.loads(line)
                        
                        # Print the complete telemetry dictionary
                        print("\n--- Received Payload ---")
                        print(json.dumps(payload, indent=4))
                        
    except ConnectionRefusedError:
        print(f"Connection refused by {SERVER_IP}. Retrying...")
        time.sleep(3)
    except socket.timeout:
        # 3. Catch the deadlock, break the context manager (which closes the socket), and loop
        print("Socket read timeout (Dead Peer). Forcing reconnection...")
        time.sleep(1)
    except Exception as e:
        print(f"Network error: {e}. Reconnecting in 3 seconds...")
        time.sleep(3)