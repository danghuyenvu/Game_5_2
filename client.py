import socket
import threading
import time

from server import recv_message, request_response, send_message


class GameClient:
    def __init__(
        self,
        server_ip,
        server_port,
        room_name=None,
        state_callback=None,
        room_status_callback=None,
    ):
        self.server_ip = server_ip
        self.server_port = server_port
        self.room_name = room_name
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_lock = threading.Lock()
        self.connected = False
        self.running = True
        self.player_index = None
        self.state_callback = state_callback
        self.room_status_callback = room_status_callback
        self.assigned_event = threading.Event()
        self.last_heartbeat_ack = None
        self.connected_players = 1
        self.target_num_players = None
        self.game_started = False
        self.last_error = None

    def connect(self):
        try:
            self.socket.connect((self.server_ip, self.server_port))
            self.connected = True
            print(f"Connected to game server at {self.server_ip}:{self.server_port}")

            listen_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
            listen_thread.start()

            self.send_message({"type": "join_request", "room_name": self.room_name})

            if not self.assigned_event.wait(3.0):
                self.last_error = "Did not receive player assignment from server"
                self.disconnect()
                return False

            heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
            heartbeat_thread.start()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            print(f"Failed to connect to server: {exc}")
            return False

    def listen_for_messages(self):
        while self.running and self.connected:
            try:
                message = recv_message(self.socket)
                if not message:
                    break

                msg_type = message.get("type")
                if msg_type in {"assign_index", "join_ack"}:
                    self.player_index = message.get("player_index", self.player_index)
                    self.target_num_players = message.get("num_players", self.target_num_players)
                    self.connected_players = message.get("connected_players", self.connected_players)
                    self.room_name = message.get("room_name", self.room_name)
                    self.game_started = message.get("game_started", self.game_started)
                    self.assigned_event.set()
                    self._notify_room_status()
                elif msg_type == "initial_state":
                    self.game_started = True
                    if self.state_callback:
                        self.state_callback("initial", message.get("state"))
                elif msg_type == "state_update":
                    if self.state_callback:
                        self.state_callback("update", message.get("state"))
                elif msg_type == "room_status":
                    self.connected_players = message.get("connected_players", self.connected_players)
                    self.target_num_players = message.get("num_players", self.target_num_players)
                    self.room_name = message.get("room_name", self.room_name)
                    self.game_started = message.get("game_started", self.game_started)
                    self._notify_room_status()
                elif msg_type == "heartbeat_ack":
                    self.last_heartbeat_ack = time.time()
                elif msg_type == "action_ack":
                    if not message.get("accepted", False):
                        self.last_error = message.get("reason")
                elif msg_type == "error":
                    self.last_error = message.get("reason")
                    print(f"Server error: {self.last_error}")
                else:
                    print(f"Unhandled server message type: {msg_type}")
            except Exception as exc:
                self.last_error = str(exc)
                print(f"Error receiving message: {exc}")
                break

        self.connected = False
        print("Disconnected from game server")

    def _notify_room_status(self):
        if self.room_status_callback:
            self.room_status_callback(
                {
                    "connected_players": self.connected_players,
                    "num_players": self.target_num_players,
                    "room_name": self.room_name,
                    "game_started": self.game_started,
                }
            )

    def heartbeat_loop(self):
        while self.running and self.connected:
            self.send_message({"type": "heartbeat", "player_index": self.player_index})
            time.sleep(5.0)
            if self.last_heartbeat_ack and time.time() - self.last_heartbeat_ack > 15:
                self.last_error = "Heartbeat timeout"
                self.disconnect()
                break

    def send_message(self, message):
        if not self.connected:
            return False
        try:
            with self.socket_lock:
                send_message(self.socket, message)
            return True
        except Exception as exc:
            self.last_error = str(exc)
            print(f"Failed to send message: {exc}")
            return False

    def send_action(self, action_payload):
        return self.send_message(
            {
                "type": "action",
                "payload": action_payload,
            }
        )

    def disconnect(self):
        self.running = False
        if self.connected:
            try:
                self.socket.close()
            except OSError:
                pass
            self.connected = False
            print("Disconnected from server")


def fetch_available_rooms(directory_host, directory_port, timeout=3.0):
    try:
        response = request_response(
            directory_host,
            directory_port,
            {"type": "list_rooms"},
            timeout=timeout,
        )
        if response and response.get("type") == "room_list":
            return response.get("rooms", [])
    except Exception as exc:
        print(f"Failed to fetch room list: {exc}")
    return []
