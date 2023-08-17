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

# def save_cache(webserver, response, client_socket):
    # print("checking image for cache")
    # web_server_folder = os.path.join(cache_directory, webserver)
    # print("web server folder: ", web_server_folder)

    # img_src_pattern = re.compile(r'<img[^>]+src="([^"]+)"', re.IGNORECASE)
    # matches = img_src_pattern.findall(response)

    # for img_src in matches:
    #     print(img_src)
    # if not os.path.exists(web_server_folder):
    #     os.makedirs(web_server_folder)
    #  #img src=
    # content_type_header = re.search(r'Content-Type: (.+?)\r\n', response.decode('utf-8'))
    # print("content_type_header: ", content_type_header)
    # if content_type_header:
    #     content_type = content_type_header.group(1)
    #     print("content_type: ", content_type)
    #     # Use regular expression to check if the content type is an image
    #     image_content_types = re.compile(r'image/(jpeg|png|gif)')
    #     is_image = image_content_types.match(content_type)

    #     if is_image:
    #         print("This is an image")
    # # Extract the image file name from the URL (you might need more sophisticated logic)
    #         image_url_pattern = r'<img [^>]*src=["\'](https?://[^"\']+\.jpg|https?://[^"\']+\.png|https?://[^"\']+\.gif)["\']'
    #         image_urls = re.findall(image_url_pattern, response)
    #         image_filename = image_urls[-1]

    #     # Full path to save the image
    #         image_path = os.path.join(web_server_folder, image_filename)

    #     # Save the image content to the specified path
    #         with open(image_path, 'wb') as image_file:
    #             image_file.write(response.content)

def proxy_image_response(client_socket, response_content):
    headers = b"HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\n\r\n"
    
    client_socket.send(headers + response_content)
    client_socket.close()

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

def clear_cache_periodically():
    while True:
        pytime.sleep(cache_time)  # Sleep for <cache_time> seconds     
        cache.clear()
        print("Cache cleaned!")
        
def is_cache_valid(url):
    if url in cache:
        print("response for ", url, "already in the cache.\n")    
        return True
    return False

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
    
    print(content_length)
    remaining_length = content_length
    while remaining_length > 0:
        chunk_size = min(remaining_length, 4096)
        msg = proxy_client_socket.recv(chunk_size)
        response += msg
        
        remaining_length -= len(msg)
        
    print("Adding response from request: ", url, "to cache\n")

    cache[url]={
        "cache": response,
        "last_update_time": pytime.time()
    }

    return response

def get_image_data(response):
    # Parse the response to extract image data
    image_start = response.find(b'\r\n\r\n') + 4
    image_data = response[image_start:]
    return image_data

def store_image_in_cache(url, image_data, webserver):
    # web_server_folder = os.path.join(cache_directory, webserver)
    # print("web server folder: ", web_server_folder)
    # if not os.path.exists(web_server_folder):
    #     os.makedirs(web_server_folder)

    # Create a directory for the cache if it doesn't exist
    if not os.path.exists(cache_directory):
        os.makedirs(cache_directory)
    
    # Create a filename based on the URL
    filename = url.replace("/", "").replace(":", "")
    
    # Save the image data to the cache directory
    image_path = os.path.join(cache_directory, filename)
    with open(image_path, 'wb') as f:
        f.write(image_data)

def is_in_cache(url):
    return os.path.exists(os.path.join(cache_directory, url.replace("/", "").replace(":", "")))

def get_cached_response(url):
    image_path = os.path.join(cache_directory, url.replace("/", "").replace(":", ""))
    with open(image_path, 'rb') as f:
        return f.read()

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
            send_403_response(client_socket)
            client_socket.close()
            return
    if is_cache_valid(url):
        print(f"[*] SENDING CACHED RESPONSE FOR: {url}\n")
        client_socket.send(cache[url]["cache"])
        client_socket.close()
        return 
    if time_restriction:
        if time_check(datetime.now().time()) == False:
            print("not in allowed time!")
            send_403_response(client_socket)
            return
    #Request to webserver (create a socket as client)
    print(f"[NEW] Request from {client_address} : {method} {url}")
    print("REQUEST: ", request)
    
    print("------------------------------------------")
    webserver_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    webserver_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sendmsg = f"{method} {url} HTTP/1.1\r\n" + f"Host: {webserver}\r\n" + f"Connection: Keep-Alive\r\n\r\n"
    print(sendmsg.encode())
    
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
    print("NEXT IS A RESPONSE TO CLIENT: \n")
    print(response)
    client_socket.send(response)
    print (f"Response sent to {client_address}\n\n")
    
    #save_cache(webserver, response, client_socket)
    # if "content-type: image" in response.lower():  # Adjust based on actual content type
    #     print("There is an image")
    #     proxy_image_response(client_socket, response)
    response_headers = response.split(b'\r\n\r\n')[0]
    # Check if the response is an image
    if b"Content-Type: image/" in response_headers:
        image_data = get_image_data(response)
        if image_data:
            store_image_in_cache(url, image_data)
    webserver_socket.close()
    client_socket.close()
        

def main():
    # if len(sys.argv) <= 1:
    #     print('Usage : "python ProxyServer.py server_ip"\n[server_ip : It is the IP Address Of Proxy Server')
    #     sys.exit(2)

    HOST = "127.0.0.1"
    # HOST = sys.argv[1]
    Port = 8888

    tcpSerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcpSerSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcpSerSock.settimeout(timeout)
    tcpSerSock.bind((HOST, Port))
    tcpSerSock.listen(5)
    print(f'Server running on {HOST}:{Port}')

    clear_cache_thread = threading.Thread(target=clear_cache_periodically)
    clear_cache_thread.start()

    while True:
        tcpCliSock, addr = tcpSerSock.accept()
        thread = threading.Thread(target=handle_client, args=(tcpCliSock, addr))
        thread.start()
    
if __name__ == "__main__":
    main()
    
    