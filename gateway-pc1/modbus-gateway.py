import time
import struct
import logging
import socket
import threading
import json
from pymodbus.client import ModbusTcpClient
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- Configurations ---
PLC_IP = "192.168.1.10"
PLC_PORT = 5502
WIFI_BIND_IP = "0.0.0.0"  # Listens on all interfaces, including 10.234.210.238
TCP_PORT = 5050

# Global state for thread sharing
latest_payload = {}
payload_lock = threading.Lock()

# --- Modbus Parsing Functions ---
def parse_float(reg_low, reg_high):
    try:
        return struct.unpack('<f', struct.pack('<HH', reg_low, reg_high))[0]
    except Exception:
        return 0.0

def parse_string(registers):
    text = ""
    for reg in registers:
        for byte_val in [(reg >> 8) & 0xFF, reg & 0xFF]:
            if byte_val == 0: continue
            if 32 <= byte_val <= 126: text += chr(byte_val)
    return text.strip()

def parse_timestamp(reg_low, reg_high):
    """Reconstructs the 32-bit Unix timestamp and converts to a SQL-friendly string."""
    try:
        # Rebuild the 32-bit integer
        timestamp_seconds = (reg_high << 16) | reg_low
        
        # If the PLC clock is not set and returns 0, handle it gracefully
        if timestamp_seconds == 0:
            return "1970-01-01 00:00:00"
            
        # Convert to human-readable string
        return datetime.fromtimestamp(timestamp_seconds).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logging.error(f"Timestamp parsing error: {e}")
        return "ERROR"


# --- TCP Server Thread ---
def tcp_server_worker():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((WIFI_BIND_IP, TCP_PORT))
    server_socket.listen(1)
    logging.info(f"TCP Server listening on port {TCP_PORT}...")

    while True:
        client_conn, client_addr = server_socket.accept()
        logging.info(f"PC2 Connected from {client_addr}")
        client_conn.settimeout(5.0)

        try:
            while True:
                with payload_lock:
                    if latest_payload:
                        # Serialize to JSON and send with a newline delimiter
                        data_string = json.dumps(latest_payload) + "\n"
                        client_conn.sendall(data_string.encode('utf-8'))
                time.sleep(1)  # Match the 1Hz Modbus poll rate
        except (socket.error, socket.timeout) as e:
            logging.warning(f"Client disconnected: {e}")
        finally:
            client_conn.close()

# --- Main Modbus Loop ---
def main():
    global latest_payload
    
    # Start the TCP Server in the background
    threading.Thread(target=tcp_server_worker, daemon=True).start()
    
    client = ModbusTcpClient(PLC_IP, port=PLC_PORT)
    
    while True:
        if not client.is_socket_open():
            if not client.connect():
                time.sleep(5)
                continue

        try:
            result = client.read_holding_registers(address=0, count=30)
            if not result.isError():
                regs = result.registers
                with payload_lock:
                    latest_payload = {
                        "plc_time":    parse_timestamp(regs[19], regs[20]),
                        "valor":       regs[0],
                        "counter":     regs[1],
                        "boolean":     bool(regs[2]),
                        "temperature": round(parse_float(regs[3], regs[4]), 2),
                        "pressure":    round(parse_float(regs[5], regs[6]), 2),
                        "velocity":    round(parse_float(regs[7], regs[8]), 3),
                        "string_msg":  parse_string(regs[9:19])
                    }
                
                # Print nicely formatted payload to the console
                print("\n--- Current PLC Payload ---")
                print(json.dumps(latest_payload, indent=4))
                
                # Keep the standard log entry for the file
                logging.info(f"Modbus Read OK. Counter: {latest_payload['counter']}")
            else:
                logging.warning("Modbus read error.")
        except Exception as e:
            logging.error(f"Modbus exception: {e}")
            client.close()
            
        time.sleep(1)

if __name__ == "__main__":
    main()
