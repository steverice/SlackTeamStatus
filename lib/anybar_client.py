import socket


class AnyBarClient(object):
    port = 1738
    client = None

    def __init__(self, port=1738, address="localhost"):
        self.port = port
        self.address = address
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def update_status(self, status):
        self.socket.sendto(status.encode(), (self.address, self.port))
