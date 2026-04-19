#!/usr/bin/env python3
"""
Server runner script for the room directory service.
Run this script first so hosts can register rooms and joiners can discover them.
"""

from server import RoomDirectoryServer

if __name__ == "__main__":
    print("Starting room directory server...")
    server = RoomDirectoryServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        server.stop()
