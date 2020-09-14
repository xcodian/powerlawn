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
# filesystem operations
import os
# vector math
import math
# timestamp management
import time
# random generation
import random
# error handling
import traceback
# hide pesky warnings
import warnings
# sane console logging
import logging
# open links
import webbrowser

# don't change this
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
TARGET_FRAMERATE = 60
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
        Main game object that should take care of most of the game logic such as score, keeping track of objects
        and calling their update methods.

        Parameters:
            logger (logging.Logger): the logger to use, if not specified, it will use print sattements
        """
        # is the game running?
        self.running = False
        # the game's logger
        self.logger = logger

        # frame where the playing field is
        self.frame: pygame.Surface = pygame.Surface((FRAME_W, FRAME_H))
        # screen
        self.screen: pygame.Surface = None  # initialized later

        # framerate cap clock
        self.screen_clock = None
        # timestamp of when the last frame was rendered
        self.last_frame = 0
        # delta time in seconds of how long rendering the last frame took
        self.frame_delta = 0

        # list of GameObject's to get ticked
        self.objects = []
        # dict of events and their corresponding functions to be run during gameplay
        self.event_callback_ingame = {
            pygame.QUIT: self.event_quit,
            pygame.KEYUP: self.event_key,
            pygame.KEYDOWN: self.event_key
        }
        # dict of events and their corresponding function to be run in menu only
        self.event_callback_menu = {
            pygame.QUIT: self.event_quit
        }
        # currently pressed down keys
        self.keys_down = []

        # textures to load
        self.textures = None
        # fonts to load
        self.fonts = None
        # sounds to load
        self.sounds = None

        # background tile grid array
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

        # money before the game ends and you exaust your money supply
        self.money_limit = 5000
        # money currently spent
        self.money = 0

        # cost per watt
        self.current_cost = 0.0010
        # normal_cost
        self.normal_cost = 0.0010
        # powered up cost
        self.powered_up_cost = -0.0010

        # Watts if slowed
        self.slow_power_consumption = 2400
        # Watts if not slowed
        self.normal_power_consumption = 800
        # power consumption every frame
        self.current_power_consumption = self.normal_power_consumption

        # time the game was started
        self.time_started = 0
        # frames rendered since the game has started
        self.frames_since_game_start = 0
        # last powerup usage timestamp
        self.last_powerup_used_at = 0
        # how many powerups were used?
        self.powerups_used = 0
        # self explanatory, powerup names keyed to their ID's
        # note: powerups not listed here will not be spawned or registered
        self.powerup_names = {
            0: 'Swiftness',
            1: 'Anti-Debt',
            2: 'Human Zapper'
        }

        # is the game in a paused state?
        # note: this is True even in the game over screen
        self.paused = False
        # has the game started or is it in the main menu
        self.game_started = False
        # has the game ended, and should the game over screen be shown?
        self.game_over = False
        # the dedicated pause button
        self.pause_button = None

        # mouse cursor position within the screen
        self.mouse_pos = (0, 0)
        # mouse buttons pressed
        self.mouse_pressed = (False, False, False)

        # current UI button pressed down (prevents others triggering events)
        self.button_pressed = None

        # page of the main menu currently accessed
        # 0 = main, 1 = how to play, 2 = credits
        self.main_menu_page = 0

        # old game objects buffer, so it can be restored after the pause menu
        self.game_objects = []

    class Textures:
        """
        Class to hold all of the game's required textures.
        Initialize to load them.

        Attributes:
            base_tile_size : int
                Small background tile size (always square, represents w and h)
            base_bg_tile_size : int
                Large background tile size (always square, represents w and h)
            base_enemy_size : Tuple[int, int]
                Size of the enemy texture
            base_player_size : Tuple[int, int]
                Size of the player texture

            tile_dev : Surface
                Development tile texture
            tile_empty : Surface
                Empty tile texture (brown)
            tile_half : Surface
                Half-mown tile texture (green/brown)

            tile_mappings : List[Optional(Surface)]
                Tile textures mapped to indexes

                In order of indices:
                    * None (transparent)
                    * Empty Tile
                    * Half Tile
                    * Dev Tile (unused)

            player : Surface
                The player's texture.
                Scaled to the base player texture size

            tile_bg_grass : Surface
                Singluar big grass tile.
                Replicated for entire background
            screen_full_bg : Surface
                Replicated background of big tiles to fit entire screen
            full_bg : Surface
                Replicated background of big tiles to fit frame

            enemy_kick : Tuple[Surface]
                Animation frames sourced for enemy kick animation
                Scaled to base enemy size
            enemy_run : Tuple[Surface]
                Animation frames sourced for enemy run animation
                Scaled to base enemy size
            enemy_stun : Surface
                Texture for the enemy when stunned
                Scaled to base enemy size

            wallet_icon : Surface
                Small wallet icon displayed next to progress bar

            powerups : Tuple[Surface]
                List of powerup textures mapped to their correct indexes
            powerup_icons : Tuple[Surface]
                powerup textures scaled down to fit UI text

            title : Surface
                Game opening font render

            button : Surface
                300 x 32 large button texture
            button_small: Surface
                32 x 32 small button texture

            bg_frame : Surface
                "Popup" window background, used in credits, how to play, game over & pause menus

            keycaps : Tuple[Surface]
                Keycap textures, used in how to play screen
        """
        def __init__(self):
            # base size for small tiles
            self.base_tile_size = 10
            # base size for big tiles
            self.base_bg_tile_size = 60
            # size enemy texture is resized to
            self.base_enemy_size = (100, 200)
            # size player texture is resized to
            self.base_player_size = (150, 60)

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

            # background tile
            self.tile_bg_grass = pygame.transform.scale(
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'tiles', 'bgtile.png')
                ), (self.base_bg_tile_size, self.base_bg_tile_size)
            )

            # player sprite
            self.player = pygame.transform.scale(
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'char.png')
                ), self.base_player_size
            )

            # replicated background that should fill the frame, see Game.bake_background_texture
            self.full_bg = None
            # replicated background that should fill the screen, see Game.bake_background_texture
            self.screen_full_bg = None

            # enemy kicking cycle
            self.enemy_kick = [
                pygame.transform.scale(
                    pygame.image.load(
                        os.path.join(RES_FOLDER, 'img', 'enemy', f'kick{i}.png')
                    ), self.base_enemy_size
                )
                for i in (0, 1)
            ]

            # enemy running cycle
            self.enemy_run = [
                pygame.transform.scale(
                    pygame.image.load(
                        os.path.join(RES_FOLDER, 'img', 'enemy', f'run{i}.png')
                    ), self.base_enemy_size
                )
                for i in (0, 1, 2, 1)
            ]

            # enemy stunned frame
            self.enemy_stun = pygame.transform.scale(
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'enemy', 'stun.png')
                ), self.base_enemy_size
            )

            # wallet UI icon
            self.wallet_icon = pygame.image.load(
                os.path.join(RES_FOLDER, 'img', 'wallet.png')
            )

            # powerup textures
            self.powerups = (
                pygame.image.load(os.path.join(RES_FOLDER, 'img', 'powerups', 'speed.png')),
                pygame.image.load(os.path.join(RES_FOLDER, 'img', 'powerups', 'money.png')),
                pygame.image.load(os.path.join(RES_FOLDER, 'img', 'powerups', 'stun.png')),
            )

            # powerup textures resized to be smaller; icons
            self.powerup_icons = [
                pygame.transform.scale(i, (25, 25)) for i in self.powerups
            ]

            # main menu title
            self.title = pygame.image.load(
                os.path.join(RES_FOLDER, 'img', 'title.png')
            )

            # large button texture
            self.button = [
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'ui', 'button', f'{i}.png')
                )
                for i in (0, 1, 2)
            ]

            # small, square button
            self.button_small = [
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'ui', 'smallbutton', f'{i}.png')
                )
                for i in (0, 1, 2)
            ]

            # popup background
            self.bg_frame = pygame.image.load(
                os.path.join(RES_FOLDER, 'img', 'ui', 'frame.png')
            )

            # keycap sprites, used in how to play
            self.keycaps = [
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'ui', 'keycaps', f'{i}.png')
                )
                for i in ('a', 'd')
            ]

    class Fonts:
        """
        Class to hold all of the game's required fonts.
        Initialize to load them.

        Attributes:
            path_arcade : str
                Absolute path to the Arcade font ttf

            arcade_50 : Font
                50pt Arcade Font
            arcade_25 : Font
                50pt Arcade Font
        """
        def __init__(self):
            # Arcade ttf path
            path_arcade = os.path.join(
                RES_FOLDER, 'fonts', 'arcade.ttf'
            )
            # 50pt Arcade
            self.arcade_50 = pygame.font.Font(
                path_arcade, 50
            )
            # 25pt Arcade
            self.arcade_25 = pygame.font.Font(
                path_arcade, 25
            )

    class Sounds:
        """
        Class to hold all of the game's required sounds.
        Initialize to load them.

        Attributes:
            sound_volume : float
                Volume of all of the loaded WAVE sounds

            music : Sound
                Background music loop during gameplay, looped forever
            select : Sound
                SFX when a button is clicked & when player lands from kick
            kick : Sound
                SFX when player is kicked
            pickup : Sound
                SFX when player picks up a powerup
        """
        def __init__(self):
            # sound volume scale
            self.sound_volume = 0.1

            # load background music
            self.music = pygame.mixer.Sound(
                os.path.join(RES_FOLDER, 'sfx', 'music.wav')
            )
            self.music.set_volume(self.sound_volume)  # scale sound down to volume

            # load button click sfx
            self.select = pygame.mixer.Sound(
                os.path.join(RES_FOLDER, 'sfx', 'select.wav')
            )
            self.select.set_volume(self.sound_volume)  # scale sound down to volume

            # load kicking sfx
            self.kick = pygame.mixer.Sound(
                os.path.join(RES_FOLDER, 'sfx', 'kick.wav')
            )
            self.kick.set_volume(self.sound_volume)  # scale sound down to volume

            # load powerup pickup sfx
            self.pickup = pygame.mixer.Sound(
                os.path.join(RES_FOLDER, 'sfx', 'pickup.wav')
            )
            self.pickup.set_volume(self.sound_volume)  # scale sound down to volume

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
        """
        Returns the first element in the objects array.
        Since this should always be the player during gameplay, this is a shortcut.
        """
        if len(self.objects):  # only do it if there's enough objects
            r = self.objects[0]
            if isinstance(r, Player):  # do not return it if it isn't a player
                return r
        return None  # return nothing otherwise

    # ---------------- Essential ----------------

    def update_delta(self):
        """Synchronise the frame timedelta for the last frame."""
        now = time.time()
        self.frame_delta = now - self.last_frame
        self.frame_delta = self.frame_delta * TARGET_FRAMERATE
        self.last_frame = now

    def run_forever(self):
        """
        Initialize and run the game forever until it quits.
        If this function returns, then the game has ended.
        Returns the exit code for the game, run this last.
        Raises any exception that occurred during any part of the game.
        """
        # load the textures
        self.log('Loading textures...')
        self.textures = self.Textures()

        # load the fonts
        self.log('Loading fonts...')
        pygame.font.init()
        self.fonts = self.Fonts()

        # load sounds
        self.log('Loading sounds...')
        pygame.mixer.init()
        self.sounds = self.Sounds()

        # init the screen and prepare it
        self.log(f'Initializing screen ({SCREEN_W}x{SCREEN_H})')
        pygame.init()
        # set title
        pygame.display.set_caption(f'Power Lawn v{VERSION}')
        # set display size and make it double buffered for performance improvements
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.DOUBLEBUF)
        # create the frame clock, which limits the framerate down to TARGET_FRAMERATE
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

        # create main menu objects & set up
        self.log(f'Setting up main menu...')
        self.prepare_main_menu()

        # finally, start the game
        self.log('Starting event loop...')
        self.running = True

        # set initial value for last frame timestamp
        self.last_frame = time.time()
        # set initial value for powerup timestamp
        self.last_powerup_used_at = self.last_frame

        while self.running:  # main loop, run while game is up
            self.update_delta()  # update the frame delta

            # update mouse state
            self.mouse_pos = pygame.mouse.get_pos()
            self.mouse_pressed = pygame.mouse.get_pressed()

            if self.game_started:
                # the game is not in the main menu
                if not self.paused:
                    # the game has begun and is in the middle of gameplay

                    # call all update methods of objects
                    self.tick_objects()
                    # tick the timeout of active powerups
                    self.tick_active_powerups()
                    # draw everything
                    self.full_draw()
                    # process the event queue
                    self.process_events(pygame.event.get())
                    # try to spawn a powerup
                    self.try_spawn_powerup()

                    if self.paused:
                        # the above process ended in some function overriding the paused value
                        # so enter the pause menu ready for the next loop
                        self.enter_pause_menu()
                else:
                    # the game is in the pause menu
                    self.draw_pause_menu()
                    self.process_events(pygame.event.get())
            else:
                # the game is in the main menu
                self.draw_main_menu()
                # process the event queue in the main menu
                self.process_events(pygame.event.get())
            # limit the framerate to 60fps (VSYNC double buffer)
            self.screen_clock.tick(TARGET_FRAMERATE)
        # no errors, the function will raise an error otherwise
        self.log('Game exited normally', 0)
        return 0

    def start_game(self, e=None):
        """
        Starts the actual gameplay part of the game.
        Can be binded to an event, but usually used by a Button's callback.

        Arguments:
            e (Optional[Event]): the event callee
        """
        self.log('Preparing game...')

        # make the big tile array
        self.log('Baking initial tilemap...')
        self.bake_tile_grid()

        # create the game objects seen during gameplay
        self.log(f'Creating objects...')
        self.objects = [
            # slot 0 should always be the main player
            Player(parent=self, start_x=-45, start_y=0, start_angle=0, image=self.textures.player),
            # start off with an enemy
            Enemy(parent=self, start_x=500, start_y=500, start_angle=0, image=self.textures.enemy_kick[0]),
        ]
        # pause button visible during gameplay
        self.pause_button = Button(self, self.frame.get_width()+20, self.screen.get_height()-74, 'P', self.textures.button_small, self.set_paused)

        self.log(f'{len(self.objects):,} objects active', 0)

        # set enemy target
        self.objects[1].target = self.player

        # play & loop the music forever
        self.sounds.music.play(loops=100)

        # mark this point at which the game started
        self.time_started = time.time()

        # tell the mainloop to start updating the gameplay
        self.game_started = True

    # ---------------- Main Menu ----------------

    def prepare_main_menu(self):
        """Ready the main menu's game objects depending on its page."""
        if self.main_menu_page == 0:
            # Title Screen
            self.objects = [
                Button(self, 100, 440, 'Start', self.textures.button, self.start_game),
                Button(self, 100, 520, 'How to Play', self.textures.button, self.switch_main_menu_page, [1]),
                Button(self, 100, 600, 'Credits', self.textures.button, self.switch_main_menu_page, [2])
            ]
        elif self.main_menu_page == 2:
            # Credits Screen
            self.objects = [
                Button(self, self.screen.get_width() / 2 - 150, 450, 'GitHub', self.textures.button, open_github),
                Button(self, self.screen.get_width() / 2 - 150, 620, 'Back', self.textures.button, self.switch_main_menu_page, [0])
            ]
        else:
            # How to Play Screen
            self.objects = [
                Button(self, self.screen.get_width() / 2 - 150, 620, 'Back', self.textures.button, self.switch_main_menu_page, [0])
            ]

    def draw_main_menu(self):
        """Draws the main menu's next frame."""
        # clear the screen by drawing the tiled background
        self.screen.blit(self.textures.screen_full_bg, (0, 0))

        if self.main_menu_page == 0:  # title screen
            # show the title texture only, the buttons are already ticked from objects array
            self.screen.blit(self.textures.title, (0, 0))

        elif self.main_menu_page == 1:  # how to play screen

            instructions = """
You've one job: mow the lawn!
Easy, right? Not quite. You're 
one of those new "smart" lawnmowers.
You're quite power hungry, so
try to do it as fast as possible.
Oh, also, don't get caught by 
your owner. He won't hesitate.
"""
            # show an info screen with the instructions
            self.show_info_screen('How To Play', instructions)

            # add some extra text for controls, leave gaps to fit textures
            control_text = self.fonts.arcade_25.render('Use   and   to turn the lawnmower.', False, (61, 64, 66))
            # find middle of said control help text
            control_text_x = (self.screen.get_width() / 2) - (control_text.get_width() * 0.5)
            # render control help text
            self.screen.blit(
                control_text,
                (control_text_x, 460)
            )
            # draw the keycap textures relative to the control help text middle
            self.screen.blit(self.textures.keycaps[0], (control_text_x + 70, 440))
            self.screen.blit(self.textures.keycaps[1], (control_text_x + 220, 440))

        elif self.main_menu_page == 2:  # credits screen
            credits_text = f"""
            Version {VERSION}            

All programming, visual & SFX by
me. Created for Year 10 Technology
school assignment at GIHS. Game 
music credited on GitHub.

By Martin Velikov (xxcodianxx)
"""
            # show an info screen with the credits
            self.show_info_screen(f'Power Lawn', credits_text)

        # tick the buttons
        self.tick_objects()
        # draw the buttons
        self.draw_objects()

        # update the entire display
        pygame.display.update()

    def switch_main_menu_page(self, page):
        """
        Helper function to change the main menu page & update it
        once for a smooth transition.

        Parameters:
            page (int): the page ID to switch to
        """
        # set the page
        self.main_menu_page = page
        # prepare objects in page
        self.prepare_main_menu()
        # draw it
        self.draw_main_menu()

    def show_info_screen(self, title, description):
        """
        Helper function to draw an info screen with a nice looking title & description.

        Parameters:
            title (str): The window title
            description (str): The window description
        """
        # find middle of screen
        middle = self.screen.get_width() / 2
        # draw a window frame to the middle of the screen
        self.screen.blit(
            self.textures.bg_frame,
            # offset frame by half its width to fit properly
            (middle - (self.textures.bg_frame.get_width() * 0.5), 50)
        )

        # render the title in large font
        title = self.fonts.arcade_50.render(title, False, (61, 64, 66))
        # render said font to middle
        self.screen.blit(
            title,
            # offset to middle
            (middle - (title.get_width() * 0.5), 80)
        )

        # for every line in the description
        for idx, line in enumerate(description.splitlines()):
            # render the line in small text
            line_text = self.fonts.arcade_25.render(line, False, (61, 64, 66))
            # draw it at the offset coordinate, influenced by idx which is the line number
            self.screen.blit(
                line_text,
                # offset to middle, offset by multiplying by idx
                (middle - 400, 150 + (30 * idx))
            )

    # ---------------- Pause Menu ----------------

    def set_paused(self):
        """Helper function to only set the paused variable, so it can be binded to callbacks"""
        self.paused = True

    def enter_pause_menu(self):
        """Helper function to cleanup objects & prepare for entry into the pause/G.O. menu"""
        # backup gameplay objects for restoration on continue
        self.game_objects = self.objects
        if self.game_over:  # is the pause menu continuable or permanent?
            # it's a game over menu, do not allow continuation
            self.objects = [
                Button(self, self.screen.get_width() / 2 - 150, 620, 'Continue', self.textures.button, self.reset_to_main_menu),
            ]
        else:
            # it's a regular pause menu, allow continuation
            self.objects = [
                Button(self, self.screen.get_width() / 2 - 350, 620, 'Main Menu', self.textures.button, self.reset_to_main_menu),
                Button(self, self.screen.get_width() / 2 + 50, 620, 'Continue', self.textures.button, self.continue_game)
            ]
        # stop the music
        self.sounds.music.stop()

    def draw_pause_menu(self):
        """Draw the pause menu with whatever contents are required"""
        # draw the full screen bg
        self.screen.blit(self.textures.screen_full_bg, (0, 0))

        if not self.game_over:
            # the pause menu is a regular one

            # show a base info screen
            self.show_info_screen('Paused', '       The game is paused.')

            # mini-frame scaled size
            newsize = (300, 300)
            # offset coordinates of mini-frame
            newpos = (self.screen.get_width() / 2 - newsize[0]*0.5, 200)
            # size of border around mini-frame
            margins = (4, 4)

            # draw the border from the margins, offset by newpos
            pygame.draw.rect(self.screen, 0x010101, pygame.Rect(
                newpos[0] - (margins[0] * 0.5),
                newpos[1] - (margins[1] * 0.5),
                newsize[0] + (margins[0]),
                newsize[1] + (margins[1])
            ))
            # draw a scaled-down version of the frame
            self.screen.blit(pygame.transform.scale(self.frame, newsize), newpos)
        else:
            # draw the game over screen instead
            self.draw_game_over_screen()

        # tick buttons
        self.tick_objects()
        # draw buttons
        self.draw_objects()

        # update display
        pygame.display.update()

    def continue_game(self):
        """Continue the game from where it left off, exit pause menu."""
        self.objects = self.game_objects  # restore gameplay objects from backup
        self.paused = False  # tell the mainloop to unpause
        self.sounds.music.play()  # music, maestro!

    def reset_to_main_menu(self):
        """Reset all game states and return to the main menu."""
        self.money = 0  # clear money
        self.current_power_consumption = self.normal_power_consumption  # reset power consumption
        self.paused = False  # initial state
        self.main_menu_page = 0  # show title screen
        self.frames_since_game_start = 0  # game started just now
        self.current_cost = self.normal_cost  # reset cost
        self.power_used = 0  # reset power usage
        self.game_started = False  # the game hasn't started, still in main menu
        self.game_over = False  # the game hasn't entered a game over state yet, for it is in the main menu

        # tell the main menu to get ready, it's show time! ...literally.
        self.prepare_main_menu()

    # ---------------- Game Over ----------------

    def set_game_over(self):
        """Set the state of the game to indicate a game over"""
        self.paused = True  # tell the pause screen to show, it will redirect to the game over screen
        self.game_over = True  # tell the pause screen & mainloop that the game has ended
        self.duration = time.time() - self.time_started  # calculate the duration to be used in the end screen

    def draw_game_over_screen(self):
        """Draw the game over screen & show stats."""
        percent, mown = self.get_mown_percentage()  # get how much of the lawn was mown

        # reason for game over
        msg = 'You ran out of money!'
        if percent == 100:
            # on the rare occasion that the player is an absolute beast
            msg = 'You mowed the entire lawn!'

        # statistics text
        stat = f'''
{msg}

Lawn Covered: {format(percent, ".2f")}%
Tiles Mown: {mown}
Power Used: {self.power_used}W
Powerups Consumed: {self.powerups_used}

You were alive for {int(self.duration)} seconds.

Have another shot, will ya?
'''

        self.show_info_screen('Game Over', stat)  # show a simple info screen that shows the stats

        # no need to update screen & tick objects, since this function is called from the pause menu update one

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
        self.tile_grid = []  # reset the tile grid
        self.tile_grid_h = 0  # reset the recorded height
        # set the width to that of the first element
        self.tile_grid_w = divmod(self.frame.get_width(), self.textures.base_tile_size)[0]

        # range acting as a divmod
        for _ in range(0, self.frame.get_height(), self.textures.base_tile_size):
            # append a row of 0's until row index exausted by range()
            self.tile_grid.append(
                [0 for _ in range(0, self.frame.get_width(), self.textures.base_tile_size)]
            )
            # add one to height
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

        Parameters:
            size (Optional[Tuple(int, int)]): what size to bake the bg texture to
        """
        # create surface large enough to house texture
        bg = pygame.Surface(size)

        # blit tile texture to larger texture
        for y in range(0, size[1], self.textures.base_bg_tile_size):
            for x in range(0, size[0], self.textures.base_bg_tile_size):
                # rotate by a random 90 degrees to make it feel more organic
                tile = pygame.transform.rotate(
                    self.textures.tile_bg_grass, random.choice((0, 90, 180, 270))
                )
                bg.blit(tile, (x, y))  # add a tile at those screenspace coords

        return bg  # return the stitched texture

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

                # calculate index inverting mutlipliers (-1, 1)
                right = player_cell_x + qx
                left = player_cell_x - qx
                bottom = player_cell_y + qy
                top = player_cell_y - qy

                quads = (  # quadrants for flipping the tilemap
                    (bottom, right),
                    (bottom, left),
                    (top, left),
                    (top, right)
                )

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

    def tick_objects(self):
        """Update all game objects & cull picked up powerups."""
        to_cull = []  # list of objects to be deleted
        for idx, game_object in enumerate(self.objects):
            game_object.update()  # update object

            if isinstance(game_object, Powerup):
                if not game_object.active:  # check if powerup is active
                    to_cull.append(idx)  # if it isn't, then add it to the delete list

        # delete all objects in the killing list
        for idx in to_cull:
            del self.objects[idx]

    def tick_active_powerups(self):
        """
        Keeps the duration of active powerups in check.
        Resets their benefits if they have expired.
        """
        to_cull = []  # list of objects to be deleted
        for powerup, times in self.player.active_powerups.items():
            # iterate through powerup class and the allowed lifetime
            current, max_allowed = times
            if current >= max_allowed:  # the powerup needs to be deleted, it has expired on the player
                to_cull.append(powerup)
                continue
            # otherwise, add the time the powerup has been alive since the last frame to its information.
            self.player.active_powerups[powerup] = (current + (self.frame_delta / TARGET_FRAMERATE), max_allowed)

        # delete unneeded powerups & reset their bonus effects
        for idx in to_cull:
            if idx == 0:  # reset speed, power consumption
                self.player.speed = 5
                self.current_power_consumption = self.normal_power_consumption
            elif idx == 1:  # reset cost
                self.current_cost = self.normal_cost
            elif idx == 2:  # un-stun the enemy
                self.objects[1].stunned = False
            # finally, delete the powerup from the active list
            del self.player.active_powerups[idx]

    def try_spawn_powerup(self, every=10):
        """
        Try to spawn a power-up at a random location.

        Parameters:
            every (int): succeed in spawning every X seconds
        """
        if time.time() - self.last_powerup_used_at > every:  # has it been more than the spawn time since the last powerup spawn?
            type = random.randint(0, len(self.powerup_names.keys())-1)  # if yes, pick one from the registered ones

            # get a random cell x and y
            cx = random.randint(0, self.tile_grid_w - 6)
            cy = random.randint(0, self.tile_grid_h - 6)

            # make the cell x, y into screenspace coordinates by multiplying times the base tile size
            ss_x = cx * self.textures.base_tile_size
            ss_y = cy * self.textures.base_tile_size
            self.log(f'Spawning powerup type {type} at {ss_x}, {ss_y}', 0)

            # create and prepare Powerup instance
            instance = Powerup(self, ss_x, ss_y, 0, self.textures.powerups[type])
            # set its type
            instance.type = type
            # set its draw priority to be lower than normal
            instance.draw_priority = 10

            # add it to the object list to get ticked
            self.objects.append(instance)
            # mark the time of spawning
            self.last_powerup_used_at = time.time()

    # ---------------- Rendering ----------------

    def full_draw(self):
        """Draw everything gameplay-related to the screen."""
        self.draw_tilemap()
        self.draw_objects()
        self.draw_ui_and_frame()
        self.frames_since_game_start += 1

    def draw_tilemap(self):
        """
        Render the tilemap to the screen.
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
        """Draws all game objects to the screen by calling their draw method."""
        for game_object in sorted(self.objects, key=lambda x: x.draw_priority):
            game_object.draw()

    def draw_ui_and_frame(self):
        """
        Takes care of what everything looks like outside the frame window during gameplay time.
        Assumes everything inside the frame is ready to go.
        Refreshes the screen this should be the final function call per frame.
        """
        # fill the screen with a bg color
        self.screen.fill(0x262626)

        # get how much of the lawn is completed
        percent, mown = self.get_mown_percentage()
        if percent == 100:
            # the player managed to mow the entire lawn, trigger a game over
            self.set_game_over()

        # show lawn mowing statistics
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

        # power usage & cost display
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

        # progress bar
        self.screen.blit(self.textures.wallet_icon, (self.frame.get_width() + 30, 180 + cost_font.get_height()))

        rectx = self.frame.get_width() + 88
        recty = 188 + cost_font.get_height()

        pygame.draw.rect(self.screen, (111, 194, 52), pygame.Rect(rectx, recty, 300, 32))

        # clamp value down from 0 to 1
        percent = self.money / self.money_limit
        if percent < 0:
            percent = 0
        elif percent > 1:
            percent = 1

        # draw the rect
        pygame.draw.rect(self.screen, (199, 84, 80), pygame.Rect(
            rectx, recty,
            int(percent * 300),  # <- bar width
            32
        ))

        # show active powerups
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
                seconds_left = max_time-current
                # show 0 seconds instead of negative for 1 frame
                seconds_left = seconds_left if seconds_left >= 0 else 0
                self.screen.blit(
                    self.fonts.arcade_25.render(f'{self.powerup_names[id]} {format((seconds_left), ".2f")}s', False, (255, 255, 255)),
                    (basex+35, y_offset)
                )
                offset_mult += 1

        # update & draw the pause button
        self.pause_button.update()
        self.pause_button.draw()

        # finally, draw the frame
        self.screen.blit(self.frame, (10, 10))
        # update the screen
        pygame.display.update()

    # ---------------- Events & Processing ----------------

    def process_events(self, queue: tuple = ()):
        """
        Run through the event queue and resolve all events to their callbacks.
        Does not mind which callback is used, uses all available

        Parameters:
            queue : Optional(Tuple[Event]): the event queue
        """

        if queue == ():  # save a bit of processing power
            return

        # get the correct binding dictionary for the main menu or ingame game state
        callback_mapping = (self.event_callback_ingame if self.game_started else self.event_callback_menu)

        for e in queue:
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

    def kick_player(self, duration_seconds=1):
        """Kick the player in a random direction"""
        # get player vector
        v_player = Vector2(self.player.x, self.player.y)
        # get distance to right side of frame
        dist_to_right = int(self.frame.get_width() - self.player.x)
        # get distance to bottom of frame
        dist_to_bottom = int(self.frame.get_height() - self.player.y)

        # get relative offset from current player pos
        offset = Vector2(
            random.randint(int(-self.player.x) + 100, dist_to_right - 100),
            random.randint(int(-self.player.y) + 100, dist_to_bottom - 100)
        )

        # orient the enemy the correct way around
        self.objects[1].horizontal_flip = not (offset.x < 0)
        end_pos = v_player + offset  # get end position for lerp

        self.sounds.kick.play()  # play the kicking sfx

        # TODO: make this framerate independent
        for i in range(TARGET_FRAMERATE):
            # update the last frame
            self.update_delta()
            # spherical lerp the player's x and y to go towards the end pos
            self.player.x, self.player.y = v_player.slerp(end_pos, i / TARGET_FRAMERATE)
            # multiply the player's angle randomly
            self.player.angle += random.randint(5, 8) * self.frame_delta  # 360 / 50
            # tick the powerup timers
            self.tick_active_powerups()
            # draw everything
            self.full_draw()
            # limit framerate
            self.screen_clock.tick(TARGET_FRAMERATE)
        # player lands back on ground, play landing sfx (select)
        self.sounds.select.play()

    def get_mown_percentage(self):
        """Helper function to return how much of the lawn is mown."""
        mown = 0
        for r in self.tile_grid:
            for c in r:
                if c:
                    mown += 1
        return (mown / (70 * 70)) * 100, mown


class GameObject(pygame.sprite.Sprite):
    """
    Universal GameObject class to be inherited & overriden by specific objects.

    Attributes:
        draw_priority : int
            When should this object be drawn in relation to others: higher than other = before

        x, y : int, int
            The topleft corner coordinates of the GameObject.
        angle : float
            The global angle of the GameObject image.
        rect : Rect
            Local image rect of the sprite.
        globalRect : Rect
            Global rect of image mimicing rect, offset by global coordinates

    """
    def __init__(self, parent: Game, start_x=0, start_y=0, start_angle=0, image=None):
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
                self.angle -= self.turnspeed * self.parent.frame_delta
            if self.key_left in self.parent.keys_down:
                self.angle += self.turnspeed * self.parent.frame_delta
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
                # pygame.draw.circle(self.parent.frame, 0xff0000, tuple(map(int, global_vector)), 10)

            # calculate the true speed based on slowdown, use self.speed if no slowdown
            if is_slowed_down:
                real_speed = (self.speed / 2)
                if self.parent.current_power_consumption == self.parent.normal_power_consumption:
                    self.parent.current_power_consumption = self.parent.slow_power_consumption
            else:
                real_speed = self.speed
                if self.parent.current_power_consumption == self.parent.slow_power_consumption:
                    self.parent.current_power_consumption = self.parent.normal_power_consumption
            self.parent.power_used += int((self.parent.current_power_consumption / TARGET_FRAMERATE) * self.parent.frame_delta)

            real_speed = real_speed * self.parent.frame_delta

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
        # kick charge
        self.kick_charge_seconds_elapsed = -1
        # charge duration in seconds
        self.kick_charge_duration = 0.5
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
                step_dist_x = (relative_x / furthest_distance) * self.speed * self.parent.frame_delta  # horizontal step
                step_dist_y = (relative_y / furthest_distance) * self.speed * self.parent.frame_delta  # vertical step

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
                self.kick_charge_seconds_elapsed = 0 # start charge loop
                self.kicking = True

        if self.kick_charge_seconds_elapsed > -1:
            if self.kick_charge_seconds_elapsed < self.kick_charge_duration:
                self.kick_charge_seconds_elapsed += self.parent.frame_delta / TARGET_FRAMERATE
            else:
                self.kick_charge_seconds_elapsed = -1

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
                self.image = self.parent.textures.enemy_run[int(self.anim / self.animate_every)]

            if self.anim + 1 < len(self.parent.textures.enemy_run) * self.animate_every:
                self.anim += 1
            else:
                self.anim = 0
        elif self.kick_charge_seconds_elapsed > -1:
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

            dist_sq = abs((self.globalRect.centerx - px)) ** 2 + abs((self.globalRect.centery - py)) ** 2

            if dist_sq <= 1024:  # 32^2
                self.trigger()
                # in range
                self.active = False

    def trigger(self):
        self.parent.powerups_used += 1
        self.parent.sounds.pickup.play()
        if self.type == 0:
            self.parent.player.speed = 10
            self.parent.current_power_consumption = 3000
            self.parent.player.active_powerups[0] = (0, 10)
        if self.type == 1:
            self.parent.current_cost = self.parent.powered_up_cost
            self.parent.player.active_powerups[1] = (0, 5)
        if self.type == 2:
            self.parent.objects[1].stunned = True
            self.parent.player.active_powerups[2] = (0, 5)


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
                    self.globalRect.x <= mx <= (self.globalRect.x + self.globalRect.w)
                    and
                    self.globalRect.y <= my <= (self.globalRect.y + self.globalRect.h)
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
                        self.parent.sounds.select.play()
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