from settings import *

class Card:
    def __init__(self, level, resources: list, color=None, points=0, path_dir=None):
        self.level = level
        self.color = color 
        self.resources = resources
        self.points = points
        if level is not None:
            self.dir = f"asset/level{level}/{path_dir}" if path_dir else None
        else:
            self.dir = f"asset/{path_dir}" if path_dir else None
        self.image = None
        self.is_draw = True

    def load(self):
        if self.image is None and self.dir:
            image = pygame.image.load(self.dir).convert_alpha()
            self.image = pygame.transform.smoothscale(image, (CARD_W, CARD_H))

    def draw(self, screen, position):
        if self.is_draw and self.image:
            rect = self.image.get_rect(topleft = position)
            screen.blit(self.image, rect)


    def is_same_card(self, card: 'Card'):
        if not card:
            return False
        return self.level == card.level and self.color == card.color and self.points == card.points and len(self.resources) == len(card.resources) and all(self.resources[idx] == card.resources[idx] for idx in range(len(self.resources)))

class Noble(Card):
    def __init__(self, level, color, resources, points=0, path_dir=None):
        super().__init__(level, resources, color, points, path_dir)
    
    def load(self):
        if self.image is None and self.dir:
            try:
                image = pygame.image.load(self.dir).convert_alpha()
                self.image = pygame.transform.smoothscale(image, (CARD_W, CARD_W))
            except Exception as e:
                print(f"Error loading noble image {self.dir}: {e}")

    def can_get(self, perm_resources):
        for index in range(5):
            if perm_resources[index] < self.resources[index]:
                return False
        return True

class NobleDeck:
    def __init__(self, nobles):
        self.nobles = nobles

    def draw(self):
        if not self.nobles:
            return None
        card = random.choice(self.nobles)
        self.nobles.remove(card)
        return card

class CardDeck:
    def __init__(self, cards: list, level: int):
        self.level = level
        self.cards = cards

    def draw(self) -> Card:
        if not self.can_draw():
            return None
        card = random.choice(self.cards)
        self.cards.remove(card)
        return card
        
    def can_draw(self):
        return bool(self.cards)
    
def process_card_data():
    cards_by_level = {}
    nobles = []
    cards = []
    try:
        with open('asset/level_card.csv', mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Dictionary chứa kết quả: {1: [], 2: [], 3: []}

            for row in reader:
                # Lấy thông tin cơ bản
                level = int(row['Level'])
                color = row['Color']
                points = int(row['PV'])
                path = row['Path']
                
                # Gom các tài nguyên thành một list theo thứ tự: Black, Blue, Green, Red, White
                resources = [
                    int(row['Black']),
                    int(row['Blue']),
                    int(row['Green']),
                    int(row['Red']),
                    int(row['White'])
                ]
                # Tạo instance của Card
                card = Card(
                    level=level,
                    resources=resources,
                    color=color,
                    points=points,
                    path_dir=path
                )
                
                # Phân loại vào level tương ứng
                if level not in cards_by_level:
                    cards_by_level[level] = []
                cards.append(card)
                cards_by_level[level].append(card)
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy level_card.csv")
    except KeyError as e:
        print(f"Lỗi: File card thiếu cột {e}")
    except Exception as e:
        print(f"Lỗi không xác định khi đọc Card: {e}")
    
    try:
        with open("asset/noble.csv", mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Noble mặc định 3 điểm, level 3
                res = [
                    int(row['Black']),
                    int(row['Blue']), 
                    int(row['Green']), 
                    int(row['Red']), 
                    int(row['White'])]
                
                noble = Noble(level = None, color = None, resources = res, points = 3, path_dir = row['Path'])
                nobles.append(noble)
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file noble asset/noble.csv")
    except KeyError as e:
        print(f"Lỗi: File noble thiếu cột {e}")
    except Exception as e:
        print(f"Lỗi không xác định khi đọc Noble: {e}")
    
    return cards_by_level, cards, NobleDeck(nobles)

def card_cost_to_dict(card):
    keys = ["black", "blue", "green", "red", "white"]
    return {keys[i]: card.resources[i] for i in range(5)}