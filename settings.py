from __future__ import annotations
import pygame
import random
from pygame.locals import *
from functools import reduce
import csv

GAME_NAME = "Peak Boardgame"
WINDOW_RESOLUTION = (1024, 768)
GAME_SCALE = 1
FPS = 120
ROOM_DIRECTORY_HOST = "127.0.0.1"
ROOM_DIRECTORY_PORT = 12345
DEFAULT_ROOM_PORT = 23456

CARD_W, CARD_H = 100, 140  # Kích thước lá bài
GAP = 20                   # Khoảng cách giữa các lá
START_X = 50

DEPOSIT_POS = (310, 623)
DEPOSIT_OFFSET = 50

GEMS_START_Y = 150 
GEM_SIZE = 60  # Kích thước hiển thị của viên đá
GEM_GAP = 15   # Khoảng cách giữa các viên đá
VERTICAL_GAP = 10

ACTION_BTN_W = 100
ACTION_BTN_H = 100
ACTION_GAP = 10

RESOURCE_START_X = 20
GEM_DISPLAY_SIZE = 50 # Nhỏ hơn gem ở Bank một chút để vừa khung

BOT_TYPES = ["Random", "Monte Carlo", "Minimax"]
MIN_PLAYERS = 2
MAX_PLAYERS = 4

ACTION_ZONE_H = 150

COLOR_INDEX = ["black","blue","green","red","white"]
GEMS_INDEX = ["Onyx","Sapphire","Emerald","Ruby","Diamond","Gold"]
