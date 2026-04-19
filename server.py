import pickle
import socket
import threading
import time
import uuid


BUFFER_SIZE = 4096
HEADER_SIZE = 4


def send_message(sock, message):
    payload = pickle.dumps(message)
    header = len(payload).to_bytes(HEADER_SIZE, "big")
    sock.sendall(header + payload)


def recv_exact(sock, size):
    chunks = bytearray()
    while len(chunks) < size:
        packet = sock.recv(size - len(chunks))
        if not packet:
            return None
        chunks.extend(packet)
    return bytes(chunks)


def recv_message(sock):
    header = recv_exact(sock, HEADER_SIZE)
    if not header:
        return None
    payload_size = int.from_bytes(header, "big")
    payload = recv_exact(sock, payload_size)
    if not payload:
        return None
    return pickle.loads(payload)


def request_response(host, port, message, timeout=3.0):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect((host, port))
        send_message(client, message)
        return recv_message(client)
    finally:
        try:
            client.close()
        except OSError:
            pass


def get_local_ip():
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        try:
            probe.close()
        except OSError:
            pass


class RoomDirectoryServer:
    def __init__(self, host="0.0.0.0", port=12345):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = True
        self.rooms = {}
        self.lock = threading.Lock()

    def start(self):
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(16)
            print(f"Room directory started on {self.host}:{self.port}")
            while self.running:
                client_socket, addr = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, addr),
                    daemon=True,
                )
                client_thread.start()
        except OSError as exc:
            if self.running:
                print(f"Room directory error: {exc}")
        finally:
            self.stop()

    def handle_client(self, client_socket, addr):
        try:
            message = recv_message(client_socket)
            if not message:
                return

            msg_type = message.get("type")
            if msg_type == "list_rooms":
                send_message(client_socket, {"type": "room_list", "rooms": self.get_rooms()})
            elif msg_type == "register_room":
                room = {
                    "room_id": message["room_id"],
                    "name": message["name"],
                    "host": message["host"],
                    "port": message["port"],
                    "max_players": message["max_players"],
                    "connected_players": message["connected_players"],
                    "game_started": message.get("game_started", False),
                    "updated_at": time.time(),
                }
                with self.lock:
                    self.rooms[room["room_id"]] = room
                send_message(client_socket, {"type": "ok"})
            elif msg_type == "update_room":
                room_id = message.get("room_id")
                with self.lock:
                    room = self.rooms.get(room_id)
                    if room:
                        room["connected_players"] = message.get("connected_players", room["connected_players"])
                        room["game_started"] = message.get("game_started", room["game_started"])
                        room["updated_at"] = time.time()
                send_message(client_socket, {"type": "ok"})
            elif msg_type == "unregister_room":
                room_id = message.get("room_id")
                with self.lock:
                    self.rooms.pop(room_id, None)
                send_message(client_socket, {"type": "ok"})
            else:
                send_message(client_socket, {"type": "error", "reason": f"Unknown message type {msg_type}"})
        except Exception as exc:
            print(f"Directory client error from {addr}: {exc}")
        finally:
            try:
                client_socket.close()
            except OSError:
                pass

    def get_rooms(self):
        with self.lock:
            stale_room_ids = [
                room_id for room_id, room in self.rooms.items()
                if time.time() - room.get("updated_at", 0) > 30
            ]
            for room_id in stale_room_ids:
                self.rooms.pop(room_id, None)

            rooms = [
                {
                    "room_id": room["room_id"],
                    "name": room["name"],
                    "addr": f"{room['host']}:{room['port']}",
                    "host": room["host"],
                    "port": room["port"],
                    "max_players": room["max_players"],
                    "connected_players": room["connected_players"],
                    "game_started": room.get("game_started", False),
                }
                for room in self.rooms.values()
                if not room.get("game_started", False)
            ]
        rooms.sort(key=lambda item: item["name"].lower())
        return rooms

    def stop(self):
        if not self.running:
            return
        self.running = False
        try:
            self.server_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.server_socket.close()
        except OSError:
            pass


class GameServer:
    def __init__(
        self,
        host="0.0.0.0",
        port=0,
        player_count_callback=None,
        room_name="Unnamed",
        max_players=2,
        action_callback=None,
        directory_host="127.0.0.1",
        directory_port=12345,
    ):
        self.host = host
        self.port = port
        self.directory_host = directory_host
        self.directory_port = directory_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = []
        self.running = True
        self.player_count_callback = player_count_callback
        self.room_name = room_name
        self.max_players = max_players
        self.accept_thread = None
        self.action_callback = action_callback
        self.game_started = False
        self.lock = threading.Lock()
        self.room_id = str(uuid.uuid4())
        self.public_host = get_local_ip()
        self.directory_registered = False
        self.directory_thread = None

    def start(self):
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.max_players)
            self.port = self.server_socket.getsockname()[1]
            print(f"Game room server started on {self.host}:{self.port}")
            self.register_room()

            self.accept_thread = threading.Thread(target=self.accept_connections, daemon=True)
            self.accept_thread.start()

            self.directory_thread = threading.Thread(target=self.directory_heartbeat_loop, daemon=True)
            self.directory_thread.start()

            while self.running:
                time.sleep(0.1)
        except Exception as exc:
            if self.running:
                print(f"Game server error: {exc}")
        finally:
            self.stop()

    def register_room(self):
        response = request_response(
            self.directory_host,
            self.directory_port,
            {
                "type": "register_room",
                "room_id": self.room_id,
                "name": self.room_name,
                "host": self.public_host,
                "port": self.port,
                "max_players": self.max_players,
                "connected_players": self.connected_players_count(),
                "game_started": self.game_started,
            },
        )
        self.directory_registered = bool(response and response.get("type") == "ok")
        if not self.directory_registered:
            print("Warning: room could not be registered in the directory server")

    def update_directory_room(self):
        if not self.directory_registered:
            return
        try:
            request_response(
                self.directory_host,
                self.directory_port,
                {
                    "type": "update_room",
                    "room_id": self.room_id,
                    "connected_players": self.connected_players_count(),
                    "game_started": self.game_started,
                },
            )
        except OSError:
            pass

    def unregister_room(self):
        if not self.directory_registered:
            return
        try:
            request_response(
                self.directory_host,
                self.directory_port,
                {"type": "unregister_room", "room_id": self.room_id},
            )
        except OSError:
            pass
        self.directory_registered = False

    def directory_heartbeat_loop(self):
        while self.running:
            self.update_directory_room()
            time.sleep(5)

    def accept_connections(self):
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                with self.lock:
                    if len(self.clients) >= max(0, self.max_players - 1):
                        send_message(client_socket, {"type": "error", "reason": "Room is full"})
                        client_socket.close()
                        continue

                    used_indexes = {client["player_index"] for client in self.clients}
                    player_index = 1
                    while player_index in used_indexes:
                        player_index += 1
                    client_info = {
                        "socket": client_socket,
                        "addr": addr,
                        "player_index": player_index,
                    }
                    self.clients.append(client_info)

                send_message(
                    client_socket,
                    {
                        "type": "assign_index",
                        "player_index": player_index,
                        "num_players": self.max_players,
                        "connected_players": self.connected_players_count(),
                        "room_name": self.room_name,
                    },
                )

                self.notify_player_count_changed()
                self.broadcast_room_status()

                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_info,),
                    daemon=True,
                )
                client_thread.start()
            except OSError:
                break

    def handle_client(self, client_info):
        client_socket = client_info["socket"]
        addr = client_info["addr"]
        player_index = client_info["player_index"]

        try:
            while self.running:
                message = recv_message(client_socket)
                if not message:
                    break

                msg_type = message.get("type")
                if msg_type == "join_request":
                    send_message(
                        client_socket,
                        {
                            "type": "join_ack",
                            "player_index": player_index,
                            "num_players": self.max_players,
                            "connected_players": self.connected_players_count(),
                            "room_name": self.room_name,
                            "game_started": self.game_started,
                        },
                    )
                    if self.game_started:
                        send_message(
                            client_socket,
                            {
                                "type": "error",
                                "reason": "Game already started",
                            },
                        )
                elif msg_type == "heartbeat":
                    send_message(client_socket, {"type": "heartbeat_ack", "player_index": player_index})
                elif msg_type == "action":
                    if not self.game_started:
                        send_message(client_socket, {"type": "error", "reason": "Game has not started yet"})
                        continue
                    if not self.action_callback:
                        send_message(client_socket, {"type": "error", "reason": "No action handler configured"})
                        continue

                    accepted, reason = self.action_callback(player_index, message.get("payload", {}))
                    send_message(
                        client_socket,
                        {
                            "type": "action_ack",
                            "accepted": accepted,
                            "reason": reason,
                        },
                    )
                else:
                    send_message(client_socket, {"type": "error", "reason": f"Unknown message type {msg_type}"})
        except Exception as exc:
            print(f"Error handling client {addr}: {exc}")
        finally:
            self.remove_client(client_info)
            print(f"Client {addr} disconnected")

    def connected_players_count(self):
        with self.lock:
            return len(self.clients) + 1

    def connected_client_count(self):
        with self.lock:
            return len(self.clients)

    def notify_player_count_changed(self):
        if self.player_count_callback:
            self.player_count_callback(self.connected_players_count())
        self.update_directory_room()

    def remove_client(self, client_info):
        with self.lock:
            if client_info in self.clients:
                self.clients.remove(client_info)
        try:
            client_info["socket"].close()
        except OSError:
            pass
        self.notify_player_count_changed()
        self.broadcast_room_status()

    def broadcast(self, message):
        with self.lock:
            clients = list(self.clients)
        for client_info in clients:
            try:
                send_message(client_info["socket"], message)
            except OSError:
                self.remove_client(client_info)

    def broadcast_room_status(self):
        self.broadcast(
            {
                "type": "room_status",
                "connected_players": self.connected_players_count(),
                "num_players": self.max_players,
                "room_name": self.room_name,
                "game_started": self.game_started,
            }
        )

    def send_initial_state(self, state):
        self.game_started = True
        self.update_directory_room()
        self.broadcast(
            {
                "type": "initial_state",
                "state": state,
            }
        )
        self.broadcast_room_status()

    def broadcast_state(self, state):
        self.broadcast({"type": "state_update", "state": state})

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.unregister_room()
        try:
            self.server_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.server_socket.close()
        except OSError:
            pass

        with self.lock:
            clients = list(self.clients)
            self.clients.clear()

        for client_info in clients:
            try:
                client_info["socket"].close()
            except OSError:
                pass


if __name__ == "__main__":
    directory = RoomDirectoryServer()
    try:
        directory.start()
    except KeyboardInterrupt:
        print("Room directory shutting down...")
        directory.stop()
