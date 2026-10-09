import time
import struct
import logging
import socket
import threading
import json
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("edge_gateway.log"),
        logging.StreamHandler()
    ]
)

# --- Configurations ---
PLC_IP = "192.168.1.10"
PLC_PORT = 5502
REG_START = 0
REG_COUNT = 30 
WIFI_BIND_IP = "0.0.0.0"  # Listens on all interfaces
TCP_PORT = 5050

# Global state for thread sharing
latest_payload = {}
payload_lock = threading.Lock()

# --- Modbus Parsing Functions ---
def parse_float(reg_low, reg_high):
    try:
        data = struct.pack('<HH', reg_low, reg_high)
        return struct.unpack('<f', data)[0]
    except Exception as e:
        logging.error(f"Float parsing exception: {e}")
        return 0.0

def parse_string(registers):
    text = ""
    for reg in registers:
        high_byte = (reg >> 8) & 0xFF
        low_byte = reg & 0xFF
        for byte_val in [high_byte, low_byte]:
            if byte_val == 0:
                continue
            if 32 <= byte_val <= 126:
                text += chr(byte_val)
    return text.strip()

# --- Background TCP Server Thread ---
def tcp_server_worker():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((WIFI_BIND_IP, TCP_PORT))
    server_socket.listen(1)
    logging.info(f"TCP Server listening for PC2 on port {TCP_PORT}...")

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
            logging.info("Connecting to Bosch Rexroth PLC...")
            if not client.connect():
                logging.error("PLC connection failed. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            logging.info("Connected successfully.")

        try:
            result = client.read_holding_registers(address=REG_START, count=REG_COUNT)
            
            if result.isError():
                logging.warning(f"Modbus error response: {result}")
                time.sleep(2)
                continue

            regs = result.registers

            # Safely update the global dictionary that the TCP thread reads
            with payload_lock:
                latest_payload = {
                    "valor":       regs[0],                
                    "counter":     regs[1],                
                    "boolean":     bool(regs[2]),          
                    "temperature": round(parse_float(regs[3], regs[4]), 2),  
                    "pressure":    round(parse_float(regs[5], regs[6]), 2),  
                    "velocity":    round(parse_float(regs[7], regs[8]), 3),  
                    "string_msg":  parse_string(regs[9:19]) 
                }

            # Print nicely formatted payload to the PC1 console
            print("\n--- Current PLC Payload ---")
            print(json.dumps(latest_payload, indent=4))

            logging.info(f"Modbus Read OK. Counter: {latest_payload['counter']}")
        except (ModbusException, Exception) as err:
            logging.error(f"Runtime communication error: {err}")
            client.close()
            time.sleep(2)

        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Edge gateway script terminated by user.")
