import pygame
import sys

from settings import *
from pygame.locals import *

class Menu:
    def __init__(self):
        # bg
        self.bg = pygame.transform.scale(
            pygame.image.load("asset/Menubg.png").convert_alpha(),
            (WINDOW_RESOLUTION[0]*GAME_SCALE, WINDOW_RESOLUTION[1]*GAME_SCALE)
        )
        # dark overlay
        self.overlay = pygame.Surface(WINDOW_RESOLUTION)
        self.overlay.set_alpha(180)
        self.overlay.fill((0,0,0))

        # black bg
        self.blackbg = pygame.Surface(WINDOW_RESOLUTION)
        self.blackbg.fill((0, 0, 0))

        self.image = self.bg

        self.state = 0
        self.in_menu = True
        self.settings = False
        self.multiplayer = False
        self.hosting = False
        self.joining = False
        self.waiting_for_players = False
        self.waiting_is_host = True
        self.current_bot = 0  # index in BOT_TYPES
        self.current_num_players = 2  # number of players (2-4)
        self.host_port = 12345
        self.host_room_name = ""
        self.host_input_field = None
        self.connected_players = 1  # Start with 1 (the host)
        self.available_servers = []
        self.selected_server = None
        self.rect = self.image.get_rect(topleft=(0,0))
        self.font = pygame.font.SysFont("Arial", 28, bold=True)

        button_size = (300*GAME_SCALE, 70*GAME_SCALE)
        center_x, center_y = 870*GAME_SCALE, 500*GAME_SCALE
        spacing = 70
        self.spacing = spacing

        # init menu buttons
        self.continue_button = MenuButton("Continue", (center_x, center_y-spacing), button_size)
        self.start_button = MenuButton("Start Game (PvE)", (center_x, center_y), button_size)
        self.multiplayer_button = MenuButton("Multiplayer", (center_x, center_y+spacing), button_size)
        self.settings_button = MenuButton("Settings", (center_x, center_y+2*spacing), button_size)
        self.quit_button = MenuButton("Quit", (center_x, center_y+3*spacing), button_size)
        self.init_buttons = [
            self.start_button,
            self.multiplayer_button,
            self.settings_button,
            self.quit_button,
        ]
        self.has_saved_game = False
        self.selected_option = None

        # pause menu buttons
        cx, cy = WINDOW_RESOLUTION[0]*GAME_SCALE//2, WINDOW_RESOLUTION[1]*GAME_SCALE//2
        self.cx = cx
        self.cy = cy
        self.pause_buttons = [
            MenuButton("Continue", (cx, cy-spacing), button_size, (0,0,200), (100,100,255)),
            MenuButton("Settings", (cx, cy), button_size, (0,0,200), (100,100,255)),
            MenuButton("Main Menu", (cx, cy+spacing), button_size, (0,0,200), (100,100,255)),
            MenuButton("Quit", (cx, cy+2*spacing), button_size, (0,0,200), (100,100,255)),
        ]

        # settings menu buttons (always centered, pure black background)
        self.settings_buttons = [
            MenuButton("Volume -", (cx-150, cy-3*spacing), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Volume +", (cx+150, cy-3*spacing), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Scale -", (cx-150, cy-2*spacing), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Scale +", (cx+150, cy-2*spacing), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Players -", (cx-150, cy-spacing), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Players +", (cx+150, cy-spacing), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Bot -", (cx-150, cy), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Bot +", (cx+150, cy), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Back", (cx, cy+spacing), button_size, (0,0,200), (100,100,255)),
        ]

        # multiplayer menu buttons
        self.multiplayer_buttons = [
            MenuButton("Host", (cx, cy-2*spacing), button_size, (0,0,200), (100,100,255)),
            MenuButton("Join", (cx, cy-spacing), button_size, (0,0,200), (100,100,255)),
            MenuButton("Back", (cx, cy+spacing), button_size, (0,0,200), (100,100,255)),
        ]

        # host submenu buttons
        self.host_room_button = MenuButton("Room Name", (cx, cy-2*spacing), button_size, (0,0,200), (100,100,255))
        self.host_buttons = [
            self.host_room_button,
            MenuButton("Players -", (cx-150, cy-spacing), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Players +", (cx+150, cy-spacing), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Bot -", (cx-150, cy), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Bot +", (cx+150, cy), (150, 60), (0,0,200), (100,100,255)),
            MenuButton("Start Host", (cx, cy+spacing), button_size, (0,0,200), (100,100,255)),
            MenuButton("Back", (cx, cy+2*spacing), button_size, (0,0,200), (100,100,255)),
        ]

        # join submenu buttons
        self.join_room_buttons = [
            MenuButton("No rooms found", (cx, cy-2*spacing), button_size, (0,0,200), (100,100,255)),
            MenuButton("", (cx, cy-spacing), button_size, (0,0,200), (100,100,255)),
            MenuButton("", (cx, cy), button_size, (0,0,200), (100,100,255)),
        ]
        self.join_buttons = [
            *self.join_room_buttons,
            MenuButton("Refresh", (cx, cy+spacing), button_size, (0,0,200), (100,100,255)),
            MenuButton("Back", (cx, cy+2*spacing), button_size, (0,0,200), (100,100,255)),
        ]

        # waiting for players buttons
        self.waiting_buttons = [
            MenuButton("Start Game", (cx, cy), button_size, (0,200,0), (100,255,100)),
            MenuButton("Quit", (cx, cy+spacing), button_size, (200,0,0), (255,100,100)),
        ]
        self.client_waiting_buttons = [
            MenuButton("Leave Room", (cx, cy+spacing), button_size, (200,0,0), (255,100,100)),
        ]

        self.buttons = self.init_buttons

    def draw(self, screen):
        if not self.in_menu:
            return
        mouse_pos = pygame.mouse.get_pos()
        screen.blit(self.image, self.rect)
        for b in self.buttons:
            b.draw(screen, self.font)
        
        if self.settings:
            # Display settings labels aligned with their button rows
            volume_text = self.font.render("Volume:", True, (255,255,255))
            scale_text = self.font.render("Scale:", True, (255,255,255))
            players_text = self.font.render(f"Players: {self.current_num_players}", True, (255,255,255))
            bot_text = self.font.render(f"{BOT_TYPES[self.current_bot]}", True, (255,255,255))
            
            # Position texts 35 pixels above their respective button rows
            screen.blit(volume_text, (self.cx - volume_text.get_width()//2, self.cy - 3*self.spacing - 15))
            screen.blit(scale_text, (self.cx - scale_text.get_width()//2, self.cy - 2*self.spacing - 15))
            screen.blit(players_text, (self.cx - players_text.get_width()//2, self.cy - self.spacing - 15))
            screen.blit(bot_text, (self.cx - bot_text.get_width()//2, self.cy - 15))
        elif self.multiplayer:
            label = self.font.render("Multiplayer", True, (255,255,255))
            screen.blit(label, (self.cx - label.get_width()//2, self.cy - 3*self.spacing - 15))
        elif self.hosting:
            players_text = self.font.render(f"Players: {self.current_num_players}", True, (255,255,255))
            bot_text = self.font.render(f"Bot: {BOT_TYPES[self.current_bot]}", True, (255,255,255))
            screen.blit(players_text, (self.cx - players_text.get_width()//2, self.cy - self.spacing - 15))
            screen.blit(bot_text, (self.cx - bot_text.get_width()//2, self.cy - 15))
        elif self.waiting_for_players:
            waiting_label = "Waiting for Players..." if self.waiting_is_host else "Waiting for Host to Start..."
            waiting_text = self.font.render(waiting_label, True, (255,255,255))
            players_count_text = self.font.render(f"Connected Players: {self.connected_players}/{self.current_num_players}", True, (255,255,0))
            room_text = self.font.render(f"Room: {self.host_room_name or 'Unnamed'}", True, (255,255,255))
            screen.blit(waiting_text, (self.cx - waiting_text.get_width()//2, self.cy - 3*self.spacing - 15))
            screen.blit(room_text, (self.cx - room_text.get_width()//2, self.cy - 2*self.spacing - 15))
            screen.blit(players_count_text, (self.cx - players_count_text.get_width()//2, self.cy - self.spacing - 15))
        elif self.joining:
            title_text = self.font.render("Available Servers", True, (255,255,255))
            screen.blit(title_text, (self.cx - title_text.get_width()//2, self.cy - 3*self.spacing - 15))

    def update(self):
        if self.settings:
            self.image = self.blackbg
            self.buttons = self.settings_buttons
        elif self.multiplayer:
            self.image = self.blackbg
            self.buttons = self.multiplayer_buttons
        elif self.hosting:
            self.image = self.blackbg
            self.buttons = self.host_buttons
        elif self.waiting_for_players:
            self.image = self.blackbg
            self.buttons = self.waiting_buttons if self.waiting_is_host else self.client_waiting_buttons
        elif self.joining:
            self.image = self.blackbg
            self.buttons = self.join_buttons
            for idx, button in enumerate(self.join_room_buttons):
                if idx < len(self.available_servers):
                    server = self.available_servers[idx]
                    button.name = f"{server['name']} ({server['connected_players']}/{server['max_players']})"
                elif idx == 0:
                    button.name = "No rooms found"
                else:
                    button.name = ""
        elif self.state == 0:
            self.image = self.bg
            self.buttons = [self.continue_button] + self.init_buttons if self.has_saved_game else self.init_buttons
        else:
            self.image = self.overlay
            self.buttons = self.pause_buttons

        mousepos = pygame.mouse.get_pos()
        for b in self.buttons:
            b.update(mousepos)

    def handle_input(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if self.multiplayer:
            for b in self.multiplayer_buttons:
                if b.handle(event):
                    print(f"{b.name} clicked")
                    match b.name:
                        case "Back":
                            self.multiplayer = False
                        case "Host":
                            self.hosting = True
                            self.multiplayer = False
                        case "Join":
                            self.joining = True
                            self.multiplayer = False
                            self.selected_option = "Refresh Rooms"
                            return True
            return False

        if self.hosting:
            for b in self.host_buttons:
                if b.handle(event):
                    print(f"{b.name} clicked")
                    match b.name:
                        case "Back":
                            self.hosting = False
                            self.host_input_field = None
                            self.host_room_button.set_active(False)
                        case "Room Name":
                            self.host_input_field = "room"
                            self.host_room_name = ""
                            self.host_room_button.set_active(True)
                        case "Players -":
                            self.current_num_players = max(MIN_PLAYERS, self.current_num_players - 1)
                            self.host_input_field = None
                            self.host_room_button.set_active(False)
                        case "Players +":
                            self.current_num_players = min(MAX_PLAYERS, self.current_num_players + 1)
                            self.host_input_field = None
                            self.host_room_button.set_active(False)
                        case "Bot -":
                            self.current_bot = (self.current_bot - 1) % len(BOT_TYPES)
                            self.host_input_field = None
                            self.host_room_button.set_active(False)
                        case "Bot +":
                            self.current_bot = (self.current_bot + 1) % len(BOT_TYPES)
                            self.host_input_field = None
                            self.host_room_button.set_active(False)
                        case "Start Host":
                            self.selected_option = "Host"
                            self.hosting = False
                            self.host_input_field = None
                            self.host_room_button.set_active(False)
                            return True
            if event.type == pygame.KEYDOWN and self.host_input_field is not None:
                if self.host_input_field == "room":
                    if event.key == pygame.K_BACKSPACE:
                        self.host_room_name = self.host_room_name[:-1]
                    elif len(self.host_room_name) < 20 and event.unicode.isprintable():
                        self.host_room_name = self.host_room_name + event.unicode
                    self.host_room_button.set_name(f"Room: {self.host_room_name}")
            return False

        if self.joining:
            for idx, b in enumerate(self.join_room_buttons):
                if idx < len(self.available_servers):
                    server = self.available_servers[idx]
                    b.name = f"{server['name']} ({server['connected_players']}/{server['max_players']})"
                elif idx == 0:
                    b.name = "No rooms found"
                else:
                    b.name = ""
                if b.handle(event):
                    print(f"{b.name} clicked")
                    if idx < len(self.available_servers):
                        self.selected_server = self.available_servers[idx]["addr"]
                        self.host_room_name = self.available_servers[idx]["name"]
                        self.selected_option = "Join"
                        self.joining = False
                        return True
            for b in self.join_buttons[len(self.join_room_buttons):]:
                if b.handle(event):
                    print(f"{b.name} clicked")
                    if b.name == "Back":
                        self.joining = False
                    elif b.name == "Refresh":
                        self.selected_option = "Refresh Rooms"
                        return True
            return False

        if self.waiting_for_players:
            active_waiting_buttons = self.waiting_buttons if self.waiting_is_host else self.client_waiting_buttons
            for b in active_waiting_buttons:
                if b.handle(event):
                    print(f"{b.name} clicked")
                    if self.waiting_is_host:
                        match b.name:
                            case "Start Game":
                                self.selected_option = "Start Multiplayer Game"
                                self.waiting_for_players = False
                                return True
                            case "Quit":
                                self.selected_option = "Quit Hosting"
                                self.waiting_for_players = False
                                return True
                    elif b.name == "Leave Room":
                        self.selected_option = "Leave Waiting Room"
                        self.waiting_for_players = False
                        return True
            return False

        if self.settings:
            for b in self.settings_buttons:
                if b.handle(event):
                    print(f"{b.name} clicked")
                    match b.name:
                        case "Back":
                            self.settings = False
                        case "Volume -":
                            print("Decrease volume")
                        case "Volume +":
                            print("Increase volume")
                        case "Scale -":
                            print("Decrease scale")
                        case "Scale +":
                            print("Increase scale")
                        case "Players -":
                            # Only allow changing players in main menu (state == 0)
                            if self.state == 0:
                                self.current_num_players = max(MIN_PLAYERS, self.current_num_players - 1)
                        case "Players +":
                            # Only allow changing players in main menu (state == 0)
                            if self.state == 0:
                                self.current_num_players = min(MAX_PLAYERS, self.current_num_players + 1)
                        case "Bot -":
                            # Only allow changing bot in main menu (state == 0)
                            if self.state == 0:
                                self.current_bot = (self.current_bot - 1) % len(BOT_TYPES)
                        case "Bot +":
                            # Only allow changing bot in main menu (state == 0)
                            if self.state == 0:
                                self.current_bot = (self.current_bot + 1) % len(BOT_TYPES)
            return False

        for b in self.buttons:
            if b.handle(event):
                print(f"{b.name} clicked")
                self.selected_option = b.name
                match b.name:
                    case "Quit":
                        pygame.quit()
                        sys.exit()
                    case "Settings":
                        self.settings = True
                        self.selected_option = None
                        return False
                    case "Multiplayer":
                        self.multiplayer = True
                        self.selected_option = None
                        return False
                    case "Main Menu":
                        self.in_menu = True
                        self.state = 0
                        return True
                    case _:
                        self.in_menu = False
                        self.state = 1
                        return True

class MenuButton:
    def __init__(self, name, pos, button_size, 
                 normal_color=(200,0,0), hover_color=(255,100,100), active_color=(255,200,0)):
        self.name = name
        self.rect = pygame.Rect(0, 0, *button_size)
        self.rect.center = pos
        self.normal_color = normal_color
        self.hover_color = hover_color
        self.active_color = active_color
        self.active = False
        self.color = self.normal_color

    def draw(self, screen, font):
        pygame.draw.rect(screen, self.color, self.rect, border_radius=8)
        pygame.draw.rect(screen, (0,0,0), self.rect, 2, border_radius=8)
        label = font.render(self.name, True, (255,255,255))
        screen.blit(label, (
            self.rect.centerx - label.get_width()//2,
            self.rect.centery - label.get_height()//2
        ))

    def update(self, mouse_pos):
        if self.active:
            self.color = self.active_color
        else:
            self.color = self.hover_color if self.rect.collidepoint(mouse_pos) else self.normal_color

    def set_name(self, name):
        self.name = name

    def set_active(self, active):
        self.active = active

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False
