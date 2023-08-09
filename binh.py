from socket import *
import threading
import os
import time
import sys

CACHE_TIMEOUT = 15 * 60  # 15 minutes
CACHE_FOLDER = "cache"
os.makedirs(CACHE_FOLDER, exist_ok=True)

WHITELIST = ["example.com"]
ALLOWED_HOURS = (8, 20)

def is_allowed():
    current_hour = time.localtime().tm_hour
    return ALLOWED_HOURS[0] <= current_hour < ALLOWED_HOURS[1]

def is_whitelisted(hostname):
    return any(hostname.endswith(domain) for domain in WHITELIST)

def is_cache_valid(cache_file):
    return time.time() - os.path.getmtime(cache_file) <= CACHE_TIMEOUT

def serve_cached_response(client_socket, cache_file):
    with open(cache_file, "rb") as f:
        response = f.read()
        client_socket.sendall(response)

def fetch_and_cache(client_socket, cache_file, target_host, target_port, request):
    with socket(AF_INET, SOCK_STREAM) as server_socket:
        server_socket.connect((target_host, target_port))
        server_socket.sendall(request)
        response = server_socket.recv(4096)
        
        with open(cache_file, "wb") as f:
            f.write(response)
        
        client_socket.sendall(response)

def handle_client(client_socket, client_address):
    request = client_socket.recv(4096).decode("utf-8")
    request_lines = request.split("\n")
    first_line = request_lines[0].split(" ")
    method = first_line[0]
    url = first_line[1]
    filename = url.partition("/")[2]
    target_host = url.split("/")[2]
    target_port = 80

    if is_allowed():
        if is_whitelisted(target_host):
            cache_file = os.path.join(CACHE_FOLDER, filename.replace("/", "_"))
            
            if os.path.exists(cache_file) and is_cache_valid(cache_file):
                serve_cached_response(client_socket, cache_file)
            else:
                fetch_and_cache(client_socket, cache_file, target_host, target_port, request.encode("utf-8"))
        else:
            response = "HTTP/1.0 403 Forbidden\r\n\r\nAccess Denied: Not Whitelisted".encode("utf-8")
            client_socket.sendall(response)
    else:
        response = "HTTP/1.0 403 Forbidden\r\n\r\nAccess Denied: Outside Allowed Hours".encode("utf-8")
        client_socket.sendall(response)
    
    client_socket.close()

#Code anh Bình
def main():
    if len(sys.argv) <= 1:
        print('Usage: "python ProxyServer.py server_ip"\n[server_ip: IP Address of Proxy Server]')
        sys.exit(2)

    HOST = sys.argv[1]
    PORT = 8888

    tcpSerSock = socket(AF_INET, SOCK_STREAM)
    tcpSerSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    tcpSerSock.bind((HOST, PORT))
    tcpSerSock.listen(5)
    print(f'Server running on {HOST}:{PORT}')

    while True:
        client_socket, client_address = tcpSerSock.accept()
        print('Accepted connection from:', client_address)
        
        client_handler = threading.Thread(target=handle_client, args=(client_socket, client_address))
        client_handler.start()

if __name__ == "__main__":
    main()
