import os
import socket
import uvicorn

PORT = int(os.environ.get("PORT", "6810"))

sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("::", PORT))
sock.listen(128)
sock.setblocking(False)

uvicorn.run("amaru.app:app", fd=sock.fileno())
