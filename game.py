#!/usr/bin/python
"""
██████╗  ██████╗ ██╗    ██╗███████╗██████╗ ██╗      █████╗ ██╗    ██╗███╗   ██╗
██╔══██╗██╔═══██╗██║    ██║██╔════╝██╔══██╗██║     ██╔══██╗██║    ██║████╗  ██║
██████╔╝██║   ██║██║ █╗ ██║█████╗  ██████╔╝██║     ███████║██║ █╗ ██║██╔██╗ ██║
██╔═══╝ ██║   ██║██║███╗██║██╔══╝  ██╔══██╗██║     ██╔══██║██║███╗██║██║╚██╗██║
██║     ╚██████╔╝╚███╔███╔╝███████╗██║  ██║███████╗██║  ██║╚███╔███╔╝██║ ╚████║
╚═╝      ╚═════╝  ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═══╝
                            by Martin Velikov
"""
import random

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
    diff_x, diff_y = map(lambda x, y: abs(x-y), center, point)  # subtract point from center then abs for both x and y

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

    event_callback : dict{pygame.event.Event : function}
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
        self.event_callback = {
            pygame.QUIT: self.game_quit,
            pygame.KEYUP: self.process_key,
            pygame.KEYDOWN: self.process_key
        }
        # currently pressed keys
        self.keys_down = []
        # textures to load
        self.textures = None
        # fonts to load
        self.fonts = None
        # background tile grid
        self.tile_grid = []
        # player trail radius
        self.path_radius = 2
        # player quadrant
        self.path_template = []

    class Textures:
        def __init__(self):
            self.base_tile_size = 10
            self.base_bg_tile_size = 60

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

            self.enemy = pygame.transform.scale(
                pygame.image.load(
                    os.path.join(RES_FOLDER, 'img', 'enemy', 'orig.png')
                ), (100, 200)
            )

    class Fonts:
        def __init__(self):
            self.comic_sans = pygame.font.Font(
                'res'
            )

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
        return self.objects[0]

    def run(self):
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

        # init the screen and prepare it
        self.log(f'Initializing screen ({SCREEN_W}x{SCREEN_H})')
        pygame.init()
        pygame.display.set_caption(f'Power Lawn v{VERSION}')
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.screen_clock = pygame.time.Clock()  # frame clock

        # create the game objects
        self.log(f'Creating objects...')
        self.objects = [
            # slot 0 should always be the main player
            Player(parent=self, start_x=0, start_y=0, start_angle=0, image=self.textures.player),
            Enemy(parent=self, start_x=500, start_y=500, start_angle=0, image=self.textures.enemy)
        ]

        # set enemy target
        self.objects[1].target = self.player

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
                self.tick_objects()  # update everything
                self.full_draw()
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
                s += (' ' * 30) + ''.join(map(lambda v: ['[-]', '[#]', '[$]'][v], r)) + '\n'
            self.log('Path quadrant result (#/full, $/half, -/empty): \n' + s.rstrip(), 0)

    def bake_background_texture(self):
        """
        Replicates the background tile to the required size of the frame.
        Outputs result to self.textures.full_bg
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
        player_cell_x, player_cell_y = cell_from_screenspace(self.player.globalRect.center, self.textures.base_tile_size)

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

    def tick_objects(self):
        """
        Update all game objects, draw them to the screen call frame_to_screen.
        Gets called every frame, so make it fast.
        """
        for game_object in self.objects:
            game_object.update()
        self.update_path()

    def draw_objects(self):
        for game_object in sorted(self.objects, key=lambda x: x.draw_priority):
            game_object.draw()

    def draw_frame_to_screen(self):
        """
        Takes care of what everything looks like outside the frame window.
        Assumes everything inside the frame is ready to go.
        Refreshes the screen; the final draw call per frame.
        """
        self.screen.fill(0x23272A)
        self.screen.blit(self.frame, (10, 10))
        pygame.display.update()

    def full_draw(self):
        self.draw_tilemap()
        self.draw_objects()
        self.draw_frame_to_screen()

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

    def kick_player(self):
        v_player = Vector2(self.player.x, self.player.y)
        dist_to_right = int(self.frame.get_width() - self.player.x)
        dist_to_bottom = int(self.frame.get_height() - self.player.y)

        end_pos = v_player + Vector2(
            random.randint(int(-self.player.x) + 100, dist_to_right - 100),
            random.randint(int(-self.player.y) + 100, dist_to_bottom - 100))

        for i in range(50):
            self.player.x, self.player.y = v_player.slerp(end_pos, i/50)
            self.player.angle += 7.2  # 360 / 50
            self.full_draw()
            pygame.draw.circle(self.frame, 0x0000ff, tuple(map(int, (self.player.x, self.player.y))), 5)
            pygame.draw.circle(self.frame, 0xff0000, tuple(map(int, end_pos)), 5)
            self.screen_clock.tick(60)



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
        By default, just draws the sprite to the screen.
        """
        self.draw()

    def draw(self, surface=None):
        """
        Rotates the game object's sprite to the appropriate angle around its center,
        then blits it to the surface specified.  If no surface is specified, the parent's
        display object is used.

        Parameters:
            surface (Surface/None): the surface to draw sprite image on
        """

        if surface is None:
            surface = self.parent.frame

        if self.angle != 0:  # use the expensive calculation below only if there is any actual rotation
            # some rotation is happening, offset calculation is required
            img_w, img_h = self.image.get_size()

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

            img = pygame.transform.rotate(self.image, self.angle)  # rotate image
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
        self.turnspeed = 5

        # these probes
        self.path_probes = [
            (30, 20),  # front right
            (30, -20),  # front left
        ]

        self.movement_allowed = True

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

        if self.movement_allowed:  # only run this code if movement is allowed, pointless otherwise
            # alter angle based on which keys are pressed
            if self.key_right in self.parent.keys_down:
                self.angle -= self.turnspeed
            if self.key_left in self.parent.keys_down:
                self.angle += self.turnspeed
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
            real_speed = (self.speed / 2) if is_slowed_down else self.speed

            # calculate step movement every frame
            step_x = math.cos(math.radians(-self.angle)) * real_speed
            step_y = math.sin(math.radians(-self.angle)) * real_speed

            # check if movement is valid, and it it is, go for it
            if frame_w > self.globalRect.center[0] + step_x > 0:
                self.x += step_x
            if frame_h > self.globalRect.center[1] + step_y > 0:
                self.y += step_y

        # render to the scene
        self.draw()

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
        self.speed = 3  # chasing speed, for reference, the player's value is 5
        self.target = None  # the target to chase, this is set after initialization
        # instead of heading for the target's center, where should the enemy head for?
        self.hunt_offset = (self.rect.centerx, self.rect.centery + 40)
        # when enemy will try to kick the lawnmower
        self.kick_distance = 40

    def update(self):
        """
        This function handles the update of the Enemy AI. The `target` parameter must be set to a valid instance
        of GameObject (usually the player).

        Called every frame.
        """

        if self.target is not None:  # skip calculating the movement if there is no set target
            # get mouse pos
            target_x, target_y = self.target.globalRect.center

            # calculate relative to object
            relative_x = target_x - (self.x + self.hunt_offset[0])
            relative_y = target_y - (self.y + self.hunt_offset[1])

            if int(relative_y - 20) > 0:
                self.draw_priority = 90
            else:
                self.draw_priority = 110

            # furthest axis
            furthest_distance = max(abs(relative_x), abs(relative_y))

            if furthest_distance > self.kick_distance:
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
                self.parent.kick_player()
        # draw to the screen, regardless of whether any movement happened
        self.draw()


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
        rcode = game.run()  # run the game forever, then get return code
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