'''
██████╗  ██████╗ ██╗    ██╗███████╗██████╗ ██╗      █████╗ ██╗    ██╗███╗   ██╗
██╔══██╗██╔═══██╗██║    ██║██╔════╝██╔══██╗██║     ██╔══██╗██║    ██║████╗  ██║
██████╔╝██║   ██║██║ █╗ ██║█████╗  ██████╔╝██║     ███████║██║ █╗ ██║██╔██╗ ██║
██╔═══╝ ██║   ██║██║███╗██║██╔══╝  ██╔══██╗██║     ██╔══██║██║███╗██║██║╚██╗██║
██║     ╚██████╔╝╚███╔███╔╝███████╗██║  ██║███████╗██║  ██║╚███╔███╔╝██║ ╚████║
╚═╝      ╚═════╝  ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═══╝
                            by Martin Velikov
'''
VERSION = '1.0'

# incorporate level-based logging instead of unfiltere print
USE_ADVANCED_LOGGING = True
# show debug prints? warning: spams console
ADVANCED_LOGGING_SHOW_DEBUG = True
# screen dimensions
FRAME_W = 700
FRAME_H = 700
# frame dimensions
SCREEN_W = 1280
SCREEN_H = 720
# resources folder
RES_FOLDER = 'res'

import os
import math
import time
import traceback
import logging
import warnings

# hide DeprecationWarning for float coordinate movement
warnings.filterwarnings("ignore", category=DeprecationWarning)
# hide the annoying prompt message pygame comes with
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame # the one and only


def is_point_in_circle(point: tuple, center: tuple, radius: int):
    px, py = point
    cx, cy = center

    diff_x = abs(cx - px)
    diff_y = abs(cy - py)

    if (diff_y > radius) or (diff_x > radius):
        return False

    dist = diff_x * diff_x + diff_y * diff_y
    if round(dist) > radius * radius:
        return False
    return True


class Game:
    def __init__(self, logger: logging.Logger = None):
        """
        Base Game which takes care of the logic. Manages and updates its objects.
        There should really be only one of these at any time.
        :param logger: the logger to use, if not specified, it will use print sattements
        """
        self.running = False  # is the game running?
        self.logger = logger

        # frame where the playing field is
        self.frame: pygame.Surface = pygame.Surface((FRAME_W, FRAME_H))
        # screen
        self.screen: pygame.Surface = None # initialized later

        self.screen_clock = None

        self.objects = []

        # dict of events and their corresponding functions to be run when caught
        self.event_callback = {
            pygame.QUIT: self.game_quit,
            pygame.KEYUP: self.process_key,
            pygame.KEYDOWN: self.process_key
        }

        self.keys_down = []
        self.textures = self.Textures()

        self.tile_gird = []
        self.path_radius = 2

    class Textures:
        def __init__(self):
            self.base_tile_size = 10

            # tiles
            self.tile_dev = pygame.image.load(
                os.path.join(RES_FOLDER, 'tile_texture.png')
            )

            self.tile_full = pygame.image.load(
                os.path.join(RES_FOLDER, 'tiles', 'full.png')
            )
            self.tile_empty = pygame.image.load(
                os.path.join(RES_FOLDER, 'tiles', 'empty.png')
            )

            # accessed from tilemap
            self.tile_mappings = [
                self.tile_full,  # 0 -> full tile
                self.tile_empty,  # 0 -> empty tile
            ]

            # player sprite
            self.player = pygame.image.load(
                os.path.join(RES_FOLDER, 'char.png')
            )

    def log(self, msg: str, level: int = 1):
        """
        Log things to the console. Respects USE_ADVANCED_LOGGING.
        :param msg: Message to log to the console.
        :param level: Level of severity. 0=DEBUG, 1=INFO (default), 2=WARNING, 3=ERROR
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

    def run(self):
        """
        Initialize and run the game forever until it quits.
        If this function returns, then the game has ended.
        Returns the exit code for the game, run this last.
        """
        self.log(f'Initializing screen ({FRAME_W}x{FRAME_H})')
        pygame.init()
        pygame.display.set_caption(f'Power Lawn v{VERSION}')
        self.running = True
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))  # TODO: Make screen size dynamic
        self.screen_clock = pygame.time.Clock()  # frame clock

        self.objects = [
            Player(self, 0, 0, 45, self.textures.player),
        ]

        self.log('Creating initial tilemap...')
        self.create_tilemap()

        self.log('Starting event loop...')
        self.log(f'{len(self.objects):,} objects active')
        try:
            while self.running:
                self.screen_update()  # update everything
                self.process_events(pygame.event.get())  # process event queue
                self.screen_clock.tick(60)  # cAlm tHe TiDe
        except Exception as e:
            self.log(str(e), 2)  # error :(
            traceback.print_exception(type(e), e, e.__traceback__)  # show in console
            return 1, e
        self.log('Game exited normally', 0)
        return 0

    def create_tilemap(self):
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
        for _ in range(0, self.frame.get_height(), self.textures.base_tile_size):
            self.tile_gird.append(
                [0 for _ in range(0, self.frame.get_width(), self.textures.base_tile_size)]
            )

    def draw_background(self):
        """
        Update and render the tilemap to the screen.
        This function takes care of:
            * The player clearing out area
            * Calculating the radius of the cleared area
            * Calculating the correct tile textures
        """
        player_cell_x = int(self.objects[0].globalRect.centerx * (1 / self.textures.base_tile_size))
        player_cell_y = int(self.objects[0].globalRect.centery * (1 / self.textures.base_tile_size))

        # cell y, row data
        for cy, r in enumerate(self.tile_gird):
            # cell x, column data
            for cx, c in enumerate(r):
                # screenspace position
                ss_pos = (cx * self.textures.base_tile_size, cy * self.textures.base_tile_size)

                if is_point_in_circle((cx, cy), (player_cell_x, player_cell_y), self.path_radius):
                    c = 1
                    self.tile_gird[cy][cx] = 1

                self.frame.blit(self.textures.tile_mappings[c], ss_pos)

    def screen_update(self):
        """
        Update all game objects, draw them to the screen and refresh it.
        Gets called every frame, so make it fast.
        """
        self.draw_background()

        for game_object in self.objects:
            game_object.update()

        self.screen.fill(0x262626)
        self.screen.blit(self.frame, (10, 10))
        pygame.display.update()

    def game_quit(self, e):
        """Event callback method to quit the game. """
        self.running = False
        pygame.quit()

    def process_key(self, e):
        """Event callback method to process keypresses."""
        if (e.type == pygame.KEYDOWN) and (e.key not in self.keys_down):
            self.keys_down.append(e.key)
        elif (e.type == pygame.KEYUP) and (e.key in self.keys_down):
            self.keys_down.remove(e.key)

    def process_events(self, queue: tuple = ()):
        """
        Run through the event queue and resolve all events to their callbacks.
        :param queue: the event queue (duh)
        """

        if queue == ():  # save a bit of processing power
            return

        for e in queue:
            # type define event object (pygame is confused)
            e: pygame.event.Event()

            # is the event's callback defined? if yes, run it
            if e_callback := self.event_callback.get(e.type):
                e_callback(e)
                # skip to next loop cycle
                continue
            # if the cycle is not skipped here, say that we missed the event on the DEBUG level
            # self.log(f'Uncaught event {e.type}', 0)


class GameObject(pygame.sprite.Sprite):
    def __init__(self, parent: Game, x=0, y=0, angle=0, image=None):
        """
        Universal GameObject class to be inherited & overriden by specific objects.

        :param parent: originating game object
        :param x: initial horizontal position
        :param y: initial vertical position
        :param image: sprite
        """
        super(GameObject, self).__init__()

        self.parent = parent
        self.image = image

        self.x, self.y = x, y
        self.angle = angle

        self.rect = self.image.get_rect()
        self.globalRect = pygame.Rect(
            self.rect.x + self.x,
            self.rect.y + self.y,
            self.rect.w, self.rect.h
        )

    @property
    def w(self): return self.rect.w

    @property
    def h(self): return self.rect.h

    def update(self):
        """
        Dynamic method to update the state/position/whatever you want of the game object.
        Gets called every frame, so make it fast.
        By default, just draws the sprite to the screen.
        """
        self.draw()

    def draw(self, surface=None):
        """
        Rotates the game object's sprite to the appropriate angle around its center,
        then blits it to the surface specified.
        If no surface is specified, the parent's display object is used.
        """

        if surface is None:
            surface = self.parent.frame

        img_w, img_h = self.image.get_size()

        bounding_box = [
            pygame.math.Vector2(0, 0),  # top left
            pygame.math.Vector2(img_w, 0),  # top right
            pygame.math.Vector2(img_w, -img_h),  # bottom right
            pygame.math.Vector2(0, -img_h)  # bottom left
        ]

        # rotate all vectors to match our rotation
        bounding_box = [vec.rotate(self.angle) for vec in bounding_box]

        # get smallest x value in all points' x values
        min_x = min(bounding_box, key=lambda vec: vec[0])[0]

        # get largest y value in all points' y values
        max_y = max(bounding_box, key=lambda vec: vec[1])[1]

        # get center of image
        center = pygame.math.Vector2(
            (img_w * 0.5),
            -(img_h * 0.5)  # pygame vectors are upside down, so this is negative
        )
        # how much should be corrected from the rotation
        pivot_offset = center.rotate(self.angle) - center

        pos = (  # apply the offsets
            self.x + min_x - pivot_offset[0],
            self.y - max_y + pivot_offset[1]
        )

        img = pygame.transform.rotate(self.image, self.angle)

        self.rect = img.get_rect()  # update internal rectangle to the rotated image's
        # re-calculate global rectangle, mindful of offset and new size
        self.globalRect = pygame.Rect(
            pos[0], pos[1],
            self.rect.w, self.rect.h
        )

        surface.blit(img, pos)  # draw to the screen at the corrected position

    def log(self, *args):
        """
        link to parent's log function for ease of access
        """
        self.parent.log(*args)


class Player(GameObject):
    """
    This class is a game object that represents the player's
    head. It strives to move towards the mouse pointer.
    """

    def __init__(self, *args):
        super(Player, self).__init__(*args)

        self.speed = 0  # speed of the player, used in update()
        self.turnspeed = 1

        self.key_up = pygame.K_w
        self.key_down = pygame.K_s
        self.key_right = pygame.K_d
        self.key_left = pygame.K_a

    def update(self):
        """
        Player Update function. Moves the player's position towards
        the desired angle at a constant speed defined in its class
        attributes.
        """

        if self.key_right in self.parent.keys_down:
            self.angle -= self.turnspeed
        if self.key_left in self.parent.keys_down:
            self.angle += self.turnspeed
        if self.key_down in self.parent.keys_down and self.speed >= 0.1:
            self.speed -= 0.1
        if self.key_up in self.parent.keys_down:
            self.speed += 0.1

        self.speed = round(self.speed, 3)

        sx = math.cos(math.radians(-self.angle)) * self.speed
        sy = math.sin(math.radians(-self.angle)) * self.speed
        self.draw()

        pygame.draw.line(
            self.parent.frame, 0xff0000,
            self.globalRect.center, (
                self.globalRect.center[0] + (sx * 100),
                self.globalRect.center[1] + (sy * 100),
            ), 2
        )

        if self.parent.frame.get_width() > self.globalRect.center[0] + sx > 0:
            self.x += sx
        if self.parent.frame.get_height() > self.globalRect.center[1] + sy > 0:
            self.y += sy


if __name__ == '__main__':
    if USE_ADVANCED_LOGGING:
        _logger = logging.Logger('game')
        _logger.setLevel(logging.DEBUG if ADVANCED_LOGGING_SHOW_DEBUG else logging.INFO)

        _stdhandler = logging.StreamHandler()
        _stdhandler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] : %(message)s', '%d/%m/%Y %H:%M:%S'))
        _logger.addHandler(_stdhandler)
    else:
        _logger = None

    game = Game(logger=_logger)
    exit(game.run())
