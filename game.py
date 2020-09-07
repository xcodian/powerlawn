'''
██████╗  ██████╗ ██╗    ██╗███████╗██████╗ ██╗      █████╗ ██╗    ██╗███╗   ██╗
██╔══██╗██╔═══██╗██║    ██║██╔════╝██╔══██╗██║     ██╔══██╗██║    ██║████╗  ██║
██████╔╝██║   ██║██║ █╗ ██║█████╗  ██████╔╝██║     ███████║██║ █╗ ██║██╔██╗ ██║
██╔═══╝ ██║   ██║██║███╗██║██╔══╝  ██╔══██╗██║     ██╔══██║██║███╗██║██║╚██╗██║
██║     ╚██████╔╝╚███╔███╔╝███████╗██║  ██║███████╗██║  ██║╚███╔███╔╝██║ ╚████║
╚═╝      ╚═════╝  ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═══╝
                            by Martin Velikov
'''
import random

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

import pygame  # the one and only


def weight_point_in_circle(point: tuple, center: tuple, radius: int, corner_threshold: float = 1.5):
    """
    Function to decide whether a certain point should be a full, half or empty tile.
    """
    px, py = point
    cx, cy = center

    diff_x = abs(cx - px)
    diff_y = abs(cy - py)

    if (diff_y > radius) or (diff_x > radius):
        return False

    dist = diff_x * diff_x + diff_y * diff_y

    # precalculate radius sqaured
    rs = radius * radius
    # precalculate rounded distance
    rd = round(dist)

    if rd < rs:  # distance within radius
        return 1  # full tile
    elif rd < rs * corner_threshold and diff_x < radius:  # distance on edge, threshold of 0.2
        return 2  # half tile
    # outside of any thresholds
    return 0  # empty tile


class Game:
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
        self.event_callback = {
            pygame.QUIT: self.game_quit,
            pygame.KEYUP: self.process_key,
            pygame.KEYDOWN: self.process_key
        }
        # currently pressed keys
        self.keys_down = []
        # textures to load
        self.textures = None
        #
        self.tile_grid = []

        self.path_radius = 2
        self.path_template = []

    class Textures:
        def __init__(self):
            self.base_tile_size = 10
            self.base_bg_tile_size = 60

            # tiles
            self.tile_dev = pygame.image.load(
                os.path.join(RES_FOLDER, 'dev.png')
            )
            self.tile_empty = pygame.image.load(
                os.path.join(RES_FOLDER, 'tiles', 'empty.png')
            )
            self.tile_half = pygame.image.load(
                os.path.join(RES_FOLDER, 'tiles', 'half.png')
            )

            # accessed from tilemap
            self.tile_mappings = [
                None,  # 0 -> full tile
                self.tile_empty,  # 1 -> empty tile
                self.tile_half,  # 2 -> half tile
            ]

            # player sprite
            self.player = pygame.transform.scale(
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'char.png')
                ), (111, 60)
            )

            # background tile
            self.tile_bg_grass = pygame.transform.scale(
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'tiles', 'bgtile.png')
                ), (self.base_bg_tile_size, self.base_bg_tile_size)
            )

            # replicated background that should fill the screen, see Game.bake_background_texture
            self.full_bg = None

            self.enemy = pygame.transform.scale(
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'enemy.png')
                ), (100, 200)
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
        # load the textures
        self.log('Loading textures...')
        self.textures = self.Textures()

        # init the screen and prepare it
        self.log(f'Initializing screen ({SCREEN_W}x{SCREEN_H})')
        pygame.init()
        pygame.display.set_caption(f'Power Lawn v{VERSION}')
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))  # TODO: Make screen size dynamic
        self.screen_clock = pygame.time.Clock()  # frame clock

        # create the game objects
        self.log(f'Creating objects...')
        self.objects = [
            # slot 0 should always be the main player
            Player(parent=self, start_x=0, start_y=0, start_angle=0, image=self.textures.player),
            Enemy(parent=self, start_x=500, start_y=500, start_angle=0, image=self.textures.enemy)
        ]

        # set enemy target
        self.objects[1].target = self.objects[0]

        # make the big tile array
        self.log('Baking initial tilemap...')
        self.bake_tilemap()

        # make a quadrant of the player path
        self.log(f'Baking path quadrant...')
        self.bake_path_quadrant()

        # replicate the grass texure to fill the frame's size
        self.log(f'Baking background texture to size {FRAME_W}x{FRAME_H}...')
        self.bake_background_texture()

        # finally, start the game
        self.log('Starting event loop...')
        self.running = True
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

    def bake_tilemap(self):
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
            self.tile_grid.append(
                [0 for _ in range(0, self.frame.get_width(), self.textures.base_tile_size)]
            )

    def bake_path_quadrant(self):
        """
        Generate one quadrant of the path to be mirrored later.
        This is calculated once and saved to quarter_path_template.
        It is applied every frame from the baked template, without being recalculated. Speed!
        """
        self.path_template = []
        for ri in range(self.path_radius + 1):
            r = []
            for ci in range(self.path_radius + 1):
                r.append(weight_point_in_circle((ci, ri), (0, 0), self.path_radius))
            self.path_template.append(r)

        if ADVANCED_LOGGING_SHOW_DEBUG:
            def convert(v):
                return ['[-]', '[#]', '[$]'][v]

            s = ''
            for r in self.path_template:
                s += (' '*30) + ''.join(map(convert, r)) + '\n'
            self.log('Path quadrant result (#/full, $/half, -/empty): \n'+s.rstrip(), 0)

    def bake_background_texture(self):
        """
        Replicates the background tile to the required size of the frame.
        """
        # get frame size
        fw, fh = self.frame.get_size()

        # create surface large enough to house texture
        bg = pygame.Surface((fw, fh))

        # blit tile texture to larger texture
        for y in range(0, fh, self.textures.base_bg_tile_size):
            for x in range(0, fw, self.textures.base_bg_tile_size):
                tile = pygame.transform.rotate(
                    self.textures.tile_bg_grass, random.choice((0, 90, 180, 270))
                )
                bg.blit(tile, (x, y))

        self.textures.full_bg = bg


    def update_path(self):
        """
        Alter the tile array to include the path of the player relative to their position.
        """
        # Calculate the cell position of the player by using int rounding, this returns cell coords in the tile array
        player_cell_x = int(self.objects[0].globalRect.centerx * (1 / self.textures.base_tile_size))
        player_cell_y = int(self.objects[0].globalRect.centery * (1 / self.textures.base_tile_size))

        # Now to set up the area around the player, we can just replicate the pregenerated quarter 4 times:

        # iterate through rows (iter as qr), keeping index as qy.
        for qy, qr in enumerate(self.path_template):
            # iterate through columns (iter as qc), keeping index as qx.
            for qx, qc in enumerate(qr):
                # do not draw empty pixels on the screen.
                if qc == 0:
                    continue

                # get tile grid width & height
                tgw, tgh = len(self.tile_grid[0]), len(self.tile_grid)

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
                    if min(x, y) > -1 and x < tgw and y < tgh:
                        if qc == 2 and (  # is the cell about to be drawn a half-cell?
                            self.tile_grid[y][x] == 1  # is the tile at that position blank?
                                or
                            y > player_cell_y  # is the position of the half below the player coordinate?
                        ):
                            continue  # do not draw that half-cell

                        # add index in bottom right (original array orientation)
                        self.tile_grid[y][x] = qc
                    quad += 1


    def draw_background(self):
        """
        Update and render the tilemap to the screen.
        This function takes care of:
            - Drawing the static texture for the background
            - Drawing the tilemap to the screen
        """

        # draw the background grid
        self.frame.blit(self.textures.full_bg, (0, 0))

        # draw the tile grid
        for cy, r in enumerate(self.tile_grid):
            # cell x, column data
            for cx, c in enumerate(r):
                if c == 0:
                    continue  # skip drawing this
                tex = self.textures.tile_mappings[c]
                # screenspace position
                ss_pos = (cx * self.textures.base_tile_size, cy * self.textures.base_tile_size)
                self.frame.blit(tex, ss_pos)

    def screen_update(self):
        """
        Update all game objects, draw them to the screen and refresh it.
        Gets called every frame, so make it fast.
        """
        self.update_path()
        self.draw_background()

        for game_object in self.objects:
            game_object.update()

        self.screen.fill(0x23272A)

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
    def __init__(self, parent: Game, start_x=0, start_y=0, start_angle=0, image=None):
        """
        Universal GameObject class to be inherited & overriden by specific objects.

        :param parent: originating game object
        :param start_x: initial horizontal position
        :param start_y: initial vertical position
        :param image: sprite
        """
        super(GameObject, self).__init__()

        self.parent = parent
        self.image = image

        self.x, self.y = start_x, start_y
        self.angle = start_angle

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

        if self.angle != 0: # skip the expensive calculation below if there is no rotation
            # some rotation is happening, offset calculation is required
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
                (img_w * 0.5),  # TODO: center offset, also do globalRect
                -(img_h * 0.5)  # pygame vectors are upside down, so this is negative
            )
            # how much should be corrected from the rotation
            pivot_offset = center.rotate(self.angle) - center

            pos = (  # apply the offsets
                self.x + min_x - pivot_offset[0],
                self.y - max_y + pivot_offset[1]
            )

            img = pygame.transform.rotate(self.image, self.angle) # rotate image
        else:
            # the angle is 0, forget all of the expensive calculations above
            img = self.image
            pos = (self.x, self.y)

        self.rect = img.get_rect()  # update internal rectangle
        # re-calculate global rectangle, mindful of offset and new size
        self.globalRect = pygame.Rect(
            pos[0], pos[1],
            self.rect.w, self.rect.h
        )

        surface.blit(img, pos)  # draw to the screen at the proper position

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

    def __init__(self, *args, **kwargs):
        super(Player, self).__init__(*args, **kwargs)

        self.speed = 0  # speed of the player, used in update()
        self.turnspeed = 5

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

        if self.parent.frame.get_width() > self.globalRect.center[0] + sx > 0:
            self.x += sx
        if self.parent.frame.get_height() > self.globalRect.center[1] + sy > 0:
            self.y += sy


class Enemy(GameObject):
    def __init__(self, *args, **kwargs):
        super(Enemy, self).__init__(*args, **kwargs)
        self.speed = 3
        self.target = None

        self.hunt_offset = (self.rect.centerx, self.rect.centery + 40)

    def update(self):
        """
        This function handles the update of the Enemy AI. The `target` parameter must be set to a valid instance
        of GameObject (usually the player).
        The enemy AI is very simple. It just tries to approach the player linearly, at a constant pace.
        """

        if self.target is not None:  # skip calculating the movement if there is no set target
            # get mouse pos
            target_x, target_y = self.target.globalRect.center

            # calculate relative to object
            relative_x = target_x - (self.x + self.hunt_offset[0])
            relative_y = target_y - (self.y + self.hunt_offset[1])

            # steps required to go to pos
            steps_required = max(abs(relative_x), abs(relative_y))

            if steps_required != 0:
                step_dist_x = (relative_x / steps_required) * self.speed  # horizontal step
                step_dist_y = (relative_y / steps_required) * self.speed  # vertical step

                # calculate if the player can still move smoothly
                if abs(int(relative_x)) >= self.speed:
                    # move one step towards target x
                    self.x += step_dist_x
                else:
                    # the player is too close to the mouse pointer to have a reliable
                    # step calculation because of framerate, just snap to pointer
                    # this runs on the last frame of the movement
                    self.x = target_x - self.hunt_offset[0]

                # same as above, but for vertical movement
                if abs(int(relative_y)) >= self.speed:
                    self.y += step_dist_y
                else:
                    self.y = target_y - self.hunt_offset[1]
        # draw to the screen, regardless of whether any movement happened
        self.draw()


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
    game.log('Starting game...')
    try:
        rcode = game.run()
    except Exception as e:
        game.log(str(e), 3)

        if ADVANCED_LOGGING_SHOW_DEBUG:
            game.log(f'Showing traceback, disable DEBUG to hide.\n\n{"-"*9} BEGIN DEBUG TRACEBACK {"-"*9}\n', 0)
            traceback.print_exception(type(e), e, e.__traceback__)
else:
    print('This file does nothing unless explicitly executed.')
    input('[Press Enter to exit.]')
