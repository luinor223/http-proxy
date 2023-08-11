import socket
import sys
import threading
import time as pytime
from configparser import ConfigParser
from datetime import datetime, time 
    
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
    
def handle_chunked_response(proxy_client_sock):
    response = b""
    while True:
        chunk_size_line = b""
        while b"\r\n" not in chunk_size_line:
            chunk_size_line += proxy_client_sock.recv(1)
        
        response += chunk_size_line
        chunk_size = int(chunk_size_line.decode().strip("\r\n"), 16) + 2
        
        chunk_data = b""
        remaining_length = chunk_size
        while remaining_length > 0:
            chunk_data += proxy_client_sock.recv(min(chunk_size, 4096))
            remaining_length -= min(chunk_size, 4096)
        
        response += chunk_data
        
        if chunk_size == 2:
            # Last chunk, end of response
            break

    return response

def handle_response(sock):
    # Read and process headers
    headers = b""
    while True:
        headers += sock.recv(1)
        if b"\r\n\r\n" in headers:
            break
    
    # Check for Transfer-Encoding: chunked
    response_data = headers
    print(response_data.decode())
    if b"Transfer-Encoding: chunked" in headers:
        response_data += handle_chunked_response(sock)
        return response_data
    
    # Process regular response with Content-Length
    content_length = 0
    for line in headers.split(b"\r\n"):
        if line.startswith(b"Content-Length:"):
            content_length = int(line.split(b":")[1].strip())
            break
    
    remaining_length = content_length
    while remaining_length > 0:
        chunk_size = min(remaining_length, 4096)
        response_data += sock.recv(chunk_size)
        remaining_length -= chunk_size

    return response_data


def handle_client(client_socket, client_address):
    #Receive request from Client
    request = client_socket.recv(4096).decode()
    method, url, webserver, port = process_request(request)
    
    #Check method
    if method not in ["GET", "POST", "HEAD"]:
        send_403_response(client_socket)
        return
    
    print(f"[NEW] Request from {client_address} : {method} {url}")
    
    #Request to webserver
    ProxyClientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        ProxyClientSock.connect((webserver, port))
    except:
        send_403_response(client_socket)
        print("Failed to connect to WebServer")
        return
    ProxyClientSock.send(request.encode())
    
    response = handle_response(ProxyClientSock)
        
    #Send response to client
    print(response)
    client_socket.send(response)
    print (f"Response sent to {client_address}\n\n")
    
    ProxyClientSock.close()
    client_socket.close()
        

def main():
    # if len(sys.argv) <= 1:
    #     print('Usage : "python ProxyServer.py server_ip"\n[server_ip : It is the IP Address Of Proxy Server')
    #     sys.exit(2)

    HOST = "127.0.0.1"
    Port = 8888

    tcpSerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcpSerSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcpSerSock.bind((HOST, Port))
    tcpSerSock.listen(5)
    print(f'Server running on {HOST}:{Port}')

    while True:
        tcpCliSock, addr = tcpSerSock.accept()
        thread = threading.Thread(target=handle_client, args=(tcpCliSock, addr))
        thread.start()
    
if __name__ == "__main__":
    main()
    
    