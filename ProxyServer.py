import socket
import sys
import threading
import time as pytime
import configparser
from datetime import datetime, time 

def send_response(client_socket, status_code, content_type, content):
    header = f"HTTP/1.1 {status_code}\r\n"
    header += f"Content-Length: {len(content)}\r\n"
    header += f"Content-Type: {content_type}\r\n\r\n"
    response = header.encode("utf8") + content.encode("utf8")
    client_socket.send(response)
    
def GET(client_socket, rq_url):
    if rq_url == "":
        url = "index.html"
        content_type = "text/html"
    if rq_url = "favicon.ico"
    
    

def handle_client(client_socket, client_address):
    request = client_socket.recv(4096).decode("utf-8")
    first_line = request.split("\r\n")[0]
    method = first_line.split(" ")[0]
    url = first_line.split(" ")[1]
    url = url.strip("/")
    
    print(f"Request from {client_address} : {method} {url}")
    #client_socket.sendall(b"HTTP/1.1 200 OK\r\n")
    
    #if method == "GET":
        #GET(client_socket, url)
        

def main():
    if len(sys.argv) <= 1:
        print('Usage : "python ProxyServer.py server_ip"\n[server_ip : It is the IP Address Of Proxy Server')
        sys.exit(2)

    HOST = sys.argv[1]
    Port = 8888

    tcpSerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcpSerSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcpSerSock.settimeout(30)
    tcpSerSock.bind((HOST, Port))
    tcpSerSock.listen(5)
    print(f'Server running on {HOST}:{Port}')

    while True:
        tcpCliSock, addr = tcpSerSock.accept()
        handle_client(tcpCliSock, addr)
    
if __name__ == "__main__":
    main()
    
    