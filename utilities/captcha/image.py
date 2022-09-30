# coding: utf-8
from __future__ import annotations

import os
import random
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple
from PIL import Image, ImageFont, ImageFilter
from PIL.ImageDraw import Draw
from PIL.ImageFont import truetype

try:
    from cStringIO import StringIO as BytesIO  # type: ignore
except ImportError:
    from io import BytesIO
try:
    from wheezy.captcha import image as wheezy_captcha  # type: ignore
except ImportError:
    wheezy_captcha = None

from utilities.converters import ToAsync

DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")
DEFAULT_FONTS = [os.path.join(DATA_DIR, "DroidSansMono.ttf")]

if wheezy_captcha:
    __all__ = ("ImageCaptcha", "WheezyCaptcha")
else:
    __all__ = ("ImageCaptcha",)

try:
    _QUAD = Image.Transform.QUAD
except AttributeError:
    _QUAD = Image.QUAD

try:
    _BILINEAR = Image.Resampling.BILINEAR
except AttributeError:
    _BILINEAR = Image.BILINEAR

table = [int(i * 1.97) for i in range(256)]


class _Captcha(object):
    if TYPE_CHECKING:
        generate_image: Callable[[str], Image.Image]

    @ToAsync()
    def generate(self, chars: str, format: str = "png") -> bytes:
        """Generate an Image Captcha of the given characters.
        :param chars: text to be generated.
        :param format: image file format
        """
        im: Image.Image = self.generate_image(chars)
        out: BytesIO = BytesIO()
        im.save(out, format=format)
        out.seek(0)
        return out

    @ToAsync()
    def write(self, chars: str, output: str, format: str = "png"):
        """Generate and write an image CAPTCHA data to the output.
        :param chars: text to be generated.
        :param output: output destination.
        :param format: image file format
        """
        im = self.generate_image(chars)
        return im.save(output, format=format)


class WheezyCaptcha(_Captcha):
    """Create an image CAPTCHA with wheezy.captcha."""

    def __init__(self, width: int = 200, height: int = 75, fonts: str = None):
        self._width = width
        self._height = height
        self._fonts = fonts or DEFAULT_FONTS

    def generate_image(self, chars: str):
        text_drawings = [
            wheezy_captcha.warp(),
            wheezy_captcha.rotate(),
            wheezy_captcha.offset(),
        ]
        fn = wheezy_captcha.captcha(
            drawings=[
                wheezy_captcha.background(),
                wheezy_captcha.text(fonts=self._fonts, drawings=text_drawings),
                wheezy_captcha.curve(),
                wheezy_captcha.noise(),
                wheezy_captcha.smooth(),
            ],
            width=self._width,
            height=self._height,
        )
        return fn(chars)


class ImageCaptcha(_Captcha):
    """Create an image CAPTCHA.
    Many of the codes are borrowed from wheezy.captcha, with a modification
    for memory and developer friendly.
    ImageCaptcha has one built-in font, DroidSansMono, which is licensed under
    Apache License 2. You should always use your own fonts::
        captcha = ImageCaptcha(fonts=['/path/to/A.ttf', '/path/to/B.ttf'])
    You can put as many fonts as you like. But be aware of your memory, all of
    the fonts are loaded into your memory, so keep them a lot, but not too
    many.
    :param width: The width of the CAPTCHA image.
    :param height: The height of the CAPTCHA image.
    :param fonts: Fonts to be used to generate CAPTCHA images.
    :param font_sizes: Random choose a font size from this parameters.
    """

    def __init__(
        self,
        width: int = 160,
        height: int = 60,
        fonts: Optional[str] = None,
        font_sizes: Optional[Tuple[int, int, int]] = None,
    ):
        self._width = width
        self._height = height
        self._fonts = fonts or DEFAULT_FONTS
        self._font_sizes = font_sizes or (42, 50, 56)
        self._truefonts: "List[ImageFont.FreeTypeFont]" = []

    @property
    def truefonts(self):
        if self._truefonts:
            return self._truefonts
        self._truefonts = tuple(
            truetype(n, s) for n in self._fonts for s in self._font_sizes
        )

        return self._truefonts

    @staticmethod
    def create_noise_curve(image: Image.Image, color: Tuple[int, int, int]):
        w, h = image.size
        x1 = random.randint(0, int(w / 5))
        x2 = random.randint(w - int(w / 5), w)
        y1 = random.randint(int(h / 5), h - int(h / 5))
        y2 = random.randint(y1, h - int(h / 5))
        points = [x1, y1, x2, y2]
        end = random.randint(160, 200)
        start = random.randint(0, 20)
        Draw(image).arc(points, start, end, fill=color)
        return image

    @staticmethod
    def create_noise_dots(
        image: Image.Image, color: Tuple, width: int = 3, number: int = 30
    ):
        draw = Draw(image)
        w, h = image.size
        while number:
            x1 = random.randint(0, w)
            y1 = random.randint(0, h)
            draw.line(((x1, y1), (x1 - 1, y1 - 1)), fill=color, width=width)
            number -= 1
        return image

    def create_captcha_image(self, chars: str, color: Tuple[int, int, int], background: str) -> Image.Image:
        """Create the CAPTCHA image itself.
        :param chars: text to be generated.
        :param color: color of the text.
        :param background: color of the background.
        The color should be a tuple of 3 numbers, such as (0, 255, 255).
        """
        image = Image.new("RGB", (self._width, self._height), background)
        draw = Draw(image)

        def _draw_character(c: str):
            font = random.choice(self.truefonts)
            try:
                _, _, w, h = draw.textbbox((1, 1), c, font=font)
            except AttributeError:
                w, h = draw.textsize(c, font=font)

            dx = random.randint(0, 4)
            dy = random.randint(0, 6)
            im = Image.new("RGBA", (w + dx, h + dy))
            Draw(im).text((dx, dy), c, font=font, fill=color)

            # rotate
            im = im.crop(im.getbbox())
            im = im.rotate(random.uniform(-30, 30), _BILINEAR, expand=1)

            # warp
            dx = w * random.uniform(0.1, 0.3)
            dy = h * random.uniform(0.2, 0.3)
            x1 = int(random.uniform(-dx, dx))
            y1 = int(random.uniform(-dy, dy))
            x2 = int(random.uniform(-dx, dx))
            y2 = int(random.uniform(-dy, dy))
            w2 = w + abs(x1) + abs(x2)
            h2 = h + abs(y1) + abs(y2)
            data = (
                x1,
                y1,
                -x1,
                h2 - y2,
                w2 + x2,
                h2 + y2,
                w2 - x2,
                -y1,
            )
            im = im.resize((w2, h2))
            im = im.transform((w, h), _QUAD, data)
            return im

        images: List[Image.Image] = []
        for c in chars:
            if random.random() > 0.5:
                images.append(_draw_character(" "))
            images.append(_draw_character(c))

        text_width = sum(im.size[0] for im in images)

        width = max(text_width, self._width)
        image = image.resize((width, self._height))

        average = int(text_width / len(chars))
        rand = int(0.25 * average)
        offset = int(average * 0.1)

        for im in images:
            w, h = im.size
            mask = im.convert("L").point(table)
            image.paste(im, (offset, int((self._height - h) / 2)), mask)
            offset = offset + w + random.randint(-rand, 0)

        if width > self._width:
            image = image.resize((self._width, self._height))

        return image

    def generate_image(self, chars: str):
        """Generate the image of the given characters.
        :param chars: text to be generated.
        """
        background = random_color(238, 255)
        color = random_color(10, 200, random.randint(220, 255))
        im: "Image.Image" = self.create_captcha_image(chars, color, background)
        self.create_noise_dots(im, color)
        self.create_noise_curve(im, color)
        im = im.filter(ImageFilter.SMOOTH)
        return im


def random_color(start: int, end: int, opacity: Optional[int] = None):
    red = random.randint(start, end)
    green = random.randint(start, end)
    blue = random.randint(start, end)
    return (red, green, blue) if opacity is None else (red, green, blue, opacity)
