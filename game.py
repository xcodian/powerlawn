# incorporate level-based logging instead of unfiltere print
USE_ADVANCED_LOGGING = True
# show debug prints? warning: spams console
ADVANCED_LOGGING_SHOW_DEBUG = True
# screen dimensions
SCREEN_W = 1280
SCREEN_H = 720
# resources
RES_FOLDER = 'res'

import os
import math
import time
import traceback
import logging

import warnings

# hide DeprecationWarning for floats
# Why am I doing this? Because I don't want to
warnings.filterwarnings("ignore", category=DeprecationWarning)

# hide the annoying prompt message pygame comes with
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame

class Game:
    def __init__(self, logger: logging.Logger = None):
        """
        Base Game which takes care of the logic. Manages and updates its objects.
        There should really be only one of these at any time.
        :param logger: the logger to use, if not specified, it will use print sattements
        """
        self.running = False  # is the game running?
        self.logger = logger

        self.screen: pygame.Surface = None
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

    class Textures:
        def __init__(self):
            self.tile_magenta = pygame.image.load(
                os.path.join(RES_FOLDER, 'tile_texture.png')
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
        self.log(f'Initializing screen ({SCREEN_W}x{SCREEN_H})')
        pygame.init()
        self.running = True
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))  # TODO: Make screen size dynamic
        self.screen_clock = pygame.time.Clock()  # frame clock

        self.objects = [
            Player(self, 0, 0, 45, pygame.image.load('res/sprite.png')),
            Player2(self, 0, 100, 0, pygame.image.load('res/thatsok.png')),
        ]

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

    def screen_update(self):
        """
        Update all game objects, draw them to the screen and refresh it.
        Gets called every frame, so make it fast.
        """

        for y in range(0, self.screen.get_height(), self.textures.tile_magenta.get_height()):
            for x in range(0, self.screen.get_width(), self.textures.tile_magenta.get_width()):
                self.screen.blit(self.textures.tile_magenta, (x, y))

        for game_object in self.objects:
            game_object.update()

        pygame.display.update()  # TODO: More efficient way of rendering!

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
            surface = self.parent.screen

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

        self.key_up = pygame.K_UP
        self.key_down = pygame.K_DOWN
        self.key_right = pygame.K_RIGHT
        self.key_left = pygame.K_LEFT

        self.trail = [
            (self.globalRect.centerx, self.globalRect.centery),
            (self.globalRect.centerx, self.globalRect.centery)
        ]

        self.frames_since_last_trail_point = 0

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

        pygame.draw.rect(self.parent.screen, 0x0000ff, self.globalRect, 1)

        self.draw()

        pygame.draw.line(
            self.parent.screen, 0xff0000,
            self.globalRect.center, (
                self.globalRect.center[0] + (sx * 100),
                self.globalRect.center[1] + (sy * 100),
            ), 2
        )

        if self.parent.screen.get_width() > self.globalRect.center[0] + sx > 0:
            self.x += sx
        if self.parent.screen.get_height() > self.globalRect.center[1] + sy > 0:
            self.y += sy

        if (max(sx, sy) > 0 or min(sx, sy) < 0) and self.frames_since_last_trail_point > 10:
            self.trail.append(
                (self.globalRect.centerx, self.globalRect.centery)
            )
            self.frames_since_last_trail_point = 0

        self.frames_since_last_trail_point += 1

    def draw(self, *args):
        pygame.draw.lines(self.parent.screen, 0xff0000, False, self.trail, 5)

        super(Player, self).draw(*args)


class Player2(Player):
    def __init__(self, *args):
        super(Player2, self).__init__(*args)

        self.key_up = pygame.K_w
        self.key_down = pygame.K_s
        self.key_right = pygame.K_d
        self.key_left = pygame.K_a


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
