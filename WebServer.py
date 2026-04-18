# Implements a simple HTTP Server 
import socket, threading, os, time, sys, signal
from email.utils import formatdate, parsedate_to_datetime

# Define socket host, port, document root, and generated log file
SERVER_HOST = '127.0.0.1' 
SERVER_PORT = 8080 
DOCUMENT_ROOT = './htdocs'
LOG_FILE = os.path.join(os.path.dirname(__file__), 'server.log')

# File extension mapping
MIME_TYPES = {
    '.html': 'text/html',
    '.htm':  'text/html',
    '.txt':  'text/plain',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png':  'image/png',
    '.gif':  'image/gif',
    '.css':  'text/css',
    '.js':   'application/javascript',
}

# Logging
log_lock = threading.Lock()
def log_request(client_ip, request_file, status_code):
    """Write a log entry for each request."""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    with log_lock:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{client_ip} - - [{timestamp}] \"{request_file}\" {status_code}\n")
    print(f"[LOG] {client_ip} - {request_file} - {status_code}")

# Create an HTTP response message header lines
def response_headers(status_code, last_modified=None, content_type=None,
                     content_length=None, connection='close', etag=None):
    """
    Generate HTTP response headers.
    Parameters:
        status_code: HTTP status code
        last_modified: Last-Modified value
        content_type: Content-Type value
        content_length: Content-Length value
        connection: Connection value (keep-alive or close)
        etag: ETag value
    Returns: String containing HTTP headers.
    """
    status_text = {
        200: 'OK', 304: 'Not Modified', 400: 'Bad Request',
        403: 'Forbidden', 404: 'Not Found',
    }.get(status_code, 'Internal Server Error')

    headers = f"HTTP/1.1 {status_code} {status_text}\r\n"
    headers += f"Date: {formatdate(time.time(), usegmt=True)}\r\n"
    headers += f"Server: WebServer/1.0\r\n"

    if last_modified:
        headers += f"Last-Modified: {last_modified}\r\n"
    if etag:
        headers += f"ETag: {etag}\r\n"

    if status_code == 200:
        headers += f"Accept-Ranges: bytes\r\n"

    if content_type:
        headers += f"Content-Type: {content_type}\r\n"
    if content_length is not None:
        headers += f"Content-Length: {content_length}\r\n"

    headers += f"Connection: {connection}\r\n"
    if connection.lower() == 'keep-alive':
        headers += f"Keep-Alive: timeout=5, max=100\r\n"

    headers += "\r\n"
    return headers

def send_error_response(client_sock, status_code, connection='close'):
    """Send an error response."""
    status_text = {400:'Bad Request', 403:'Forbidden', 404:'Not Found'}.get(status_code, 'Error')
    body = f"<html><body><h1>{status_code} {status_text}</h1></body></html>"
    headers = f"HTTP/1.1 {status_code} {status_text}\r\n"
    headers += f"Content-Type: text/html\r\n"
    headers += f"Content-Length: {len(body)}\r\n"
    headers += f"Connection: {connection}\r\n\r\n"
    client_sock.send(headers.encode() + body.encode())

# Handle the HTTP request
def handle_client(client_sock, client_addr):
    print(f"[THREAD] Handling {client_addr} in thread {threading.current_thread().name}")
    client_ip = client_addr[0]
    try:
        while True:
            request_data = b''
            while b'\r\n\r\n' not in request_data:
                chunk = client_sock.recv(1024)
                if not chunk:
                    break
                request_data += chunk
            if not request_data:
                break

            # Decode bytes to string
            request_text = request_data.decode('utf-8', errors='ignore')
            lines = request_text.split('\r\n')
            if not lines:
                break

            # Parse the request line
            request_line = lines[0]
            fields = request_line.split()
            if len(fields) != 3:
                send_error_response(client_sock, 400)   # Send 400 Bad Request
                log_request(client_ip, request_line, 400)
                break

            request_type, filename, version = fields
            # Only GET and HEAD are supported
            if request_type in ('GET', 'HEAD'):
                # Parse headers
                headers = {}
                for line in lines[1:]:
                    if ': ' in line:
                        key, value = line.split(': ', 1)
                        headers[key.lower()] = value

                # Decide persistent connection
                conn_header = headers.get('connection', '').lower()
                keep_alive = (conn_header == 'keep-alive')            # True if keep-alive requested

                # Prevent directory traversal attacks
                print(f"[DEBUG] filename before security: {filename}") 
                if '?' in filename:
                    filename = filename.split('?')[0]
                if '..' in filename or filename.startswith('/../') or filename == '..':
                    send_error_response(client_sock, 403, 'keep-alive' if keep_alive else 'close')
                    log_request(client_ip, filename, 403)
                    if not keep_alive:
                        break
                    continue   # If keep-alive, continue to next request

                # Default to index.html if root is requested
                if filename == '/' or filename == '':
                    filename = '/index.html'
                # Build full filesystem path
                file_path = DOCUMENT_ROOT + filename

                # Check and retrieve metadata
                try:
                    stat = os.stat(file_path)
                    if not os.path.isfile(file_path):
                        raise FileNotFoundError
                except FileNotFoundError:                # File not found -> 404
                    send_error_response(client_sock, 404, 'keep-alive' if keep_alive else 'close')
                    log_request(client_ip, filename, 404)
                    if not keep_alive:
                        break
                    continue
                except PermissionError:                  # Permission denied -> 403
                    send_error_response(client_sock, 403, 'keep-alive' if keep_alive else 'close')
                    log_request(client_ip, filename, 403)
                    if not keep_alive:
                        break
                    continue

                # Generate Last-Modified, ETag, and Content-Length
                ext = os.path.splitext(file_path)[1].lower()
                last_modified = formatdate(stat.st_mtime, usegmt=True)
                content_type = MIME_TYPES.get(ext, 'application/octet-stream')
                content_length = stat.st_size
                etag = f'"{hex(int(stat.st_mtime))[2:]}-{hex(content_length)[2:]}"'

                # Handle If-Modified-Since conditional request
                if_modified = headers.get('if-modified-since')
                if if_modified:
                    try:
                        client_time = parsedate_to_datetime(if_modified).timestamp()
                        print(f"[DEBUG] client_time: {client_time}, stat.st_mtime: {int (stat.st_mtime)}")
                        if int(stat.st_mtime) <= client_time:
                            resp_headers = f"HTTP/1.1 304 Not Modified\r\n"
                            resp_headers += f"Date: {formatdate(time.time(), usegmt=True)}\r\n"
                            resp_headers += f"Connection: {'keep-alive' if keep_alive else 'close'}\r\n"
                            if keep_alive:
                                resp_headers += f"Keep-Alive: timeout=5, max=100\r\n"
                            resp_headers += "\r\n"
                            client_sock.send(resp_headers.encode())
                            log_request(client_ip, filename, 304)
                            if not keep_alive:
                                break
                            continue
                        else:
                            print("[DEBUG] file modified, sending 200")
                    except Exception as e:
                            print(f"[DEBUG] Failed to parse If-Modified-Since: {e}")

                # Build 200 OK response headers
                resp_headers = response_headers(
                    status_code=200,
                    last_modified=last_modified,
                    etag=etag,
                    content_type=content_type,
                    content_length=content_length,
                    connection='keep-alive' if keep_alive else 'close'
                )
                client_sock.send(resp_headers.encode())

                # GET request_type sends file content in binary chunks
                if request_type == 'GET':
                    with open(file_path, 'rb') as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            client_sock.send(chunk)

                log_request(client_ip, filename, 200)

                # Decide to close the connection
                if not keep_alive:
                    break   # Non-persistent connection -> exit loop and close socket
            else:
                send_error_response(client_sock, 400)   # Unsupported request_type -> 400
                log_request(client_ip, filename, 400)
                break
     
    except Exception as e:
        print(f"Error handling client {client_addr}: {e}")
    finally:
        client_sock.close()

server_running = True
def signal_handler(sig, frame):
    global server_running
    print("\nInterrupt received, shutting down server...")
    server_running = False

# Multi-threaded main server
def start_server():
    """Start the server, listen on port, and spawn a new thread for each client."""
    global server_running
    signal.signal(signal.SIGINT, signal_handler)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(5)
    server_socket.settimeout(1.0)
    print(f"Server started at http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"Document root: {os.path.abspath(DOCUMENT_ROOT)}")
    print("Press Ctrl+C to stop")

    try:
        while server_running:
            try:
                client_sock, client_addr = server_socket.accept()
                print(f"New connection from {client_addr}")
                client_thread = threading.Thread(target=handle_client, args=(client_sock, client_addr))
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                continue
            except OSError:
                break
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt caught, shutting down...")
    finally:
        server_running = False
        server_socket.close()
        print("Server socket closed. Goodbye.")

# Entry Point
if __name__ == '__main__':
    # Create document root if not exists
    if not os.path.exists(DOCUMENT_ROOT):
        os.makedirs(DOCUMENT_ROOT)
        with open(os.path.join(DOCUMENT_ROOT, 'index.html'), 'w', encoding='utf-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<head><title>My Web Server</title></head>
<body>
<h1>It works!</h1>
<p>This page is served by your custom multi-threaded web server with ETag and Keep-Alive.</p>
<p><a href="test.html">Test HTML</a></p>
</body>
</html>""")
        # Create a test HTML file
        with open(os.path.join(DOCUMENT_ROOT, 'test.html'), 'w', encoding='utf-8') as f:
            f.write("""<!DOCTYPE html>
<html><body><h2>Test Page</h2><p>This is another page.</p></body></html>""")
        print(f"Sample files created in {DOCUMENT_ROOT}: index.html and test.html")
    start_server()