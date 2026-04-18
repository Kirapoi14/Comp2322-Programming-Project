# COMP2322 Programming Project

## Environment Configuration
- Python 3.6 or higher
- Python environment variables
- Visual Studio Code with Python extension

## How to Compile and Run
1. Put any files among MIME_TYPES you want into ./htdocs
2. Open a command prompt, a.k.a terminal in the directory.
3. Run the server:
   ```bash
   python WebServer.py
4. Website http://127.0.0.1:8080 released, copy and paste this link into the browser, and log file will record (better open the link in private mode or clean the cache).
5. Command on website is limited.
    - curl -v http://127.0.0.1:8080/file_name for GET request type
    - curl -v http://127.0.0.1:8080/file_name for HEAD request type
    - python -c "import socket; s=socket.socket(); s.connect(('127.0.0.1',8080)); s.send(b'GET /index.html\r\n\r\n'); print(s.recv(1024).decode()) returns 400 Bad Request
    - curl -v --path-as-is http://127.0.0.1:8080/../server.log returns 403 Forbidden
    - curl -v http://127.0.0.1:8080/notexist.html ruturns 404 Not Found
    - curl -I http://127.0.0.1:8080/index.html; curl -v --header "If-Modified-Since: Last-Modified value" http://127.0.0.1:8080/index.html returns  304 Not Modified
    - curl -v --header "Connection: close" http://127.0.0.1:8080/index.html for close connection
    - curl -v --keepalive --header "Connection: keep-alive" http://127.0.0.1:8080/index.html http://127.0.0.1:8080/test.html for keep-alive connection

## Log File
client_ip - - [timestamp] "requested_file" status_code

## Stop the Server
Press Ctrl+C in the terminal.

## Notes
1. The server only listens on 127.0.0.1 (localhost). To allow external connections, change SERVER_HOST to '0.0.0.0' in the code.
2. The default port is 8080. Change SERVER_PORT if needed.
3. Place all web files (HTML, images, etc.) inside the htdocs folder.
4. Do not manually delete server.log while the server is running; stop the server first.

## Troubleshooting
1. "Address already in use": Change SERVER_PORT to another number (e.g., 8081) or stop the program using that port.
2. No log file created: Ensure the program has write permission in the current directory. The log file path is set to os.path.join(os.path.dirname(__file__), 'server.log'), so it will be created next to the script.