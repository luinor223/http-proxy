import socket
import sys
import threading
import time as pytime
from configparser import ConfigParser
from datetime import datetime, time 

def read_config_file(filename):
    config = ConfigParser()
    config.read(filename)

    # Get values from the "default" section
    cache_time = config.getint('default', 'cache_time')
    whitelisting = config.get('default', 'whitelisting')
    time = config.get('default', 'time')
    timeout = int(config.get('default', 'timeout'))
    enabling_whitelist = config.getboolean('default', 'enabling_whitelist')
    time_restriction = config.getboolean('default', 'time_restriction')
    max_recieve = config.getint('default', 'max_recieve')

    # Process the whitelisting string into a list
    whitelist = [item.strip() for item in whitelisting.split(',')]
    timelist = [timeline.strip() for timeline in time.split('-')]

    return cache_time, whitelist, timelist, timeout, enabling_whitelist, time_restriction, max_recieve

cache = {}
file_path = 'config.ini'
cache_time, whitelist, timelist, timeout, enabling_whitelist, time_restriction, max_recieve = read_config_file(file_path)

def process_request(request):
    first_line = request.split("\r\n")[0]
    method = first_line.split(" ")[0]
    url = first_line.split(" ")[1]
    http_pos = url.find("://") # find pos of ://
    if (http_pos==-1):
        temp = url
    else:
        temp = url[(http_pos+3):] # get the rest of url

    port_pos = temp.find(":") # find the port pos (if any)

    # find end of web server
    webserver_pos = temp.find("/")
    if webserver_pos == -1:
        webserver_pos = len(temp)

    webserver = ""
    port = -1
    if (port_pos==-1 or webserver_pos < port_pos): 
        # default port 
        port = 80 
        webserver = temp[:webserver_pos] 

    else: # specific port 
        port = int((temp[(port_pos+1):])[:webserver_pos-port_pos-1])
        webserver = temp[:port_pos]
    
    return method, url, webserver, port

def send_403_response(client_socket):
    header = "HTTP/1.1 403 Forbidden\r\n"
    header += "Content-Type: text/html\r\n\r\n"
    with open("403.html", 'r') as file:
        content = file.read()
    client_socket.send(header.encode() + content.encode())
    return

def is_in_whitelist(url):
    for link in whitelist:
        if url in link:
            return True
    return False

def time_check(time):
    start = timelist[0]
    end = timelist[1]
    if start <= time <= end:
        return True
    return False    

def proxy_create(client_socket, webserver, port, ProxyClientSock): 
    if enabling_whitelist:
        if not is_in_whitelist(webserver):
            send_403_response(client_socket)
            client_socket.close()
            return
    try:
        ProxyClientSock.connect((webserver, port))
        ProxyClientSock.send(request.encode())
        while 1:
            #Receive response from webserver
            message = ProxyClientSock.recv(max_recieve)
            #Send response to client
            client_socket.send(message)
            if len(message) <= 0:
                break
        client_socket.close()
        ProxyClientSock.close()
    except:
        send_403_response(client_socket)
        print("Connection timed out. Unable to connect to the server.")
        ProxyClientSock.close()
        client_socket.close()
        return

def handle_client(client_socket, client_address):
    #Receive request from Client
    request = client_socket.recv(max_recieve).decode()
    method, url, webserver, port = process_request(request)
    
    #Check method
    if method not in ["GET", "POST", "HEAD"]:
        send_403_response(client_socket)
        return
    
    #Request to webserver
    print(f"Request from {client_address} : {method} {url}")
    ProxyClientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_create(client_socket, webserver, port, ProxyClientSock)
    
    client_socket.close()
        

def main():
    if len(sys.argv) <= 1:
        print('Usage : "python ProxyServer.py server_ip"\n[server_ip : It is the IP Address Of Proxy Server')
        sys.exit(2)

    HOST = sys.argv[1]
    Port = 8888

    tcpSerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcpSerSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcpSerSock.settimeout(timeout)
    tcpSerSock.bind((HOST, Port))
    tcpSerSock.listen(5)
    print(f'Server running on {HOST}:{Port}')

    while True:
        tcpCliSock, addr = tcpSerSock.accept()
        thread = threading.Thread(target=handle_client, args=(tcpCliSock, addr))
        thread.start()
    
if __name__ == "__main__":
    main()
    
    