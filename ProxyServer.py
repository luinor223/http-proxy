import socket
import sys
import threading
import time as pytime
from configparser import ConfigParser
from datetime import datetime, time 
from pathlib import Path
import os
import re

cache_directory  = 'Cache'
supported_image = [".png", ".jpg", ".ico", ".gif", ".jpeg", ".jfif"]

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

file_path = 'config.ini'
cache_time, whitelist, timelist, timeout, enabling_whitelist, time_restriction, max_recieve = read_config_file(file_path)
cache = {}
       
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

def time_check(time1):
    current_time = time(time1.hour, time1.minute, 0)
    start = datetime.strptime(timelist[0], '%H:%M').time()
    end = datetime.strptime(timelist[1], '%H:%M').time()
    
    print(start, current_time, end)
    if start <= current_time <= end:
        return True
    return False    

def handle_chunked_response(webserver_socket):
    response = b""
    while True:
        chunk_size_line = b""
        while b"\r\n" not in chunk_size_line:
            chunk_size_line += webserver_socket.recv(1)
        
        response += chunk_size_line
        chunk_size = int(chunk_size_line.strip(b'\r\n'), 16) + 2
        
        chunk_data = b""
        remaining_length = chunk_size
        while remaining_length > 0:
            msg = webserver_socket.recv(min(remaining_length, max_recieve))
            chunk_data += msg
            remaining_length -= len(msg)
        
        response += chunk_data
        
        if chunk_size == 2:
            # Last chunk, end of response
            break

    return response

def get_response_from_webserver(proxy_client_socket, client_socket , url, method):
    # Read and process headers
    headers = b""
    while True:
        while b"\r\n\r\n" not in headers:
            headers += proxy_client_socket.recv(1)
            
        if (b"100 Continue" not in headers):
                break
            
        client_socket.send(headers)
        headers = b""
    
    # Check for Transfer-Encoding: chunked
    response = headers
    #print(response.decode())
    if method == "HEAD":
        return response
    
    #print(response.decode())
    if b"transfer-encoding: chunked" in headers.lower():
        response += handle_chunked_response(proxy_client_socket)
        return response

    # Process regular response with Content-Length
    content_length = 0
    for line in headers.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            content_length = int(line.split(b":")[1].strip())
            break
    
    #print(content_length)
    remaining_length = content_length
    while remaining_length > 0:
        chunk_size = min(remaining_length, 4096)
        msg = proxy_client_socket.recv(chunk_size)
        response += msg
        
        remaining_length -= len(msg)

    return response

def get_image_data(response):
    # Parse the response to extract image data
    image_start = response.find(b'\r\n\r\n') + 4
    image_data = response[image_start:]
    return image_data

def store_image_in_cache(url, image_data, webserver):
    web_server_folder = os.path.join(cache_directory, webserver)
    #print("web server folder: ", web_server_folder)
    if not os.path.exists(web_server_folder):
        os.makedirs(web_server_folder)

    # Create a filename based on the URL
    filename = os.path.basename(url)
    #print("Filename: ", filename)
    # Save the image data to the cache directory
    image_path = os.path.join(web_server_folder, filename)
    print("Saving [", filename, "] in: ", web_server_folder)
    with open(image_path, 'wb') as f:
        f.write(image_data)

    #modification_time = os.path.getmtime(image_path)
    #print("modification_time: ", modification_time)

def cache_check(webserver, filename):
    FilePath =  os.path.join(cache_directory, webserver, filename)
    #print("File Path: ", FilePath)
    if os.path.exists(FilePath):
        modification_time = os.path.getmtime(FilePath)
        #print("modification_time: ", modification_time)
        current_time = pytime.time()
        #print("current_time: ", current_time)
        #print("Time diff: ", current_time - modification_time)
        if current_time - modification_time < cache_time:
            return 1   #cache still valid
        else:
            return 2   #cache invalid
    else:
        return 0

def get_cached_response(url, webserver, filename):
    image_path = os.path.join(cache_directory, webserver, filename)
    header = "HTTP/1.1 200 OK\r\n"
    file_extension = filename.split('.')[-1]
    header += f"Content-Type: image/{file_extension}\r\n\r\n"
    print("HEADER: ", header)
    with open(image_path, 'rb') as f:
        return header.encode() + f.read()

def image_check(request, filename):
    if "accept: image/" in request.lower() or supported_image in filename.lower():
        print("There is an image in request")
        return True
    return False
 
def handle_client(client_socket, client_address):
    #Receive request from Client
    request = client_socket.recv(max_recieve).decode()
    if request == "":
        return
    method, url, webserver, port = process_request(request)
    
    #Check method
    if method not in ["GET", "POST", "HEAD"]:
        send_403_response(client_socket)
        return
    if enabling_whitelist:
        if not is_in_whitelist(webserver):
            print("> ", webserver, " not in whitelist")
            send_403_response(client_socket)
            client_socket.close()
            return
    if time_restriction:
        if time_check(datetime.now().time()) == False:
            print("> Request not in allowed time")
            send_403_response(client_socket)        
            client_socket.close()
            return
    #Request to webserver (create a socket as client)
    print(f"[NEW] Request from {client_address} : {method} {url}")
    #print("REQUEST: ", request)
    #print("------------------------------------------")



    has_image = False
    filename = os.path.basename(url)
    if image_check(request, filename):
        has_image = True
        status = cache_check(webserver, filename)
        if status == 1:
            print("   > Image already in Cache, sending cache response")
            cache_response = get_cached_response(url, webserver, filename)
            #print("Cache Responsed!")
            client_socket.send(cache_response)

            client_socket.close()
            return
        elif status == 2:
            print("   > Image already in Cache but invalid")
        elif status == 0:
            print("   > Image not in Cache")
        
    webserver_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    webserver_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sendmsg = f"{method} {url} HTTP/1.1\r\n" + f"Host: {webserver}\r\n" + f"Connection: Keep-Alive\r\n\r\n"
    #print("Send MSG: ", sendmsg.encode())
    
    try:
        webserver_socket.connect((webserver, port))
        webserver_socket.sendall(sendmsg.encode())
    except:
        send_403_response(client_socket)
        print("Failed to connect to WebServer")
        webserver_socket.close()
        client_socket.close()
        return
 
    
    response = get_response_from_webserver(webserver_socket, client_socket, url, method)
    response_headers = response.split(b'\r\n\r\n')[0]

    if has_image:
        print("Storing/Updating image...")
        image_data = get_image_data(response)
        store_image_in_cache(url, image_data, webserver)
    #print("NEXT IS A RESPONSE TO CLIENT: \n")
    #print(response)
    client_socket.send(response)
    print (f"Response sent to {client_address}\n\n")
    
    
    # print("response_headers: ", response_headers)

    
    webserver_socket.close()
    client_socket.close()
        

def main():
    if len(sys.argv) <= 2:
        print('Usage : "python ProxyServer.py server_ip port"\n[server_ip : It is the IP Address Of Proxy Server]\n[port: Port for Proxy Server]')
        sys.exit()

    #HOST = "127.0.0.1"
    HOST = sys.argv[1]
    Port = int(sys.argv[2])

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
    
    