import pygame
from concurrent.futures import ThreadPoolExecutor
import threading
import pickle
import socket
import os

from pygame.locals import *
from settings import * 
from Deck import *
from bank import *
from Menu import *
from player import *
from minimax import *
from monte_carlo import *
import time

class Game():
    def __init__(self, workers=4):
        # pygame stuff
        pygame.init()
        self.screen = pygame.display.set_mode(WINDOW_RESOLUTION)
        pygame.display.set_caption(GAME_NAME)
        self.clock = pygame.time.Clock()

        # Menu
        self.menu = Menu()
        self.start = False
        self.initialized = False

        # Multiplayer
        self.server = None
        self.client = None
        self.is_host = False
        self.is_client = False
        self.pending_network_actions = []
        self.pending_network_lock = threading.Lock()

        self.running = True
        self.bot_thinking = False
        self.game_over = False
        self.winner_text = ""
        self.bot = None
        self.save_dir = "game_saves"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        self.executor = ThreadPoolExecutor(max_workers=workers)
        # game stuffs here
        self.cards = None
        self.nobles = None
        self.shown_nobles = []
        self.players = []
        self.bank = None

        self.level1 = None
        self.level2 = None
        self.level3 = None

        self.board = {}

        self.gems = []
        # Sửa dòng này trong __init__
        for gem_name in GEMS_INDEX:
            img = pygame.image.load(f"asset/{gem_name}.png").convert_alpha()
            self.gems.append(img)

        self.current_player = 0
        self.num_player = 2
        self.choosing_card = None
        self.choosing_cost = [0,0,0,0,0,0]
        self.choosing_gems = [0,0,0,0,0]
        self.choosing_nobles = []
        self.show_noble_overlay = False
        self.action_button_rects = []
        self.cost_rects = []
        self.gems_rect = []
        self.card_rects = [[],[],[]]
        self.deposit_rects = []
        self.noble_rects = []
        self.board_rect = None
        self.bank_rect = None
        self.action_box_rect = None
        self.noble_area_rect = None

        self.current_action = None   # "TAKE 3", "TAKE 2", "RESERVE", "BUY"
        self.selected_gems = []      # indices for TAKE 3
        self.selected_gem = None     # index for TAKE 2

    def get_selected_bot(self):
        from settings import BOT_TYPES
        bot_index = self.menu.current_bot
        if bot_index == 0:
            return RandomBot()
        elif bot_index == 1:
            return Monte_carlo()
        elif bot_index == 2:
            return MinmaxPlayer()
        return RandomBot()  # default

    # Setting up game (can be used to restart new game)
    def init_game(self, num_player = 2, bot=None):
        if not hasattr(self, 'font'):
            self.font = pygame.font.SysFont("Arial", 16, bold=True)
        self.noble_rects = []
        self.card_rects = [[], [], []]
        self.cost_rects = []
        self.gems_rect = []
        self.action_button_rects = []
        self.deposit_rects = []
        cards_by_level, self.cards, self.nobles = process_card_data()
        self.level1 = CardDeck(cards_by_level[1], 1)
        self.level2 = CardDeck(cards_by_level[2], 2)
        self.level3 = CardDeck(cards_by_level[3], 3)
        self.board = {
            1: [self.level1.draw() for _ in range(4)],
            2: [self.level2.draw() for _ in range(4)],
            3: [self.level3.draw() for _ in range(4)]
        }
        self.num_player = num_player
        # Create first player as human, rest as bots
        self.players = [Player()]
        for i in range(1, num_player):
            self.players.append(self.get_selected_bot())
        self.bank = Bank(self.gems, None, num_player)
        # load sprites trước khi draw
        for card in self.cards:
            self.executor.submit(card.load)
        for noble in self.nobles.nobles:
            self.executor.submit(noble.load)
        
        # Chờ noble load xong trước khi bắt đầu game
        for noble in self.nobles.nobles:
            while noble.image is None:
                time.sleep(0.01)
        
        self.shown_nobles = [self.nobles.draw() for _ in range(num_player + 1)]


        main_width = int(WINDOW_RESOLUTION[0] * 0.75)
        main_height = WINDOW_RESOLUTION[1]

        self.noble_area_rect = pygame.Rect(START_X + (CARD_W + GAP), 20, (num_player + 1) * (CARD_W + GAP), CARD_W)
        board_height = 3 * (CARD_H + GAP)
        board_width = 4 * (CARD_W + GAP)
        self.board_rect = pygame.Rect(START_X + (CARD_W + GAP), 150, board_width, board_height)


        for i, noble in enumerate(self.shown_nobles):
            noble_rect = pygame.Rect(START_X + (i + 1) * (CARD_W + GAP), 20, CARD_W, CARD_W) # Noble thường hình vuông
            self.noble_rects.append(noble_rect)

        for level in [1, 2, 3]:
            # Tính tọa độ Y dựa trên Level (3 là cao nhất)
            row_y = 150 + (3 - level) * (CARD_H + GAP)
            # Vẽ các lá bài đang lật trên bàn
            if level in self.board:
                for i, card in enumerate(self.board[level]):
                    card_x = START_X + (i + 1) * (CARD_W + GAP)
                    card_rect = pygame.Rect(card_x, row_y, CARD_W, CARD_H)
                    self.card_rects[level-1].append(card_rect)
        # 4. Draw gem
        gems_start_x = START_X + 5 * (CARD_W + GAP) + 30 
        bank_h = len(GEMS_INDEX) * (GEM_SIZE + VERTICAL_GAP)
        self.bank_rect = pygame.Rect(gems_start_x, GEMS_START_Y, GEM_SIZE, bank_h)

        for i, gem_img in enumerate(self.gems):
            # Chỉ tính toán theo hàng dọc (row), không dùng cột (col)
            gem_x = gems_start_x
            gem_y = GEMS_START_Y + i * (GEM_SIZE + VERTICAL_GAP)
           
            gem_rect = pygame.Rect(gem_x, gem_y, GEM_SIZE, GEM_SIZE)
            self.gems_rect.append(gem_rect)

        # 5. Draw action box
        action_y_start = main_height - ACTION_ZONE_H
        self.action_box_rect = pygame.Rect(0, action_y_start, main_width, ACTION_ZONE_H)
        

        for i, _ in enumerate(GEMS_INDEX):
            # Tính toán cột và hàng (3 cột, 2 hàng)
            col = i % 3
            row = i // 3
            
            gx = RESOURCE_START_X + col * ( GAP * 2 + GEM_DISPLAY_SIZE)
            gy = action_y_start + 20 + row * (GAP + GEM_DISPLAY_SIZE)
            
            # Vẽ hình ảnh viên đá
            
            # Lưu rect để handle click
            gem_rect = pygame.Rect(gx, gy, GEM_DISPLAY_SIZE, GEM_DISPLAY_SIZE)
            self.cost_rects.append(gem_rect)


        # def action
        actions = [
            "TAKE 3",
            "TAKE 2",
            "RESERVE",
            "BUY"
        ]
        
        # position in map
        start_button_x = main_width - (ACTION_BTN_W + ACTION_GAP) * 2 - ACTION_GAP
        start_button_y = main_height - ACTION_ZONE_H + ACTION_GAP 

        for i, _ in enumerate(actions):
            # Sắp xếp thành lưới 2x2
            col = i % 2
            row = i // 2
            
            bx = start_button_x + col * (ACTION_BTN_W + ACTION_GAP)
            by = start_button_y + row * (60 + ACTION_GAP) # 60 là chiều cao nút rút gọn
            
            btn_rect = pygame.Rect(bx, by, ACTION_BTN_W, 60)
            self.action_button_rects.append(btn_rect)

        # deposit rect
        for index in range(3):
            card_pos = (DEPOSIT_POS[0] + DEPOSIT_OFFSET * index, DEPOSIT_POS[1])
            rect = pygame.Rect(card_pos[0], card_pos[1], CARD_W, CARD_H)
            self.deposit_rects.append(rect)

        self.save_game_state('initial_game.pkl')

    def clear_pygame_surfaces(self, obj, seen=None):
        """Recursively clear pygame Surface objects from game objects."""
        if seen is None:
            seen = set()
        if obj is None:
            return
        obj_id = id(obj)
        if obj_id in seen:
            return
        seen.add(obj_id)

        if isinstance(obj, pygame.Surface):
            return None

        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, pygame.Surface):
                    obj[key] = None
                else:
                    self.clear_pygame_surfaces(value, seen)
            return

        if isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, pygame.Surface):
                    obj[i] = None
                else:
                    self.clear_pygame_surfaces(item, seen)
            return

        if isinstance(obj, tuple):
            for item in obj:
                self.clear_pygame_surfaces(item, seen)
            return

        if isinstance(obj, set):
            for item in list(obj):
                self.clear_pygame_surfaces(item, seen)
            return

        if hasattr(obj, '__dict__'):
            for key, value in obj.__dict__.items():
                if isinstance(value, pygame.Surface):
                    obj.__dict__[key] = None
                else:
                    self.clear_pygame_surfaces(value, seen)
            return

        if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
            try:
                for item in obj:
                    self.clear_pygame_surfaces(item, seen)
            except TypeError:
                pass

    def reload_sprites(self):
        """Reload all pygame Surface objects for cards and nobles"""
        # Reload card sprites
        for level_num in [1, 2, 3]:
            level_deck = getattr(self, f'level{level_num}')
            if level_deck:
                for card in level_deck.cards:
                    self.executor.submit(card.load)
        
        # Reload board card sprites
        for level in [1, 2, 3]:
            if level in self.board:
                for card in self.board[level]:
                    self.executor.submit(card.load)
        
        # Reload player deposit card sprites
        for player in self.players:
            for card in player.deposit_card:
                self.executor.submit(card.load)
        
        # Reload noble sprites
        if self.nobles:
            for noble in self.nobles.nobles:
                self.executor.submit(noble.load)
        
        for noble in self.shown_nobles:
            self.executor.submit(noble.load)

    def get_game_state_dict(self):
        """Get all game state data for saving"""
        return {
            'current_player': self.current_player,
            'num_player': self.num_player,
            'players': self.players,
            'board': self.board,
            'bank': self.bank,
            'nobles': self.nobles,
            'shown_nobles': self.shown_nobles,
            'level1': self.level1,
            'level2': self.level2,
            'level3': self.level3,
            'choosing_card': self.choosing_card,
            'choosing_cost': self.choosing_cost,
            'choosing_gems': self.choosing_gems,
            'choosing_nobles': self.choosing_nobles,
            'show_noble_overlay': self.show_noble_overlay,
            'current_action': self.current_action,
            'selected_gems': self.selected_gems,
            'selected_gem': self.selected_gem,
        }

    def build_serializable_state(self):
        state = self.get_game_state_dict()
        for obj in state.values():
            if isinstance(obj, list):
                for item in obj:
                    self.clear_pygame_surfaces(item)
            else:
                self.clear_pygame_surfaces(obj)
        # Detach the snapshot from the live game objects before sprites are reloaded.
        return pickle.loads(pickle.dumps(state))

    def wait_for_sprite_reload(self):
        if self.nobles:
            for noble in self.nobles.nobles:
                while noble.image is None:
                    time.sleep(0.01)

    def apply_loaded_state(self, state):
        self.current_player = state['current_player']
        self.num_player = state['num_player']
        self.players = state['players']
        self.board = state['board']
        self.bank = state['bank']
        self.nobles = state['nobles']
        self.shown_nobles = state['shown_nobles']
        self.level1 = state['level1']
        self.level2 = state['level2']
        self.level3 = state['level3']
        self.choosing_card = state['choosing_card']
        self.choosing_cost = state['choosing_cost']
        self.choosing_gems = state['choosing_gems']
        self.choosing_nobles = state['choosing_nobles']
        self.show_noble_overlay = state['show_noble_overlay']
        self.current_action = state['current_action']
        self.selected_gems = state['selected_gems']
        self.selected_gem = state['selected_gem']

        self.reload_sprites()
        self.wait_for_sprite_reload()

    def save_initial_state(self):
        """Save the initial game state for easy reset"""
        state = self.build_serializable_state()
        filepath = os.path.join(self.save_dir, 'initial_game.pkl')
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
        print(f"Initial game state saved to {filepath}")
        # Reload sprites after saving so game can continue displaying
        self.reload_sprites()
        self.wait_for_sprite_reload()

    def save_game_state(self, filename='current_game.pkl'):
        """Save current game state"""
        state = self.build_serializable_state()
        filepath = os.path.join(self.save_dir, filename)
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
        # Reload sprites after saving so game can continue displaying
        self.reload_sprites()

    def load_game_state(self, filename='initial_game.pkl'):
        """Load a saved game state"""
        filepath = os.path.join(self.save_dir, filename)
        if not os.path.exists(filepath):
            print(f"Save file {filepath} not found")
            return False
        try:
            with open(filepath, 'rb') as f:
                state = pickle.load(f)
            self.apply_loaded_state(state)
            print(f"Game state loaded from {filepath}")
            return True
        except Exception as e:
            print(f"Error loading game state: {e}")
            return False

    def play(self):
        while self.running:
            self.handle_input()
            self.process_network_actions()
            if not self.game_over:
                self.handle_bot()
            self.draw()
            self.update()
            self.clock.tick(FPS)
        
        pygame.quit()

    def is_client_turn(self):
        if not self.is_client or not self.client:
            return True
        return getattr(self.client, 'player_index', None) == self.current_player

    def get_local_player_index(self):
        if self.is_client and self.client:
            player_index = getattr(self.client, 'player_index', None)
            if player_index is not None and 0 <= player_index < len(self.players):
                return player_index
        if self.is_host and self.players:
            return 0
        return self.current_player

    def is_multiplayer_session(self):
        return self.is_host or self.is_client

    def is_local_human_turn(self):
        if self.is_client:
            return self.is_client_turn()
        if self.is_host:
            return self.current_player == 0
        return True

    def ensure_card_image(self, card):
        if card is None:
            return None
        if card.image is None and hasattr(card, "load"):
            card.load()
        return card.image

    def draw(self):
        # 1. Clear screen & Background
        self.screen.fill((30, 30, 30))

        if self.menu.in_menu or not self.start:
            self.menu.draw(self.screen)
            pygame.display.flip()
            return

        main_width = int(WINDOW_RESOLUTION[0] * 0.75)
        main_height = WINDOW_RESOLUTION[1]

        main_rect = pygame.Rect(0, 0, main_width, main_height)
        pygame.draw.rect(self.screen, (0, 200, 200), main_rect)

        # 2. Draw NOBLES
        noble_rect = pygame.Rect(START_X , 20, CARD_W, CARD_W) 
        pygame.draw.rect(self.screen, (100, 100, 100), noble_rect)
        for i, noble in enumerate(self.shown_nobles):
            if i < len(self.noble_rects):
                rect = self.noble_rects[i]
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
                noble.draw(self.screen, rect.topleft)

        # 3. Draw cards on BOARD 
        for level_idx in range(3): # level 0, 1, 2 tương ứng level 1, 2, 3
            level = level_idx + 1
            # Vẽ Deck placeholder (Nếu bạn muốn lưu deck_rect riêng cũng được, ở đây dùng tạm logic cũ)
            row_y = 150 + (3 - level) * (CARD_H + GAP)
            pygame.draw.rect(self.screen, (100, 100, 100), (START_X, row_y, CARD_W, CARD_H))
            
            if level in self.board:
                for i, card in enumerate(self.board[level]):
                    if i < len(self.card_rects[level_idx]):
                        rect = self.card_rects[level_idx][i]
                        
                        # Vẽ khung nền dựa trên màu lá bài
                        color_map = {"Black": (0,0,0), "Blue": (0,0,255), "Red": (255,0,0), "Green": (0,255,0), "White": (255,255,255)}
                        bg_color = color_map.get(card.color, (200, 200, 200))
                        
                        pygame.draw.rect(self.screen, bg_color, rect)
                        pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
                        
                        if card.image:
                            card.draw(self.screen, rect.topleft)
                        
                        if self.choosing_card and card.is_same_card(self.choosing_card):
                            pygame.draw.rect(self.screen, (255, 255, 0), rect, 4)

        # 4. Draw BANK GEMS (Sử dụng self.gems_rect)
        for i, gem_img in enumerate(self.gems):
            rect = self.gems_rect[i]
            # Vẽ hình ảnh viên đá
            scaled_gem = pygame.transform.smoothscale(gem_img, (GEM_SIZE, GEM_SIZE))
            self.screen.blit(scaled_gem, rect.topleft)
            
            if self.bank:
                count = self.bank.gem[i]
                count_txt = self.font.render(str(count), True, (255, 255, 255))
                # Căn số lượng vào góc dưới bên phải của rect
                txt_rect = count_txt.get_rect(bottomright=(rect.right - 5, rect.bottom - 5))
                self.screen.blit(count_txt, txt_rect)
            if i < len(self.choosing_gems) and self.choosing_gems[i] > 0:
                # Vẽ số lượng dự tính lấy màu xanh lá
                select_txt = self.font.render(f"{self.choosing_gems[i]}", True, (0, 255, 0))
                self.screen.blit(select_txt, (rect.x + 5, rect.y + 5))

            if i in self.selected_gems or i == self.selected_gem:
                pygame.draw.rect(self.screen, (255, 255, 0), rect, 3)

        # 5. Draw ACTION BOX & PLAYER RESOURCES (Sử dụng self.cost_rects)
        action_rect = pygame.Rect(0, main_height - ACTION_ZONE_H, main_width, ACTION_ZONE_H)
        pygame.draw.rect(self.screen, (40, 40, 40), action_rect)
        pygame.draw.rect(self.screen, (0, 255, 200), action_rect, 3)

        display_player_index = self.get_local_player_index()
        current_p = self.players[display_player_index]
        gem_to_key = {"Onyx": "black", "Sapphire": "blue", "Emerald": "green", "Ruby": "red", "Diamond": "white", "Gold": "gold"}
        score_txt = self.font.render(f"YOUR SCORE: {current_p.point}", True, (255, 255, 0))
        self.screen.blit(score_txt, (20, action_rect.y + 5))
        for i, gem_name in enumerate(GEMS_INDEX):
            rect = self.cost_rects[i]
            # Vẽ hình ảnh viên đá nhỏ trong túi player
            scaled_img = pygame.transform.smoothscale(self.gems[i], (GEM_DISPLAY_SIZE, GEM_DISPLAY_SIZE))
            self.screen.blit(scaled_img, rect.topleft)
            
            key = gem_to_key[gem_name]
            # Vẽ số lượng Gems đang có (temp)
            count_surf = self.font.render(f"x{current_p.temp.get(key, 0)}", True, (255, 255, 255))
            self.screen.blit(count_surf, (rect.right + 8, rect.top + 2))
            
            # Vẽ số lượng Card vĩnh viễn (perm)
            if key != "gold":
                perm_count = current_p.perm.get(key, 0)
                perm_surf = self.font.render(f"+{perm_count}", True, (0, 255, 100))
                self.screen.blit(perm_surf, (rect.right + 8, rect.top + 22))
            if i < len(self.choosing_cost) and self.choosing_cost[i] > 0:
                cost_txt = self.font.render(f"{self.choosing_cost[i]}", True, (0, 255, 0))
                # Vẽ đè ngay trung tâm icon gem của player
                self.screen.blit(cost_txt, (rect.x + 5, rect.y + 5))
            
        # Draw deposit cards
        for index, card in enumerate(current_p.deposit_card):
            image = self.ensure_card_image(card)
            if image is None:
                pygame.draw.rect(self.screen, (80, 80, 80), self.deposit_rects[index])
                pygame.draw.rect(self.screen, (255, 255, 255), self.deposit_rects[index], 2)
                continue
            self.screen.blit(image, self.deposit_rects[index])
            if self.choosing_card and card.is_same_card(self.choosing_card):
                pygame.draw.rect(self.screen, (255, 255, 0), self.deposit_rects[index], 4)

        # 6. Draw ACTION BUTTONS (Sử dụng self.action_button_rects)
        actions_labels = ["TAKE 3", "TAKE 2", "RESERVE", "BUY"]
        for i, label in enumerate(actions_labels):
            rect = self.action_button_rects[i]
            # Vẽ nút
            if self.current_action == label:
                color = (0, 150, 200)
            else:
                color = (60, 60, 60)

            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
            
            # Vẽ text
            txt_surf = self.font.render(label, True, (255, 255, 255))
            self.screen.blit(txt_surf, txt_surf.get_rect(center=rect.center))

        # Draw CONFIRM BUTTON
        if self.current_action:
            confirm_rect = pygame.Rect(self.bank_rect.right - 100, self.bank_rect.bottom , 120, 50)
            self.confirm_rect = confirm_rect

            valid = self.can_confirm()
            color = (0, 200, 0) if valid else (80, 80, 80)

            pygame.draw.rect(self.screen, color, confirm_rect)
            pygame.draw.rect(self.screen, (255,255,255), confirm_rect, 2)

            txt = self.font.render("CONFIRM", True, (255,255,255))
            self.screen.blit(txt, txt.get_rect(center=confirm_rect.center))

        # 7. Draw SIDE BAR
        side_width = WINDOW_RESOLUTION[0] - main_width
        side_height = WINDOW_RESOLUTION[1] // 3
        for i in range(3):
            s_rect = pygame.Rect(main_width, i * side_height, side_width, side_height)
            pygame.draw.rect(self.screen, (150, 150, 150), s_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), s_rect, 2)

        others = [ (idx, p) for idx, p in enumerate(self.players) if idx != display_player_index ]
        
        for i, (idx, p_other) in enumerate(others):
            # Vẽ từng ô từ trên xuống dưới
            s_rect = pygame.Rect(main_width, i * side_height, side_width, side_height)
            pygame.draw.rect(self.screen, (60, 60, 60), s_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), s_rect, 2)
            
            # Tên và điểm đối thủ
            name_txt = self.font.render(f"PLAYER {idx + 1}", True, (255, 255, 255))
            p_score_txt = self.font.render(f"Score: {p_other.point}", True, (255, 255, 0))
            self.screen.blit(name_txt, (s_rect.x + 10, s_rect.y + 10))
            self.screen.blit(p_score_txt, (s_rect.x + 10, s_rect.y + 30))

            # Vẽ tài nguyên tóm tắt của đối thủ
            for g_idx, g_name in enumerate(GEMS_INDEX):
                key = gem_to_key[g_name]

                # small icon
                gx = s_rect.x + 10 + (g_idx % 2) * (side_width // 2)
                gy = s_rect.y + 60 + (g_idx // 2) * 25

                small_gem = pygame.transform.smoothscale(self.gems[g_idx], (20, 20))
                self.screen.blit(small_gem, (gx, gy))

                # temp count
                temp_count = p_other.temp.get(key, 0)
                temp_txt = self.font.render(f"x{temp_count}", True, (255, 255, 255))
                temp_rect = temp_txt.get_rect(midleft=(gx + 25, gy + 10))
                self.screen.blit(temp_txt, temp_rect)

                # perm count (skip gold)
                if key != "gold":
                    perm_count = p_other.perm.get(key, 0)
                    perm_txt = self.font.render(f"+{perm_count}", True, (0, 255, 100))
                    # place right next to temp count
                    perm_rect = perm_txt.get_rect(midleft=(temp_rect.right + 10, temp_rect.centery))
                    self.screen.blit(perm_txt, perm_rect)

            # Draw reserved cards for opponent (scaled smaller)
            if p_other.deposit_card:
                # Calculate card size - make them smaller to fit
                small_card_w = int(CARD_W * 0.4)  # 40% of normal size
                small_card_h = int(CARD_H * 0.4)
                card_gap = 5
                
                # Position cards starting from below the gem info (moved lower to avoid overlap)
                start_x = s_rect.x + 10
                start_y = s_rect.y + 140  # Below the gem display area
                
                for card_idx, card in enumerate(p_other.deposit_card):
                    image = self.ensure_card_image(card)
                    if image:
                        # Scale down the card image
                        scaled_card = pygame.transform.smoothscale(image, (small_card_w, small_card_h))
                        card_x = start_x + card_idx * (small_card_w + card_gap)
                        card_y = start_y
                        
                        # Only draw if it fits in the sidebar width
                        if card_x + small_card_w <= s_rect.right - 10:
                            self.screen.blit(scaled_card, (card_x, card_y))

        # Draw noble overlay if needed
        if self.show_noble_overlay:
            # Dark overlay
            overlay = pygame.Surface(WINDOW_RESOLUTION)
            overlay.set_alpha(180)
            overlay.fill((0, 0, 0))
            self.screen.blit(overlay, (0, 0))
            
            # Draw choosing nobles
            title = self.font.render("Choose a Noble", True, (255, 255, 255))
            self.screen.blit(title, (WINDOW_RESOLUTION[0] // 2 - title.get_width() // 2, 100))
            
            for i, noble in enumerate(self.choosing_nobles):
                x = WINDOW_RESOLUTION[0] // 2 - len(self.choosing_nobles) * (CARD_W + 10) // 2 + i * (CARD_W + 10)
                y = 150
                rect = pygame.Rect(x, y, CARD_W, CARD_W)
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
                noble.draw(self.screen, (x, y))

        if self.bot_thinking:
            # Semi-transparent overlay
            overlay = pygame.Surface(WINDOW_RESOLUTION, pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 128))  # Semi-transparent black
            self.screen.blit(overlay, (0, 0))
            
            # Text
            thinking_text = self.font.render("Bot is Thinking...", True, (255, 255, 255))
            text_rect = thinking_text.get_rect(center=(WINDOW_RESOLUTION[0] // 2, WINDOW_RESOLUTION[1] // 2))
            self.screen.blit(thinking_text, text_rect)

        if (self.is_client or self.is_host) and not self.is_local_human_turn() and not self.game_over:
            overlay = pygame.Surface(WINDOW_RESOLUTION, pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            self.screen.blit(overlay, (0, 0))

            waiting_text = self.font.render("Opponent is making move.", True, (255, 255, 255))
            waiting_rect = waiting_text.get_rect(center=(WINDOW_RESOLUTION[0] // 2, WINDOW_RESOLUTION[1] // 2))
            self.screen.blit(waiting_text, waiting_rect)

        if self.game_over:
            # Semi-transparent overlay
            overlay = pygame.Surface(WINDOW_RESOLUTION, pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))  # More opaque for game over
            self.screen.blit(overlay, (0, 0))
            
            # Winner text - handle multiline
            lines = self.winner_text.split('\n')
            y_offset = WINDOW_RESOLUTION[1] // 2 - (len(lines) - 1) * 15  # Center vertically
            for line in lines:
                if line.strip():  # Skip empty lines
                    text_surf = self.font.render(line, True, (255, 255, 0))
                    text_rect = text_surf.get_rect(center=(WINDOW_RESOLUTION[0] // 2, y_offset))
                    self.screen.blit(text_surf, text_rect)
                    y_offset += 30  # Line spacing

        self.menu.draw(self.screen)
        pygame.display.flip()

    def update(self):
        # Reset flags at the start of each frame
        self.noble_chosen_this_frame = False
        
        self.card_rects = [[], [], []]
        for level in [1, 2, 3]:
            row_y = 150 + (3 - level) * (CARD_H + GAP)
            for i, card in enumerate(self.board[level]):
                card_x = START_X + (i + 1) * (CARD_W + GAP)
                rect = pygame.Rect(card_x, row_y, CARD_W, CARD_H)
                self.card_rects[level-1].append(rect)
        if self.menu.in_menu:
            self.menu.update()
            return
        if not self.is_client:
            self.fill_board_slots()

        # move chosen deposit to last to blit
        cur = self.players[self.current_player]
        for index, card in enumerate(cur.deposit_card):
            if card.is_same_card(self.choosing_card) and index != len(cur.deposit_card) - 1:
                chosen = cur.deposit_card.pop(index)
                cur.deposit_card.append(chosen)

    def handle_bot(self):
        if self.is_client:
            return
        player = self.players[self.current_player]
        if isinstance(player, RandomBot):
            def bot_action():
                action = player.get_action(self.board[1] + self.board[2] + self.board[3], self.bank, self.players, self.shown_nobles)
                self.current_action = action
                print(f"BOT MOVE: {self.current_action}")
                self.execute_action()
                # self.next_turn()
                self.bot_thinking = False
            
            if not self.bot_thinking:
                self.bot_thinking = True
                threading.Thread(target=bot_action).start()

    def handle_input(self):
        for event in pygame.event.get():
            if self.menu.in_menu:
                self.menu.has_saved_game = (
                    not self.is_multiplayer_session()
                    and os.path.exists(os.path.join(self.save_dir, 'current_game.pkl'))
                )
                if self.menu.handle_input(event):
                    if self.menu.selected_option == "Continue":
                        # Only load saved game if in main menu (state == 0)
                        # If in pause menu (state == 1), just resume
                        if (
                            not self.is_multiplayer_session()
                            and self.menu.state == 0
                            and os.path.exists(os.path.join(self.save_dir, 'current_game.pkl'))
                        ):
                            self.load_game_state('current_game.pkl')
                            self.initialized = True
                        self.menu.selected_option = None
                    elif self.menu.selected_option == "Start Game (PvE)":
                        if not self.initialized:
                            self.init_players(num_players = self.menu.current_num_players)
                            self.initialized = True
                        self.menu.selected_option = None
                    elif self.menu.selected_option == "Host":
                        self.start_server()
                        # Go to waiting state instead of starting game immediately
                        self.menu.waiting_for_players = True
                        self.menu.waiting_is_host = True
                        self.menu.hosting = False
                        self.menu.connected_players = 1  # Host counts as 1 player
                        self.menu.selected_option = None
                    elif self.menu.selected_option == "Start Multiplayer Game":
                        if not self.initialized:
                            self.init_game(num_player = self.menu.current_num_players)
                            self.configure_multiplayer_players()
                            self.initialized = True

                        # Start the multiplayer session now. Fill missing slots with chosen bots.
                        if self.server:
                            self.server.send_initial_state(self.build_initial_state())
                        self.menu.waiting_for_players = False
                        self.menu.in_menu = False
                        self.menu.hosting = False
                        self.menu.selected_option = None
                    elif self.menu.selected_option == "Quit Hosting":
                        # Stop the server and return to main menu
                        if hasattr(self, 'server') and self.server:
                            self.server.stop()
                            self.server = None
                        self.is_host = False
                        self.menu.waiting_for_players = False
                        self.menu.waiting_is_host = True
                        self.menu.in_menu = True
                        self.menu.state = 0
                        self.menu.selected_option = None
                    elif self.menu.selected_option == "Leave Waiting Room":
                        if self.client:
                            self.client.disconnect()
                            self.client = None
                        self.is_client = False
                        self.menu.waiting_for_players = False
                        self.menu.waiting_is_host = True
                        self.menu.in_menu = True
                        self.menu.state = 0
                        self.menu.selected_option = None
                    elif self.menu.selected_option == "Join":
                        # Get the selected server address from menu
                        if self.menu.selected_server:
                            if not self.join_server(self.menu.selected_server):
                                print("Failed to join server")
                        self.menu.selected_option = None
                    elif self.menu.selected_option == "Refresh Rooms":
                        self.refresh_available_rooms()
                        self.menu.selected_option = None
                    elif self.menu.selected_option == "Main Menu":
                        self.initialized = False
                        if not self.is_multiplayer_session():
                            self.save_game_state('current_game.pkl')
                        self.menu.selected_option = None
                    self.start = True
                continue
            if event.type == pygame.QUIT:
                if not self.is_multiplayer_session():
                    self.save_game_state('current_game.pkl')
                self.running = False
                return
            if self.game_over:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        self.restart_game()
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
                return
            if self.bot_thinking:
                return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.menu.in_menu = True
                    continue

            player = self.players[self.current_player]
            if (self.is_client or self.is_host) and not self.is_local_human_turn():
                continue
            if isinstance(player, RandomBot):
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                
                # ===== NOBLE OVERLAY =====
                if self.show_noble_overlay:
                    for i, noble in enumerate(self.choosing_nobles):
                        x = WINDOW_RESOLUTION[0] // 2 - len(self.choosing_nobles) * (CARD_W + 10) // 2 + i * (CARD_W + 10)
                        y = 150
                        rect = pygame.Rect(x, y, CARD_W, CARD_W)
                        if rect.collidepoint(pos):
                            # Choose this noble
                            cur = self.players[self.current_player]
                            cur.add_noble(noble)
                            self.shown_nobles.remove(noble)
                            # Draw a new noble if available
                            # new_noble = self.nobles.draw()
                            # if new_noble:
                            #     self.shown_nobles.append(new_noble)
                            self.choosing_nobles = []
                            self.show_noble_overlay = False
                            self.noble_chosen_this_frame = True  # Prevent re-checking nobles this frame
                            # End the turn after choosing a noble
                            self.next_turn()
                            self.broadcast_multiplayer_state()
                            # reset everything
                            self.current_action = None
                            self.selected_gems = []
                            self.selected_gem = None
                            self.choosing_card = None
                            return
                
                # ===== CLICK ACTION BUTTON =====
                for i, rect in enumerate(self.action_button_rects):
                    if rect.collidepoint(pos):
                        actions = ["TAKE 3", "TAKE 2", "RESERVE", "BUY"]
                        action = actions[i]

                        # toggle behavior
                        if self.current_action == action:
                            self.current_action = None
                        else:
                            self.current_action = action

                        # reset selections
                        self.selected_gems = []
                        self.selected_gem = None
                        self.choosing_card = None
                        return
                    
                # ===== CLICK CARD =====        
                if self.board_rect.collidepoint(pos):
                    for level_idx in range(3):
                        for i, rect in enumerate(self.card_rects[level_idx]):
                            if rect.collidepoint(pos):
                                if i < len(self.board[level_idx + 1]):
                                    card = self.board[level_idx + 1][i]

                                    if self.current_action in ["BUY", "RESERVE"]:
                                        if self.choosing_card and card.is_same_card(self.choosing_card):
                                            self.choosing_card = None
                                        else:
                                            self.choosing_card = card
                                return
                            
                # ===== CLICK DEPOSIT ======
                for index, card in enumerate(player.deposit_card):
                    if self.deposit_rects[index].collidepoint(pos):
                        if self.current_action == "BUY":
                            if self.choosing_card and card.is_same_card(self.choosing_card):
                                self.choosing_card = None
                            else:
                                self.choosing_card = card
                            
                # ===== CLICK BANK =====
                if self.bank_rect.collidepoint(pos):
                    for i, rect in enumerate(self.gems_rect):
                        if rect.collidepoint(pos):

                            # TAKE 3 (select up to 3 different)
                            if self.current_action == "TAKE 3":
                                if i == 5:
                                    return  # ignore gold
                                if i in self.selected_gems:
                                    self.selected_gems.remove(i)
                                elif len(self.selected_gems) < 3:
                                    self.selected_gems.append(i)

                            # TAKE 2 (only 1 type)
                            elif self.current_action == "TAKE 2":
                                if self.selected_gem == i:
                                    self.selected_gem = None
                                else:
                                    self.selected_gem = i

                            return
                        
                # ===== CONFIRM =====
                if self.current_action and hasattr(self, "confirm_rect") and self.confirm_rect.collidepoint(pos):
                    if self.can_confirm():
                        if self.is_client:
                            self.submit_client_action()
                        else:
                            self.execute_action()
                        # self.next_turn()

    def next_turn(self):
        old_player = self.current_player
        self.current_player = (self.current_player + 1) % len(self.players)
        if old_player == len(self.players) - 1 and self.current_player == 0:
            self.check_end_game()
        self.choosing_card = None
        self.choosing_cost = [0,0,0,0,0,0]
        self.choosing_gems = [0,0,0,0,0]

    def check_end_game(self):
        max_points = max(p.point for p in self.players)
        if max_points >= 15:
            winners = [f"Player {i+1}" for i, p in enumerate(self.players) if p.point == max_points]
            self.winner_text = f"Game Over! Winner(s): {', '.join(winners)}\n\nPress ENTER for new game\nPress ESC to quit"
            self.game_over = True
            current_path = os.path.join(self.save_dir, 'current_game.pkl')
            if os.path.exists(current_path):
                os.remove(current_path)


    def restart_game(self):
        self.game_over = False
        self.winner_text = ""
        self.bot_thinking = False
        self.current_player = 0
        self.choosing_card = None
        self.choosing_cost = [0,0,0,0,0,0]
        self.choosing_gems = [0,0,0,0,0]
        self.selected_gems = []
        self.selected_gem = None
        self.current_action = None
        self.show_noble_overlay = False
        self.choosing_nobles = []
        self.noble_chosen_this_frame = False
        self.load_game_state('initial_game.pkl')

    def can_confirm(self):
        player = self.players[self.current_player]
        total = sum(player.temp.values())

        # BUY
        if self.current_action == "BUY":
            if not self.choosing_card:
                return False

            cost = card_cost_to_dict(self.choosing_card)
            total_gold = player.temp["gold"]
            for color, amount in cost.items():
                available = player.temp[color] + player.perm.get(color, 0)
                if available >= amount:
                    continue
                needed = amount - available
                if total_gold >= needed:
                    total_gold -= needed
                else:
                    return False
            return True

        # RESERVE
        if self.current_action == "RESERVE":
            return self.choosing_card is not None and len(player.deposit_card) < 3

        # TAKE 3
        if self.current_action == "TAKE 3":
            if total + len(self.selected_gems) > 10:
                return False
            return self.bank.can_take_3(self.selected_gems)

        # TAKE 2
        if self.current_action == "TAKE 2":
            if total + 2 > 10:
                return False
            return self.selected_gem is not None and self.bank.can_take_2(self.selected_gem)

        return False
    
    def remove_card_from_board(self, target):
        for level in [1,2,3]:
            for i, card in enumerate(self.board[level]):
                if card.is_same_card(target):
                    self.board[level].pop(i)
                    return

    def fill_board_slots(self):
        for level in [1, 2, 3]:
            while len(self.board[level]) < 4:
                card = getattr(self, f"level{level}").draw()
                if card:
                    self.board[level].append(card)
                else:
                    break
                   
    def execute_action(self):
        player = self.players[self.current_player]
        if not isinstance(player, RandomBot):
            # ===== BUY =====
            if self.current_action == "BUY":
                cost = card_cost_to_dict(self.choosing_card)

                payment = player.purchase(cost, self.choosing_card)
                if payment:
                    self.bank.pay(payment)
                    # ADD PERMANENT BONUS
                    color_map = {
                        "Black": "black",
                        "Blue": "blue",
                        "Green": "green",
                        "Red": "red",
                        "White": "white"
                    }

                    bonus_color = color_map.get(self.choosing_card.color)
                    if bonus_color:
                        player.perm[bonus_color] = player.perm.get(bonus_color, 0) + 1

                    self.remove_card_from_board(self.choosing_card)
            # ===== RESERVE =====
            elif self.current_action == "RESERVE":
                if len(player.deposit_card) < 3:
                    player.deposit(self.choosing_card)
                    self.remove_card_from_board(self.choosing_card)

                    # take gold if available and temp < 10
                    if sum(player.temp.values()) + 1 <= 10 and self.bank.can_book():
                        self.bank.gem[5] -= 1
                        player.temp["gold"] += 1
                        
            # ===== TAKE 3 =====
            elif self.current_action == "TAKE 3":
                if self.bank.get_3(self.selected_gems):
                    keys = ["black","blue","green","red","white"]
                    for i in self.selected_gems:
                        player.temp[keys[i]] += 1

            # ===== TAKE 2 =====
            elif self.current_action == "TAKE 2":
                if self.bank.get_2(self.selected_gem):
                    keys = ["black","blue","green","red","white"]
                    player.temp[keys[self.selected_gem]] += 2
        else:
            if self.current_action == "BUY":
                cost = card_cost_to_dict(player.choosing_card)

                payment = player.purchase(cost, player.choosing_card)
                if payment:
                    self.bank.pay(payment)
                    # ADD PERMANENT BONUS
                    color_map = {
                        "Black": "black",
                        "Blue": "blue",
                        "Green": "green",
                        "Red": "red",
                        "White": "white"
                    }

                    bonus_color = color_map.get(player.choosing_card.color)
                    if bonus_color:
                        player.perm[bonus_color] = player.perm.get(bonus_color, 0) + 1

                    self.remove_card_from_board(player.choosing_card)
            # ===== RESERVE =====
            elif self.current_action == "RESERVE":
                if len(player.deposit_card) < 3:
                    player.deposit(player.choosing_card)
                    self.remove_card_from_board(player.choosing_card)

                    # take gold if available and temp < 10
                    if sum(player.temp.values()) + 1 <= 10 and self.bank.can_book():
                        self.bank.gem[5] -= 1
                        player.temp["gold"] += 1

            # ===== TAKE 3 =====
            elif self.current_action == "TAKE 3":
                if self.bank.get_3(player.selected_gems):
                    keys = ["black","blue","green","red","white"]
                    for i in player.selected_gems:
                        player.temp[keys[i]] += 1

            # ===== TAKE 2 =====
            elif self.current_action == "TAKE 2":
                if self.bank.get_2(player.selected_gems):
                    keys = ["black","blue","green","red","white"]
                    player.temp[keys[player.selected_gems]] += 2

        # The host/offline game must draw replacement board cards immediately.
        # Clients should only ever receive those cards from the host.
        if not self.is_client:
            self.fill_board_slots()

        # reset everything
        self.current_action = None
        self.selected_gems = []
        self.selected_gem = None
        self.choosing_card = None
        # ---- check for and perform noble logic at the end of the turn
        # Check for noble availability after action completion
        cur = self.players[self.current_player]
        keys = ["black", "blue", "green", "red", "white"]
        perm_gems = [cur.perm.get(item) for item in keys]
        available_nobles = [noble for noble in self.shown_nobles if noble.can_get(perm_gems)]
        
        if isinstance(cur, RandomBot):
            # RandomBot: automatically choose a random noble if available
            chosen_noble = cur.check_and_choose_noble(self.shown_nobles)
            if chosen_noble:
                cur.add_noble(chosen_noble)
                self.shown_nobles.remove(chosen_noble)
                # Draw a new noble if available
                # new_noble = self.nobles.draw()
                # if new_noble:
                #     self.shown_nobles.append(new_noble)
        elif self.is_host or self.is_client:
            if available_nobles:
                cur.add_noble(available_nobles[0])
                self.shown_nobles.remove(available_nobles[0])
        else:
            # Human players: show overlay if multiple nobles available
            if len(available_nobles) > 1:
                self.choosing_nobles = available_nobles
                self.show_noble_overlay = True
                # Don't end turn yet - wait for noble choice
                return
            elif len(available_nobles) == 1:
                # Automatically take the noble
                cur.add_noble(available_nobles[0])
                self.shown_nobles.remove(available_nobles[0])
                # Draw a new noble if available
                # new_noble = self.nobles.draw()
                # if new_noble:
                #     self.shown_nobles.append(new_noble)

        # ===== END TURN =====
        self.next_turn()
        self.broadcast_multiplayer_state()

    def start_server(self):
        """Start the game server for hosting multiplayer games"""
        from server import GameServer
        self.is_host = True
        self.is_client = False
        
        # Callback to update connected players count in menu
        def update_player_count(count):
            self.menu.connected_players = count

        def handle_remote_action(player_index, payload):
            return self.handle_network_action(player_index, payload)
        
        self.server = GameServer(
            port=DEFAULT_ROOM_PORT,
            player_count_callback=update_player_count,
            room_name=self.menu.host_room_name or "Unnamed",
            max_players=self.menu.current_num_players,
            action_callback=handle_remote_action,
            directory_host=ROOM_DIRECTORY_HOST,
            directory_port=ROOM_DIRECTORY_PORT,
        )
        # Start server in a separate thread
        import threading
        server_thread = threading.Thread(target=self.server.start)
        server_thread.daemon = True
        server_thread.start()
        print("Server started")
        self.refresh_available_rooms()

    def join_server(self, server_addr):
        """Connect to a multiplayer game server"""
        from client import GameClient
        self.is_client = True
        self.is_host = False
        ip, port = server_addr.split(':')
        port = int(port)
        self.client = GameClient(
            ip,
            port,
            room_name=self.menu.host_room_name,
            state_callback=self.handle_initial_state,
            room_status_callback=self.handle_room_status,
        )
        if self.client.connect():
            if self.client.target_num_players is not None:
                self.menu.current_num_players = self.client.target_num_players
            self.menu.connected_players = self.client.connected_players
            self.menu.host_room_name = self.client.room_name or self.menu.host_room_name
            self.menu.waiting_for_players = True
            self.menu.waiting_is_host = False
            self.menu.in_menu = True
            print("Connected to server")
            return True
        else:
            print("Failed to connect to server")
            return False

    def refresh_available_rooms(self):
        from client import fetch_available_rooms

        self.menu.available_servers = fetch_available_rooms(ROOM_DIRECTORY_HOST, ROOM_DIRECTORY_PORT)

    def handle_room_status(self, status):
        self.menu.connected_players = status.get("connected_players", self.menu.connected_players)
        self.menu.current_num_players = status.get("num_players", self.menu.current_num_players)
        self.menu.host_room_name = status.get("room_name", self.menu.host_room_name)

    def handle_initial_state(self, sync_mode, state):
        if sync_mode == "initial":
            self.apply_initial_state(state)
        else:
            self.apply_state_update(state)

    def apply_initial_state(self, state):
        self.num_player = state.get('num_player', state.get('num_players', self.menu.current_num_players))
        if not self.initialized:
            self.init_game(num_player=self.num_player)
        self.apply_loaded_state(state)
        self.menu.current_num_players = self.num_player
        self.menu.host_room_name = self.client.room_name or self.menu.host_room_name

        self.initialized = True
        self.start = True
        self.menu.in_menu = False
        self.menu.waiting_for_players = False
        self.menu.waiting_is_host = False

    def card_key(self, card):
        if card is None:
            return None
        if getattr(card, "dir", None):
            return card.dir
        return (
            card.level,
            card.color,
            card.points,
            tuple(card.resources),
        )

    def build_card_lookup(self):
        lookup = {}

        def register(card):
            if card is None:
                return
            lookup[self.card_key(card)] = card

        for level in [1, 2, 3]:
            deck = getattr(self, f"level{level}", None)
            if deck:
                for card in deck.cards:
                    register(card)
            for card in self.board.get(level, []):
                register(card)

        if self.nobles:
            for noble in self.nobles.nobles:
                register(noble)
        for noble in self.shown_nobles:
            register(noble)

        for player in self.players:
            for card in player.cards:
                register(card)
            for card in player.deposit_card:
                register(card)
            for noble in player.noble:
                register(noble)

        return lookup

    def resolve_card_keys(self, keys, lookup):
        cards = []
        for key in keys:
            card = lookup.get(key)
            if card is not None:
                cards.append(card)
        return cards

    def build_player_sync(self):
        return [
            {
                "point": player.point,
                "temp": player.temp.copy(),
                "perm": player.perm.copy(),
                "cards": [self.card_key(card) for card in player.cards],
                "deposit_card": [self.card_key(card) for card in player.deposit_card],
                "noble": [self.card_key(card) for card in player.noble],
            }
            for player in self.players
        ]

    def build_state_update(self):
        return {
            "num_player": self.num_player,
            "current_player": self.current_player,
            "room_name": self.menu.host_room_name or "Unnamed",
            "bank_gem": list(self.bank.gem),
            "board": {
                level: [self.card_key(card) for card in self.board[level]]
                for level in [1, 2, 3]
            },
            "level_decks": {
                1: [self.card_key(card) for card in self.level1.cards],
                2: [self.card_key(card) for card in self.level2.cards],
                3: [self.card_key(card) for card in self.level3.cards],
            },
            "shown_nobles": [self.card_key(card) for card in self.shown_nobles],
            "nobles_deck": [self.card_key(card) for card in self.nobles.nobles] if self.nobles else [],
            "players": self.build_player_sync(),
            "game_over": self.game_over,
            "winner_text": self.winner_text,
        }

    def apply_state_update(self, state):
        if not self.initialized:
            return

        lookup = self.build_card_lookup()

        self.num_player = state.get("num_player", self.num_player)
        self.current_player = state.get("current_player", self.current_player)
        self.menu.current_num_players = self.num_player
        self.menu.host_room_name = state.get("room_name", self.menu.host_room_name)

        if self.bank and "bank_gem" in state:
            self.bank.gem = list(state["bank_gem"])

        level_decks = state.get("level_decks", {})
        for level in [1, 2, 3]:
            deck = getattr(self, f"level{level}", None)
            if deck and level in level_decks:
                deck.cards = self.resolve_card_keys(level_decks[level], lookup)

        board_state = state.get("board", {})
        for level in [1, 2, 3]:
            if level in board_state:
                self.board[level] = self.resolve_card_keys(board_state[level], lookup)

        if self.nobles and "nobles_deck" in state:
            self.nobles.nobles = self.resolve_card_keys(state["nobles_deck"], lookup)
        if "shown_nobles" in state:
            self.shown_nobles = self.resolve_card_keys(state["shown_nobles"], lookup)

        for player, player_state in zip(self.players, state.get("players", [])):
            player.point = player_state.get("point", player.point)
            player.temp = player_state.get("temp", player.temp)
            player.perm = player_state.get("perm", player.perm)
            player.cards = self.resolve_card_keys(player_state.get("cards", []), lookup)
            player.deposit_card = self.resolve_card_keys(player_state.get("deposit_card", []), lookup)
            player.noble = self.resolve_card_keys(player_state.get("noble", []), lookup)

        self.game_over = state.get("game_over", self.game_over)
        self.winner_text = state.get("winner_text", self.winner_text)
        self.current_action = None
        self.selected_gems = []
        self.selected_gem = None
        self.choosing_card = None
        self.choosing_nobles = []
        self.show_noble_overlay = False

    def build_initial_state(self):
        state = self.build_serializable_state()
        state['room_name'] = self.menu.host_room_name or 'Unnamed'
        self.reload_sprites()
        self.wait_for_sprite_reload()
        return state

    def configure_multiplayer_players(self):
        if not self.server:
            return
        connected_clients = self.server.connected_client_count()
        for idx in range(1, min(self.num_player, connected_clients + 1)):
            self.players[idx] = Player()

    def broadcast_multiplayer_state(self):
        if self.is_host and self.server and self.server.game_started:
            self.server.broadcast_state(self.build_state_update())

    def get_card_reference(self, card):
        if card is None:
            return None

        for level in [1, 2, 3]:
            for index, board_card in enumerate(self.board[level]):
                if board_card.is_same_card(card):
                    return {"source": "board", "level": level, "index": index}

        current_player = self.players[self.current_player]
        for index, deposit_card in enumerate(current_player.deposit_card):
            if deposit_card.is_same_card(card):
                return {"source": "deposit", "index": index}

        return None

    def resolve_card_reference(self, player_index, card_ref):
        if not card_ref:
            return None

        source = card_ref.get("source")
        if source == "board":
            level = card_ref.get("level")
            index = card_ref.get("index")
            if level in self.board and isinstance(index, int) and 0 <= index < len(self.board[level]):
                return self.board[level][index]
        elif source == "deposit":
            index = card_ref.get("index")
            player = self.players[player_index]
            if isinstance(index, int) and 0 <= index < len(player.deposit_card):
                return player.deposit_card[index]
        return None

    def submit_client_action(self):
        if not self.client:
            return

        payload = {
            "current_action": self.current_action,
            "selected_gems": list(self.selected_gems),
            "selected_gem": self.selected_gem,
            "card_ref": self.get_card_reference(self.choosing_card),
        }
        self.client.send_action(payload)
        self.current_action = None
        self.selected_gems = []
        self.selected_gem = None
        self.choosing_card = None

    def handle_network_action(self, player_index, payload):
        event = threading.Event()
        request = {
            "player_index": player_index,
            "payload": payload,
            "event": event,
            "result": (False, "Action timed out"),
        }
        with self.pending_network_lock:
            self.pending_network_actions.append(request)
        event.wait(timeout=5.0)
        return request["result"]

    def process_network_actions(self):
        if not self.is_host:
            return

        with self.pending_network_lock:
            requests = list(self.pending_network_actions)
            self.pending_network_actions.clear()

        for request in requests:
            request["result"] = self._apply_network_action(
                request["player_index"],
                request["payload"],
            )
            request["event"].set()

    def _apply_network_action(self, player_index, payload):
        if player_index != self.current_player:
            return False, "It is not this player's turn"

        action = payload.get("current_action")
        self.current_action = action
        self.selected_gems = payload.get("selected_gems", [])
        self.selected_gem = payload.get("selected_gem")
        self.choosing_card = self.resolve_card_reference(player_index, payload.get("card_ref"))

        if not self.can_confirm():
            self.current_action = None
            self.selected_gems = []
            self.selected_gem = None
            self.choosing_card = None
            return False, "Invalid action"

        self.execute_action()
        return True, None

    def init_players(self, num_players):
        self.num_player = num_players
        # Create first player as human, rest as bots
        self.players = [Player()]
        for i in range(1, num_players):
            self.players.append(self.get_selected_bot())

        # draw additional nobles
        if self.num_player > 2:
            [self.shown_nobles.append(self.nobles.draw()) for i in range(self.num_player + 1 - 3)]

        self.noble_rects = []
        for i, noble in enumerate(self.shown_nobles):
            noble_rect = pygame.Rect(START_X + (i + 1) * (CARD_W + GAP), 20, CARD_W, CARD_W) # Noble thường hình vuông
            self.noble_rects.append(noble_rect)

        self.bank = Bank(None, self, self.num_player)
