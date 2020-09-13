#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
██████╗  ██████╗ ██╗    ██╗███████╗██████╗ ██╗      █████╗ ██╗    ██╗███╗   ██╗
██╔══██╗██╔═══██╗██║    ██║██╔════╝██╔══██╗██║     ██╔══██╗██║    ██║████╗  ██║
██████╔╝██║   ██║██║ █╗ ██║█████╗  ██████╔╝██║     ███████║██║ █╗ ██║██╔██╗ ██║
██╔═══╝ ██║   ██║██║███╗██║██╔══╝  ██╔══██╗██║     ██╔══██║██║███╗██║██║╚██╗██║
██║     ╚██████╔╝╚███╔███╔╝███████╗██║  ██║███████╗██║  ██║╚███╔███╔╝██║ ╚████║
╚═╝      ╚═════╝  ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═══╝
                            by Martin Velikov
"""
import os
import math
import copy
import time
import random
import traceback
import warnings
import logging
import webbrowser

VERSION = '1.0'

# incorporate level-based logging instead of unfiltere print
USE_ADVANCED_LOGGING = True
# show debug prints? warning: spams console
ADVANCED_LOGGING_SHOW_DEBUG = True
# show debug draws on screen? eg. bounding boxes
PERFORM_DEBUG_DRAWS = True
# screen dimensions
FRAME_W = 700
FRAME_H = 700
# frame dimensions
SCREEN_W = 1280
SCREEN_H = 720
# fixed framerate
FRAMERATE = 60
# resources folder
RES_FOLDER = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    'res'
)

# check version first
import sys
if not sys.version_info.major == 3 and sys.version_info.minor >= 5:
    print('This program requires Python version 3.5 or above.')
    print('You are running Python {0.major}.{0.minor}.{0.micro}!'.format(
        sys.version_info
    ))
    exit(1)

# hide DeprecationWarning for float coordinate movement
warnings.filterwarnings("ignore", category=DeprecationWarning)
# hide the annoying prompt message pygame comes with
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame  # the one and only

from pygame import Vector2  # this is used a lot


def weight_point_in_circle(
        point: tuple,
        center: tuple,
        radius: int,
        corner_threshold: float = 1.5
):
    """
    Function to decide whether a certain grid coordinate should be a full, half or empty tile.

        Arguments:
            point (tuple): x, y of the point to be tested
            center (tuple): x, y of the origin (center) point
            radius (int): radius of certainly empty tiles, does not include half tiles
            corner_threshold (float): threshold that decides if the tile should be a half tile instead of empty

        Returns:
            int: the type of the tested tile

            0 if empty tile
            1 if full tile
            2 if half tile
    """
    diff_x, diff_y = map(lambda x, y: abs(x - y), center, point)  # subtract point from center then abs for both x and y

    if (diff_y > radius) or (diff_x > radius):
        return 0  # eliminate any obviously out of bounds tiles

    # precalculate pythagoras distance squared
    dist_squared = (diff_x * diff_x) + (diff_y * diff_y)
    # precalculate radius sqaured
    radius_squared = radius * radius
    # precalculate rounded distance
    rounded_distance = round(dist_squared)

    if rounded_distance < radius_squared:  # distance within radius
        return 1  # full tile
    elif rounded_distance < radius_squared * corner_threshold and diff_x < radius:  # distance on edge
        return 2  # half tile
    # outside of any thresholds
    return 0  # empty tile


def cell_from_screenspace(screenspace_coords: tuple, tile_size: int):
    """
    Helper function to convert from screenspace coordinates to tile row and column.
    Calculations based on texture base tile size; no boundary checking is performed.

    Parameters:
        screenspace_coords (Tuple[float, float]): The X and Y screeenspace coordinates of the probe location.

    Returns:
        Tuple[int, int]: Array containing the X and Y values of the corresponding tile coordinate.
    """
    return tuple(
        map(
            lambda n: int(n * (1 / tile_size)),
            screenspace_coords
        )
    )


def open_github():
    webbrowser.open('https://github.com/xxcodianxx/', autoraise=True)


class Game:
    """
    Main game object that should take care of most of the game logic such as score, keeping track of objects
    and calling their update methods.

    Attributes
    ----------
    running : bool
        Whether the game is currently updating events

    logger : Optional[logging.Logger]
        The logger with which to log console messages
        Can be None to use default print() call

    frame : pygame.Surface
        The frame surface within which to render the game

    screen : pygame.Surface
        Binding to the initialized PyGame screen

    screen_clock : pygame.time.Clock
        Timing clock to keep framerate constant

    objects : List[GameObject]
        List of game objects to be updated
        Note that index 0 should always be reserved for the player

    event_callback_ingame : dict{pygame.event.Event : function}
        Bindings from PyGame events to class methods
        If a method is within this list, it should have at least one variable to catch the original event

        Example:
        def event_function(e):
            ...

        Note the extra `e` argument here. Although it may be unused, it is required for that function
        to be within the event_callback dictionary.

    keys_down : List[int]
        List of currently pressed keys, usually referenced by game objects

    textures : Game.Textures
        Texture handler for all game sprites, referenced upon creation of GameObject

    tile_grid : List[List[int], ...]
        Two-dimensional array containing the state of each tile
        this can represent:
            * 0 for full (visually transparent)
            * 1 for empty (visually mown)
            * 2 for half (visually half-mown)

    path_radius : int
        radius within which to generate path
        called upon pre-baking of the path quadrant

    path_template : List[List[int]]
        pre-generated quadrant of the player path at runtime
        see method `bake_path_quadrant` for generation
        this quadrant is generated once at the beginning, then masked four times
        every frame depending on the player's tile position
        see method `update_path` to see this in action
    """

    def __init__(self, logger: logging.Logger = None):
        """
        Base Game which takes care of the logic. Manages and updates its objects.
        There should really be only one of these at any time.
        :param logger: the logger to use, if not specified, it will use print sattements
        """
        self.running = False  # is the game running?
        self.logger = logger

        # frame where the playing f   ield is
        self.frame: pygame.Surface = pygame.Surface((FRAME_W, FRAME_H))
        # screen
        self.screen: pygame.Surface = None  # initialized later
        # framerate cap clock
        self.screen_clock = None
        # list of GameObject's or subclasses thereof
        self.objects = []
        # dict of events and their corresponding functions to be run when caught
        self.event_callback_ingame = {
            pygame.QUIT: self.event_quit,
            pygame.KEYUP: self.event_key,
            pygame.KEYDOWN: self.event_key
        }

        self.event_callback_menu = {
            pygame.QUIT: self.event_quit
        }

        # currently pressed keys
        self.keys_down = []
        # textures to load
        self.textures = None
        # fonts to load
        self.fonts = None
        # background tile grid
        self.tile_grid = []

        # tile grid size
        self.tile_grid_w = 0
        self.tile_grid_h = 0

        # player trail radius
        self.path_radius = 2
        # player path quadrant
        self.path_template = []

        # total power used so far
        self.power_used = 0

        # cost per watt
        self.current_cost = 0.0005
        # normal_cost
        self.normal_cost = 0.0005
        # powered up cost
        self.powered_up_cost = -0.0005

        # money before the game ends and you exaust your money supply
        self.money_limit = 5000
        # money currently spent
        self.money = 0

        # W if slowed
        self.slow_power_consumption = 2400
        # W if not slowed
        self.normal_power_consumption = 800
        # power consumption every frame
        self.current_power_consumption = self.normal_power_consumption

        # frames rendered since the game has started
        self.frames_since_game_start = 0
        # last_powerup
        self.last_powerup = 0
        self.powerups_used = 0

        self.powerup_names = {
            0: 'Swiftness',
            1: 'Anti-Debt',
            2: 'Human Zapper'
        }

        self.current_power_consumption = self.normal_power_consumption
        self.paused = False
        self.game_started = False

        self.mouse_pos = (0, 0)
        self.mouse_pressed = (False, False, False)

        self.button_pressed = None

        self.main_menu_page = 0

        # old game objects
        self.game_objects = []

        self.pause_button = None
        self.game_over = False

    class Textures:
        def __init__(self):
            self.base_tile_size = 10
            self.base_bg_tile_size = 60
            self.base_enemy_size = (100, 200)

            # tiles
            self.tile_dev = pygame.image.load(
                os.path.join(RES_FOLDER, 'img', 'tiles', 'dev.png')
            )
            self.tile_empty = pygame.image.load(
                os.path.join(RES_FOLDER, 'img', 'tiles', 'empty.png')
            )
            self.tile_half = pygame.image.load(
                os.path.join(RES_FOLDER, 'img', 'tiles', 'half.png')
            )

            # accessed from tilemap
            self.tile_mappings = [
                None,  # 0 -> full tile
                self.tile_empty,  # 1 -> empty tile
                self.tile_half,  # 2 -> half tile,
                self.tile_dev
            ]

            # player sprite
            self.player = pygame.transform.scale(
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'char.png')
                ), (150, 60)
            )

            # background tile
            self.tile_bg_grass = pygame.transform.scale(
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'tiles', 'bgtile.png')
                ), (self.base_bg_tile_size, self.base_bg_tile_size)
            )

            # replicated background that should fill the screen, see Game.bake_background_texture
            self.full_bg = None
            self.screen_full_bg = None

            self.enemy_kick = [
                pygame.transform.scale(
                    pygame.image.load(
                        os.path.join(RES_FOLDER, 'img', 'enemy', f'kick{i}.png')
                    ), self.base_enemy_size
                )
                for i in (0, 1)
            ]

            self.enemy_cycle = [
                pygame.transform.scale(
                    pygame.image.load(
                        os.path.join(RES_FOLDER, 'img', 'enemy', f'run{i}.png')
                    ), self.base_enemy_size
                )
                for i in (0, 1, 2, 1)
            ]

            self.enemy_stun = pygame.transform.scale(
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'enemy', 'stun.png')
                ), self.base_enemy_size
            )

            self.wallet_icon = pygame.image.load(
                os.path.join(RES_FOLDER, 'img', 'wallet.png')
            )

            self.powerups = (
                pygame.image.load(os.path.join(RES_FOLDER, 'img', 'powerups', 'speed.png')),
                pygame.image.load(os.path.join(RES_FOLDER, 'img', 'powerups', 'money.png')),
                pygame.image.load(os.path.join(RES_FOLDER, 'img', 'powerups', 'stun.png')),
            )

            self.powerup_icons = [
                pygame.transform.scale(i, (25, 25)) for i in self.powerups
            ]

            self.title = pygame.image.load(
                os.path.join(RES_FOLDER, 'img', 'title.png')
            )

            self.button = [
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'ui', 'button', f'{i}.png')
                )
                for i in (0, 1, 2)
            ]

            self.button_small = [
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'ui', 'smallbutton', f'{i}.png')
                )
                for i in (0, 1, 2)
            ]

            self.bg_frame = pygame.image.load(
                os.path.join(RES_FOLDER, 'img', 'ui', 'frame.png')
            )

            self.keycaps = [
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'ui', 'keycaps', f'{i}.png')
                )
                for i in ('a', 'd')
            ]

    class Fonts:
        def __init__(self):
            path_arcade = os.path.join(
                RES_FOLDER, 'fonts', 'arcade.ttf'
            )
            self.arcade_50 = pygame.font.Font(
                path_arcade, 50
            )
            self.arcade_25 = pygame.font.Font(
                path_arcade, 25
            )
            self.arcade_50: pygame.font.Font

    def log(self, msg: str, level: int = 1):
        """
        Log things to the console. Respects USE_ADVANCED_LOGGING.

        Parameters:
            msg (str): Message to log to the console.
            level (Optional[int]): Message severity: 0 DEBUG, 1 INFO, 2 WARNING, 3 CRITICAL

        """
        if self.logger is not None:
            callback = [
                self.logger.debug,
                self.logger.info,
                self.logger.warning,
                self.logger.error
            ]
            callback[level](msg)
            return  # run the corresponding function with the `msg` argument then return
        print(f'[{["DEBUG", "INFO", "WARNING", "ERROR"][level]}] : {msg}')  #

    @property
    def player(self):
        if len(self.objects):
            return self.objects[0]
        return None

    # ---------------- Essential ----------------

    def run_forever(self):
        """
        Initialize and run the game forever until it quits.
        If this function returns, then the game has ended.
        Returns the exit code for the game, run this last.
        """
        # load the textures
        self.log('Loading textures...')
        self.textures = self.Textures()

        self.log('Loading fonts...')
        pygame.font.init()
        self.fonts = self.Fonts()

        # init the screen and prepare it
        self.log(f'Initializing screen ({SCREEN_W}x{SCREEN_H})')
        pygame.init()
        pygame.display.set_caption(f'Power Lawn v{VERSION}')
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.screen_clock = pygame.time.Clock()  # frame clock

        # make a quadrant of the player path
        self.log(f'Baking path quadrant...')
        self.bake_path_quadrant()

        # replicate the grass texure to fill the frame's size
        self.log(f'Baking screen texture to size {SCREEN_W}x{SCREEN_H}...')
        self.textures.screen_full_bg = self.bake_background_texture(self.screen.get_size())

        # replicate the grass texure to fill the frame's size
        self.log(f'Baking background texture to size {FRAME_W}x{FRAME_H}...')
        self.textures.full_bg = self.bake_background_texture(self.frame.get_size())

        self.log(f'Setting up main menu...')
        self.prepare_main_menu()

        # finally, start the game
        self.log('Starting event loop...')
        self.running = True

        while self.running:
            self.mouse_pos = pygame.mouse.get_pos()
            self.mouse_pressed = pygame.mouse.get_pressed()
            if self.game_started:
                if not self.paused:
                    # the game has begun
                    self.tick_objects()  # update everything
                    self.tick_powerups()
                    self.full_draw()
                    self.process_events(pygame.event.get())  # process event queue
                    self.frames_since_game_start += 1
                    self.last_powerup += 1
                    self.try_spawn_powerup()

                    if self.paused:
                        self.enter_pause_menu()
                else:
                    self.draw_pause_menu()
                    self.process_events(pygame.event.get())
            else:
                self.draw_main_menu()
                self.process_events(pygame.event.get())
            self.screen_clock.tick(FRAMERATE)  # cAlm tHe TiDe
        self.log('Game exited normally', 0)
        return 0

    def start_game(self, e=None):
        self.log('Preparing game...')

        # make the big tile array
        self.log('Baking initial tilemap...')
        self.bake_tile_grid()

        # create the game objects
        self.log(f'Creating objects...')
        self.objects = [
            # slot 0 should always be the main player
            Player(parent=self, start_x=-45, start_y=0, start_angle=0, image=self.textures.player),
            Enemy(parent=self, start_x=500, start_y=500, start_angle=0, image=self.textures.enemy_kick[0]),
        ]
        self.pause_button = Button(self, self.frame.get_width()+20, self.screen.get_height()-74, 'P', self.textures.button_small, self.set_paused)

        self.log(f'{len(self.objects):,} objects active')

        # set enemy target
        self.objects[1].target = self.player

        self.game_started = True

    # ---------------- Main Menu ----------------

    def prepare_main_menu(self):
        if self.main_menu_page == 0:
            self.objects = [
                Button(self, 100, 440, 'Start', self.textures.button, self.start_game),
                Button(self, 100, 520, 'How to Play', self.textures.button, self.switch_main_menu_page, [1]),
                Button(self, 100, 600, 'Credits', self.textures.button, self.switch_main_menu_page, [2])
            ]
        elif self.main_menu_page == 2:
            self.objects = [
                Button(self, self.screen.get_width() / 2 - 150, 450, 'GitHub', self.textures.button, open_github),
                Button(self, self.screen.get_width() / 2 - 150, 620, 'Back', self.textures.button, self.switch_main_menu_page, [0])
            ]
        else:
            self.objects = [
                Button(self, self.screen.get_width() / 2 - 150, 620, 'Back', self.textures.button, self.switch_main_menu_page, [0])
            ]

    def draw_main_menu(self):
        self.screen.blit(self.textures.screen_full_bg, (0, 0))

        if self.main_menu_page == 0:
            self.screen.blit(self.textures.title, (0, 0))
        elif self.main_menu_page == 1:
            instructions = """
You've one job: mow the lawn!
Easy, right? Not quite. You're 
one of those new "smart" lawnmowers.
You're quite power hungry, so
try to do it as fast as possible.
Oh, also, don't get caught by 
your owner. He won't hesitate.
"""

            self.show_info_screen('How To Play', instructions)
            control_text = self.fonts.arcade_25.render('Use   and   to turn the lawnmower.', False, (61, 64, 66))
            control_text_x = (self.screen.get_width() / 2) - (control_text.get_width() * 0.5)
            self.screen.blit(
                control_text,
                (control_text_x, 460)
            )

            self.screen.blit(self.textures.keycaps[0], (control_text_x + 70, 440))
            self.screen.blit(self.textures.keycaps[1], (control_text_x + 220, 440))
        elif self.main_menu_page == 2:
            credits_text = f"""
            Version {VERSION}            

All programming & visual assets by
me. Created for Year 10 Technology
school assignment at GIHS.

By Martin Velikov (xxcodianxx)
"""
            self.show_info_screen(f'Power Lawn', credits_text)

        self.tick_objects()
        self.draw_objects()

        pygame.display.update()

    def switch_main_menu_page(self, page):
        self.main_menu_page = page
        self.prepare_main_menu()
        self.draw_main_menu()

    def show_info_screen(self, title, description):
        middle = self.screen.get_width() / 2
        self.screen.blit(
            self.textures.bg_frame,
            (middle - (self.textures.bg_frame.get_width() * 0.5), 50)
        )

        title = self.fonts.arcade_50.render(title, False, (61, 64, 66))
        self.screen.blit(
            title,
            (middle - (title.get_width() * 0.5), 80)
        )

        for idx, line in enumerate(description.splitlines()):
            line_text = self.fonts.arcade_25.render(line, False, (61, 64, 66))
            self.screen.blit(
                line_text,
                (middle - 400, 150 + (30 * idx))
            )

    # ---------------- Pause Menu ----------------

    def set_paused(self):
        """Helper function to only set the paused variable, so it can be binded to callbacks"""
        self.paused = True

    def enter_pause_menu(self):
        self.game_objects = self.objects
        if self.game_over:
            self.objects = [
                Button(self, self.screen.get_width() / 2 - 150, 620, 'Continue', self.textures.button, self.reset_to_main_menu),
            ]
        else:
            self.objects = [
                Button(self, self.screen.get_width() / 2 - 350, 620, 'Main Menu', self.textures.button, self.reset_to_main_menu),
                Button(self, self.screen.get_width() / 2 + 50, 620, 'Continue', self.textures.button, self.continue_game)
            ]

    def draw_pause_menu(self):
        self.screen.blit(self.textures.screen_full_bg, (0, 0))

        if not self.game_over:
            self.show_info_screen('Paused', '       The game is paused.')

            newsize = (300, 300)
            newpos = (self.screen.get_width() / 2 - newsize[0]*0.5, 200)
            margins = (4, 4)

            pygame.draw.rect(self.screen, 0x010101, pygame.Rect(
                newpos[0] - (margins[0] * 0.5),
                newpos[1] - (margins[1] * 0.5),
                newsize[0] + (margins[0]),
                newsize[1] + (margins[1])
            ))
            self.screen.blit(pygame.transform.scale(self.frame, newsize), newpos)
        else:
            self.draw_game_over_screen()

        self.tick_objects()
        self.draw_objects()

        pygame.display.update()

    def continue_game(self):
        self.objects = self.game_objects
        self.paused = False

    def reset_to_main_menu(self):
        self.money = 0
        self.current_power_consumption = self.normal_power_consumption
        self.paused = False
        self.main_menu_page = 0
        self.frames_since_game_start = 0
        self.current_cost = 0.0005
        self.power_used = 0
        self.game_started = False
        self.game_over = False

        self.prepare_main_menu()

    # ---------------- Game Over ----------------

    def set_game_over(self):
        self.paused = True
        self.game_over = True

    def draw_game_over_screen(self):
        percent, mown = self.get_mown_percentage()

        msg = 'You ran out of money!'
        if percent == 100:
            msg = 'You mowed the entire lawn!'

        stat = f'''
{msg}

Lawn Covered: {format(percent, ".2f")}%
Tiles Mown: {mown}
Power Used: {self.power_used}W
Powerups Consumed: {self.powerups_used}

You were alive for {self.frames_since_game_start / FRAMERATE} seconds.

Have another shot, will ya?
'''

        self.show_info_screen('Game Over', stat)


    # ---------------- Initialization ----------------

    def bake_tile_grid(self):
        """
        Generates empty tile array the size of the screen.
        Its strucure is equrivalent to
        [
            [0, 0, 0, 0, (...)],
            [0, 0, 0, 0, (...)],
            [0, 0, 0, 0, (...)],
        ]
        Where each number represents the tile state - here, 0 is full tile.
        To reference any cell within it: tilemap[row][column]
        """
        self.tile_grid = []
        self.tile_grid_h = 0
        self.tile_grid_w = divmod(self.frame.get_width(), self.textures.base_tile_size)[0]
        for _ in range(0, self.frame.get_height(), self.textures.base_tile_size):
            self.tile_grid.append(
                [0 for _ in range(0, self.frame.get_width(), self.textures.base_tile_size)]
            )
            self.tile_grid_h += 1

    def bake_path_quadrant(self):
        """
        Generate one quadrant of the path to be mirrored later.
        This is calculated once and saved to quarter_path_template.
        It is applied every frame from the baked template, without being recalculated. Speed!
        """
        self.path_template = []  # output array
        for ri in range(self.path_radius + 1):  # row index
            r = []  # temporary row array
            for ci in range(self.path_radius + 1):  # column index
                r.append(  # add the type of that cell to that index, using the weighting function
                    weight_point_in_circle((ci, ri), (0, 0), self.path_radius)
                )
            self.path_template.append(r)  # add the row to the path quadrant

        if ADVANCED_LOGGING_SHOW_DEBUG:  # show what the quadrant looks like once baked
            s = ''
            for r in self.path_template:
                s += (' ' * 28) + ': ' + ''.join(map(lambda v: ['[-]', '[#]', '[$]'][v], r)) + '\n'
            self.log('Path quadrant result (#/full, $/half, -/empty): \n' + s.rstrip(), 0)

    def bake_background_texture(self, size=(700, 700)):
        """
        Replicates the background tile to the required size of the frame.
        Outputs result to self.textures.full_bg
        """
        # create surface large enough to house texture
        bg = pygame.Surface(size)

        # blit tile texture to larger texture
        for y in range(0, size[1], self.textures.base_bg_tile_size):
            for x in range(0, size[0], self.textures.base_bg_tile_size):
                tile = pygame.transform.rotate(
                    self.textures.tile_bg_grass, random.choice((0, 90, 180, 270))
                )
                bg.blit(tile, (x, y))

        return bg

    # ---------------- Updaters ----------------

    def update_path(self):
        """
        Alter the tile array to include the path of the player relative to their position.
        """
        # Calculate the cell position of the player by using int rounding, this returns cell coords in the tile array
        player_cell_x, player_cell_y = cell_from_screenspace(self.player.globalRect.center,
                                                             self.textures.base_tile_size)

        # Now to set up the area around the player, we can just replicate the pregenerated quarter 4 times:

        # iterate through rows (iter as qr), keeping index as qy.
        for qy, qr in enumerate(self.path_template):
            # iterate through columns (iter as qc), keeping index as qx.
            for qx, qc in enumerate(qr):
                # do not draw empty pixels on the screen.
                if qc == 0:
                    continue

                # get tile grid width & height

                right = player_cell_x + qx
                left = player_cell_x - qx
                bottom = player_cell_y + qy
                top = player_cell_y - qy

                quads = (
                    (bottom, right),
                    (bottom, left),
                    (top, left),
                    (top, right)
                )

                quad = 0
                for y, x in quads:
                    if min(x, y) > -1 and x < self.tile_grid_w and y < self.tile_grid_h:
                        if qc == 2 and (  # is the cell about to be drawn a half-cell?
                                self.tile_grid[y][x] == 1  # is the tile at that position blank?
                                or
                                y > player_cell_y  # is the position of the half below the player coordinate?
                        ):
                            continue  # do not draw that half-cell

                        # add index in bottom right (original array orientation)
                        self.tile_grid[y][x] = qc
                    quad += 1

    def tick_objects(self):
        """
        Update all game objects, draw them to the screen call frame_to_screen.
        Gets called every frame, so make it fast.
        """
        to_cull = []
        for idx, game_object in enumerate(self.objects):
            game_object.update()

            if isinstance(game_object, Powerup):
                if not game_object.active:
                    to_cull.append(idx)

        for idx in to_cull:
            del self.objects[idx]

    def tick_powerups(self):
        to_cull = []
        for powerup, times in self.player.active_powerups.items():
            current, max_allowed = times
            if current >= max_allowed:
                to_cull.append(powerup)
                continue
            self.player.active_powerups[powerup] = (current+1, max_allowed)

        for idx in to_cull:
            if idx == 0:
                self.player.speed = 5
                self.current_power_consumption = self.normal_power_consumption
            elif idx == 1:
                self.current_cost = self.normal_cost
            elif idx == 2:
                self.objects[1].stunned = False
            del self.player.active_powerups[idx]

    def try_spawn_powerup(self):
        if self.last_powerup > FRAMERATE * 7:  # 30 seconds
            type = random.randint(0, 2)

            cx = random.randint(0, self.tile_grid_w - 6)
            cy = random.randint(0, self.tile_grid_h - 6)

            ss_x = cx * self.textures.base_tile_size
            ss_y = cy * self.textures.base_tile_size
            self.log(f'Spawning powerup type {type} at {ss_x}, {ss_y}', 0)

            instance = Powerup(self, ss_x, ss_y, 0, self.textures.powerups[type])
            instance.type = type
            instance.draw_priority = 10

            self.objects.append(instance)

            self.last_powerup = 0

    # ---------------- Rendering ----------------

    def full_draw(self):
        self.draw_tilemap()
        self.draw_objects()
        self.draw_ui_and_frame()

    def draw_tilemap(self):
        """
        Render the tilemap to the screen.
        This function takes care of:
            - Drawing the static texture for the background
            - Drawing the tilemap to the screen
        Does not update the player's path. See method `update_path` for that functionality.
        """

        # draw the background grid
        self.frame.blit(self.textures.full_bg, (0, 0))

        # draw the tile grid
        for cy, r in enumerate(self.tile_grid):
            # cell x, column data
            for cx, c in enumerate(r):
                if c == 0:
                    continue  # skip drawing this
                # get corresponding texture
                tex = self.textures.tile_mappings[c]
                # screenspace position
                ss_pos = (cx * self.textures.base_tile_size, cy * self.textures.base_tile_size)
                self.frame.blit(tex, ss_pos)

    def draw_objects(self):
        for game_object in sorted(self.objects, key=lambda x: x.draw_priority):
            game_object.draw()

    def draw_ui_and_frame(self):
        """
        Takes care of what everything looks like outside the frame window.
        Assumes everything inside the frame is ready to go.
        Refreshes the screen; the final draw call per frame.
        """
        self.screen.fill(0x262626)

        percent, mown = self.get_mown_percentage()
        if percent == 100:
            self.set_game_over()

        self.screen.blit(
            self.fonts.arcade_25.render(f'Lawn Stats', False, (142, 142, 142)),
            (self.frame.get_width() + 20, 10)
        )

        self.screen.blit(
            self.fonts.arcade_50.render(f'{format(percent, ".2f")}%', False, (255, 255, 255)),
            (self.frame.get_width() + 20, 40)
        )
        self.screen.blit(
            self.fonts.arcade_25.render(f'{mown} tiles mown', False, (255, 255, 255)),
            (self.frame.get_width() + 20, 95)
        )

        # power usage
        self.screen.blit(
            self.fonts.arcade_25.render(f'Power Bills', False, (142, 142, 142)),
            (self.frame.get_width() + 20, 150)
        )
        cost_font = self.fonts.arcade_50.render(
            f'${round(self.money)}', False,
            (82, 148, 226) if self.player.active_powerups.get(1) else (255, 255, 255)
        )
        self.screen.blit(
            cost_font,
            (self.frame.get_width() + 20, 180)
        )

        wattage_display = self.fonts.arcade_25.render(f'{self.power_used}W', False, (210, 210, 210))
        usage_display = self.fonts.arcade_25.render(
            f'+{self.current_power_consumption}',
            False,
            (111, 194, 52) if self.current_power_consumption == self.normal_power_consumption else (199, 84, 80)
        )

        usage_offset_y = 180 + cost_font.get_height() - (usage_display.get_height() + wattage_display.get_height())
        usage_offset_x = self.frame.get_width() + 30 + cost_font.get_width()

        self.screen.blit(
            usage_display,
            (usage_offset_x, usage_offset_y)
        )

        self.screen.blit(
            wattage_display,
            (usage_offset_x, usage_offset_y + usage_display.get_height())
        )

        self.screen.blit(self.textures.wallet_icon, (self.frame.get_width() + 30, 180 + cost_font.get_height()))

        rectx = self.frame.get_width() + 88
        recty = 188 + cost_font.get_height()

        pygame.draw.rect(self.screen, (111, 194, 52), pygame.Rect(rectx, recty, 300, 32))

        percent = self.money / self.money_limit
        if percent < 0:
            percent = 0
        elif percent > 1:
            percent = 1

        pygame.draw.rect(self.screen, (199, 84, 80), pygame.Rect(
            rectx, recty,
            int(percent * 300),  # <- bar width
            32
        ))

        # powerups
        if len(self.player.active_powerups.keys()):
            basex = self.frame.get_width()+20
            basey = recty+75

            self.screen.blit(
                self.fonts.arcade_25.render(f'Power Ups', False, (142, 142, 142)),
                (basex, basey)
            )

            offset_mult = 1
            for id, times in self.player.active_powerups.items():
                current, max_time = times
                y_offset = basey+(30*offset_mult)

                self.screen.blit(self.textures.powerup_icons[id], (basex, y_offset))
                self.screen.blit(
                    self.fonts.arcade_25.render(f'{self.powerup_names[id]} {format((max_time-current) / FRAMERATE, ".2f")}s', False, (255, 255, 255)),
                    (basex+35, y_offset)
                )
                offset_mult += 1

        self.pause_button.update()
        self.pause_button.draw()

        self.screen.blit(self.frame, (10, 10))
        pygame.display.update()

    # ---------------- Events & Processing ----------------

    def process_events(self, queue: tuple = ()):
        """
        Run through the event queue and resolve all events to their callbacks.
        :param queue: the event queue (duh)
        """

        if queue == ():  # save a bit of processing power
            return

        # get the correct binding dictionary for the main menu or ingame game state
        callback_mapping = (self.event_callback_ingame if self.game_started else self.event_callback_menu)

        for e in queue:
            # type define event object (pygame is confused)
            e: pygame.event.Event

            # is the event's callback defined? if yes, run it
            e_callback = callback_mapping.get(e.type)
            if e_callback:
                e_callback(e)
                # skip to next loop cycle
                continue
            # if the cycle is not skipped here, say that we missed the event on the DEBUG level
            # self.log(f'Uncaught event {e.type}', 0)

    def event_key(self, e = None):
        """Event callback method to process keypresses."""
        if (e.type == pygame.KEYDOWN) and (e.key not in self.keys_down):
            self.keys_down.append(e.key)
        elif (e.type == pygame.KEYUP) and (e.key in self.keys_down):
            self.keys_down.remove(e.key)

    def event_quit(self, e = None):
        """Event callback method to quit the game. """
        self.running = False
        self.log('Quitting...')
        pygame.quit()

    # ---------------- Miscellaneous ----------------

    def kick_player(self):
        v_player = Vector2(self.player.x, self.player.y)
        dist_to_right = int(self.frame.get_width() - self.player.x)
        dist_to_bottom = int(self.frame.get_height() - self.player.y)

        offset = Vector2(
            random.randint(int(-self.player.x) + 100, dist_to_right - 100),
            random.randint(int(-self.player.y) + 100, dist_to_bottom - 100)
        )

        self.objects[1].horizontal_flip = not (offset.x < 0)
        end_pos = v_player + offset

        for i in range(50):
            self.player.x, self.player.y = v_player.slerp(end_pos, i / 50)
            self.player.angle += random.randint(5, 8)  # 360 / 50
            self.tick_powerups()
            self.full_draw()
            pygame.draw.circle(self.frame, 0x0000ff, tuple(map(int, (self.player.x, self.player.y))), 5)
            pygame.draw.circle(self.frame, 0xff0000, tuple(map(int, end_pos)), 5)
            self.screen_clock.tick(FRAMERATE)

    def get_mown_percentage(self):
        mown = 0
        for r in self.tile_grid:
            for c in r:
                if c:
                    mown += 1
        return (mown / (70 * 70)) * 100, mown


class GameObject(pygame.sprite.Sprite):
    def __init__(self, parent: Game, start_x=0, start_y=0, start_angle=0, image=None):
        """
        Universal GameObject class to be inherited & overriden by specific objects.

        :param parent: originating game object
        :param start_x: initial horizontal position
        :param start_y: initial vertical position
        :param image: sprite
        """
        super(GameObject, self).__init__()
        self.draw_priority = 100  # object update priority, higher = sooner

        self.parent = parent
        if image is None:
            image = pygame.Surface((0, 0))

        self.image = image

        self.x, self.y = start_x, start_y
        self.angle = start_angle

        self.rect = self.image.get_rect()
        self.globalRect = pygame.Rect(
            self.rect.x + self.x,
            self.rect.y + self.y,
            self.rect.w, self.rect.h
        )

    def update(self):
        """
        Dynamic method to update the state/position/whatever you want of the game object.
        Gets called every frame, so makstart_anglee it fast.
        By default, just does nothing.
        """
        pass

    def draw(self, surface=None, image=None):
        """
        Rotates the game object's sprite to the appropriate angle around its center,
        then blits it to the surface specified.  If no surface is specified, the parent's
        display object is used.

        Parameters:
            surface (Optional[Surface]): the surface to draw sprite image on
            image (Optional[Surface]): the surface to draw to the screen instead of self.image
        """

        if surface is None:
            surface = self.parent.frame

        if image is None:
            image = self.image

        if self.angle != 0:  # use the expensive calculation below only if there is any actual rotation
            # some rotation is happening, offset calculation is required
            img_w, img_h = image.get_size()

            bounding_box = [
                Vector2(0, 0),  # top left
                Vector2(img_w, 0),  # top right
                Vector2(img_w, -img_h),  # bottom right
                Vector2(0, -img_h)  # bottom left
            ]

            # rotate all vectors to match our rotation
            bounding_box = [vec.rotate(self.angle) for vec in bounding_box]

            # get smallest x value in all points' x values
            min_x = min(bounding_box, key=lambda vec: vec[0])[0]

            # get largest y value in all points' y values
            max_y = max(bounding_box, key=lambda vec: vec[1])[1]

            # get center of image
            center = Vector2(
                (img_w * 0.5),  # TODO: center offset, also do globalRect
                -(img_h * 0.5)  # pygame vectors are upside down, so this is negative
            )
            # how much should be corrected from the rotation
            pivot_offset = center.rotate(self.angle) - center

            pos = (  # apply the offsets
                self.x + min_x - pivot_offset[0],
                self.y - max_y + pivot_offset[1]
            )

            img = pygame.transform.rotate(image, self.angle)  # rotate image
        else:
            # the angle is 0, forget all of the expensive calculations above
            img = image
            pos = (self.x, self.y)

        self.rect = img.get_rect()  # update internal rectangle
        # re-calculate global rectangle, mindful of offset and new size
        self.globalRect = pygame.Rect(
            pos[0], pos[1],
            self.rect.w, self.rect.h
        )

        surface.blit(img, pos)  # draw to the screen at the proper position

    def log(self, *args):
        """Binding to parent's log function for ease of access."""
        self.parent.log(*args)


class Player(GameObject):
    """
    This class is a game object that represents the player's
    head. It strives to move towards the mouse pointer.
    """

    def __init__(self, *args, **kwargs):
        super(Player, self).__init__(*args, **kwargs)

        self.speed = 5  # speed of the player, used in update()
        self.turnspeed = 6

        # these probes
        self.path_probes = [
            # (30, 20),  # front right
            # (30, -20),  # front left
            # front middle
            (30, 0)
        ]

        self.movement_allowed = True

        self.key_up = pygame.K_w
        self.key_down = pygame.K_s
        self.key_right = pygame.K_d
        self.key_left = pygame.K_a

        self.key_pause = pygame.K_ESCAPE

        """
        Active power-ups:
        
        {
            <powerup_id>: <frames_elapsed>, <max_frames>)
        }
        
        """

        self.active_powerups = {}

    def update(self):
        """
        Player Update function. Moves the player's position towards
        the desired angle at a constant speed defined in its class
        attributes.
        """

        if self.movement_allowed:  # only run this code if movement is allowed, pointless otherwise
            # alter angle based on which keys are pressed
            if self.key_right in self.parent.keys_down:
                self.angle -= self.turnspeed
            if self.key_left in self.parent.keys_down:
                self.angle += self.turnspeed
            if self.key_pause in self.parent.keys_down:
                self.parent.set_paused()
            """
            IF YOU EVER NEED CONTROLLABLE SPEED AGAIN...
            
            if self.key_down in self.parent.keys_down and self.speed >= 0.1:
                self.speed -= 0.1
            if self.key_up in self.parent.keys_down:
                self.speed += 0.1
                
            """

            # round the speed off, floating points are annoying
            self.speed = round(self.speed, 3)
            # save time calling the Surface method
            frame_w, frame_h = self.parent.frame.get_size()
            # is the player's speed reduced as a result of getting stuck?
            is_slowed_down = False

            # perform check for each probe
            for probe in self.path_probes:
                # convert local probe point offsets to global coordinates, and get their cell row/column
                global_vector, cell = self.offset_point(probe)

                try:
                    # check tile at the probe's location
                    at_probe = self.parent.tile_grid[cell[1]][cell[0]]
                except IndexError:
                    # that coordinate is out of bounds (eg. probe is clipping out of frame)
                    pass
                else:
                    # successfully got tile at cell
                    if at_probe == 1:
                        # the tile there is an empty tile, cowabunga it is
                        is_slowed_down = True

                # TODO: remove this
                pygame.draw.circle(self.parent.frame, 0xff0000, tuple(map(int, global_vector)), 10)

            # calculate the true speed based on slowdown, use self.speed if no slowdown
            if is_slowed_down:
                real_speed = (self.speed / 2)
                if self.parent.current_power_consumption == self.parent.normal_power_consumption:
                    self.parent.current_power_consumption = self.parent.slow_power_consumption
            else:
                real_speed = self.speed
                if self.parent.current_power_consumption == self.parent.slow_power_consumption:
                    self.parent.current_power_consumption = self.parent.normal_power_consumption
            self.parent.power_used += int(self.parent.current_power_consumption / FRAMERATE)

            # calculate step movement every frame
            step_x = math.cos(math.radians(-self.angle)) * real_speed
            step_y = math.sin(math.radians(-self.angle)) * real_speed

            # check if movement is valid, and it it is, go for it
            if frame_w > self.globalRect.center[0] + step_x > 0:
                self.x += step_x
            if frame_h > self.globalRect.center[1] + step_y > 0:
                self.y += step_y

            self.parent.money += self.parent.current_cost * self.parent.current_power_consumption
            if self.parent.money >= self.parent.money_limit:
                self.parent.set_game_over()

            self.parent.update_path()

    def offset_point(self, probe: tuple):
        """
        Converts local offset coordinates to global ones, relative to player coordinates.
        Also returns the cell index of that coordinate set using `cell_from_screenspace`.

        Parameters:
            probe (Tuple(float, float): The offset, local coordinates. Assumes 0,0 is pivot.

        Returns:
            Tuple(Vector2, Tuple(int, int)) : Pair of the screenspace coordinate and cell index.
        """
        global_vector = Vector2(probe).rotate(-self.angle) + self.globalRect.center
        cell = cell_from_screenspace(global_vector, self.parent.textures.base_tile_size)
        return global_vector, cell


class Enemy(GameObject):
    """
    Nasty Gustav, follows you around and makes your lawn mowing adventure hell.
    His AI is pretty simple: he makes a B-line towards you until he reaches within kicking distance,
    at which point he will try to kick you into the stratosphere.

    Properties:
        speed
    """

    def __init__(self, *args, **kwargs):
        super(Enemy, self).__init__(*args, **kwargs)

        self.draw_priority = 90  # lower than player by 10
        self.speed = 3.5  # chasing speed, for reference, the player's value is 5
        self.target = None  # the target to chase, this is set after initialization
        # instead of heading for the target's center, where should the enemy head for?
        self.hunt_offset = (self.rect.centerx, self.rect.centery + 40)
        # when enemy will try to kick the lawnmower
        self.kick_distance = 40
        # animation frame
        self.anim = 0
        # animate every X frames
        self.animate_every = 10
        # flip image horizontally?
        self.horizontal_flip = False
        # currently kicking?
        self.kicking = False
        # frames since charge
        self.kick_charge = 0
        # frames required to complete charge
        self.charge_duration = 17
        # is stunned?
        self.stunned = False

    def update(self):
        """
        This function handles the update of the Enemy AI. The `target` parameter must be set to a valid instance
        of GameObject (usually the player).

        Called every frame.
        """

        if self.target is not None and not self.kicking:  # skip calculating the movement if there is no set target
            # get mouse pos
            target_x, target_y = self.target.globalRect.center

            # calculate relative to object
            relative_x = target_x - (self.x + self.hunt_offset[0])
            relative_y = target_y - (self.y + self.hunt_offset[1])

            if int(relative_y - 20) > 0:
                self.draw_priority = 90
            else:
                self.draw_priority = 110

            if self.stunned:
                return

            self.horizontal_flip = relative_x > 0

            # furthest axis
            furthest_distance = max(abs(relative_x), abs(relative_y))

            if furthest_distance > self.kick_distance - 10:
                step_dist_x = (relative_x / furthest_distance) * self.speed  # horizontal step
                step_dist_y = (relative_y / furthest_distance) * self.speed  # vertical step

                # calculate if the enemy can still move smoothly
                if abs(int(relative_x)) >= self.speed:
                    # move one step towards target x
                    self.x += step_dist_x
                else:
                    # the enemy is too close to the player to have a reliable
                    # step calculation because of framerate, just snap to position
                    # this runs on the last frame of the movement
                    self.x = target_x - self.hunt_offset[0]

                # same as above, but for vertical movement
                if abs(int(relative_y)) >= self.speed:
                    self.y += step_dist_y
                else:
                    self.y = target_y - self.hunt_offset[1]
            else:
                self.kick_charge = 0  # start charge loop
                self.kicking = True

        if self.kick_charge > -1:
            if self.kick_charge < self.charge_duration:
                self.kick_charge += 1
            else:
                self.kick_charge = -1

                relative_x = self.target.globalRect.centerx - (self.x + self.hunt_offset[0])
                relative_y = self.target.globalRect.centery - (self.y + self.hunt_offset[1])

                if max(abs(relative_x), abs(relative_y)) <= self.kick_distance * 2:
                    self.parent.kick_player()
                self.kicking = False

    def draw(self, *args, **kwargs):
        if self.stunned:
            self.image = self.parent.textures.enemy_stun
        elif not self.kicking:
            if self.anim % self.animate_every == 0:
                self.image = self.parent.textures.enemy_cycle[int(self.anim / self.animate_every)]

            if self.anim + 1 < len(self.parent.textures.enemy_cycle) * self.animate_every:
                self.anim += 1
            else:
                self.anim = 0
        elif self.kick_charge > -1:
            self.image = self.parent.textures.enemy_kick[0]
        else:
            self.image = self.parent.textures.enemy_kick[1]

        if not self.horizontal_flip:
            super(Enemy, self).draw(
                *args, image=pygame.transform.flip(self.image, True, False)
            )
            return
        super(Enemy, self).draw(*args)


class Powerup(GameObject):
    def __init__(self, *args, **kwargs):
        super(Powerup, self).__init__(*args, **kwargs)
        self.start_y = self.y
        self.type = 0
        self.active = True

    def update(self):
        if self.active:
            self.y = self.start_y + (math.sin(self.parent.frames_since_game_start/10)*3)
            px, py = self.parent.player.globalRect.center

            dist_sq = abs((self.globalRect.centerx-px))**2 + abs((self.globalRect.centery-py))**2

            if dist_sq <= 1024:  # 32^2
                self.trigger()
                # in range
                self.active = False

    def trigger(self):
        self.parent.powerups_used += 1
        if self.type == 0:
            self.parent.player.speed = 10
            self.parent.current_power_consumption = 3000
            self.parent.player.active_powerups[0] = (0, FRAMERATE*10)
        if self.type == 1:
            self.parent.current_cost = self.parent.powered_up_cost
            self.parent.player.active_powerups[1] = (0, FRAMERATE*3)
        if self.type == 2:
            self.parent.objects[1].stunned = True
            self.parent.player.active_powerups[2] = (0, FRAMERATE*5)



class Button(GameObject):
    def __init__(self, parent: Game, start_x, start_y, text: str, image_set: list, callback=None, callback_args=[]):
        super(Button, self).__init__(parent, start_x, start_y, 0, image_set[0])
        self.text = text
        self.image_set = image_set
        self.callback = callback
        self.callback_args = callback_args

        self.font_colors = (
            (60, 63, 65),
            (255, 251, 181),
            (33, 33, 33)
        )
        self.font_color = self.font_colors[0]
        self.pressed = False

    def update(self):
        mx, my = self.parent.mouse_pos

        if self.parent.button_pressed in (None, self):
            # check if mouse is within rect
            hover = (
                self.globalRect.x <= mx <= (self.globalRect.x+self.globalRect.w)
                and
                self.globalRect.y <= my <= (self.globalRect.y+self.globalRect.h)
            )

            asset_idx = 0
            if hover:
                if self.parent.mouse_pressed[0]:
                    asset_idx = 2
                    self.pressed = True
                    self.parent.button_pressed = self
                else:
                    asset_idx = 1
            else:
                asset_idx = 0

            if self.pressed:
                if not self.parent.mouse_pressed[0]:
                    # trigger
                    if hover:
                        self.log(f'Button "{self.text}" pressed.', 0)
                        if self.callback is not None:
                            self.callback(*self.callback_args)

                    self.pressed = False
                    self.parent.button_pressed = None

            asset_idx = asset_idx if not self.pressed else 2
            self.image = self.image_set[asset_idx]
            self.font_color = self.font_colors[asset_idx]

    def draw(self, surface=None, *args, **kwargs):
        if surface is None:
            surface = self.parent.screen

        # force copy of image here by scaling to exact same size
        image = pygame.transform.scale(self.image, self.image.get_size())

        text_surface = self.parent.fonts.arcade_25.render(self.text, False, self.font_color)
        tx = (self.rect.w * 0.5) - (text_surface.get_width() * 0.5)
        ty = (self.rect.h * 0.5) - (text_surface.get_height() * 0.5)

        image.blit(
            text_surface,
            (tx, ty)
        )

        super(Button, self).draw(surface, image)



if __name__ == '__main__':
    # this runs only when the file is the main one
    if USE_ADVANCED_LOGGING:
        # set up advanced logging with levels & debug filtering
        _logger = logging.Logger('game')  # initialize logger object
        _logger.setLevel(logging.DEBUG if ADVANCED_LOGGING_SHOW_DEBUG else logging.INFO)  # set debug filter

        _stdhandler = logging.StreamHandler()  # create handler object to pipe to console
        _stdhandler.setFormatter(  # set the logger message & time format
            logging.Formatter('%(asctime)s [%(levelname)s] : %(message)s', '%d/%m/%Y %H:%M:%S')
        )
        _logger.addHandler(_stdhandler)  # add the console handler to the logger
    else:
        _logger = None  # tell the game to use fallback logging

    game = Game(logger=_logger)  # initialize game
    game.log('Starting game...')
    try:
        rcode = game.run_forever()  # run the game forever, then get return code
    except Exception as e:
        # an error has occurred
        game.log(str(e), 3)  # log the error

        if ADVANCED_LOGGING_SHOW_DEBUG:  # show the traceback if enabled, for convenience purposes
            game.log(f'Showing traceback, disable DEBUG to hide.\n\n{"-" * 9} BEGIN DEBUG TRACEBACK {"-" * 9}\n', 0)
            traceback.print_exception(type(e), e, e.__traceback__)
else:
    # this file was imported for some reason, this shouldn't really happen, so:
    print('This file does nothing unless explicitly executed.')
    input('[Press Enter to exit.]')