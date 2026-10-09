# client.py

import socket

SERVER_IP = "xx.xx.xxx.xxx"
PORT = 5060

s = socket.socket()

s.connect((SERVER_IP, PORT))

s.send(b"Hello from PC2")

s.close()
