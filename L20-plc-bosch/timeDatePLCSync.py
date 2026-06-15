import time
import logging
from pymodbus.client import ModbusTcpClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

PLC_IP = "192.168.1.10"
PLC_PORT = 5502
SYNC_REG_START = 21

def sync_time():
    client = ModbusTcpClient(PLC_IP, port=PLC_PORT)
    
    if not client.connect():
        logging.error("Could not connect to PLC to sync time.")
        return

    try:
        # 1. Get current accurate PC time as a 32-bit UNIX timestamp (seconds since epoch)
        current_unix_time = int(time.time())
        logging.info(f"Current PC Time (UNIX): {current_unix_time}")

        # 2. Split the 32-bit integer into two 16-bit WORDs
        low_word = current_unix_time & 0xFFFF
        high_word = (current_unix_time >> 16) & 0xFFFF

        # 3. Write to PLC registers 21 and 22
        # Using write_registers requires explicitly passing the list of values
        result = client.write_registers(address=SYNC_REG_START, values=[low_word, high_word])

        if result.isError():
            logging.error(f"Failed to write time to PLC: {result}")
        else:
            logging.info("Successfully pushed PC time to PLC internal clock!")

    except Exception as e:
        logging.error(f"Error during time sync: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    sync_time()
