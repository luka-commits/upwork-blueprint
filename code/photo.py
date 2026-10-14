#!/usr/bin/env python3
"""A picture as a `data:` URI, ready to paste into a page.

    python3 code/photo.py ~/Desktop/me.jpg
    python3 code/photo.py ~/Desktop/me.jpg --into jobs/2104512976561523960/pitch.html

The page is one HTML file the member opens and shows in the Loom, so every image on
it has to live inside that file. Converting a photo by hand is a detour through a website
nobody should have to find, and the first member who tries it pastes a 4 MB phone
picture into a page that then takes six seconds to open on a phone.

So this does the whole job: square crop from the centre, resized, re-encoded, and the
result printed or written straight into the page's photo slot. It refuses a file it
would make worse rather than quietly shipping it.
"""
import argparse
import base64
import io
import pathlib
import re
import sys

SIZE = 320          # twice the largest the card draws it, so it stays sharp on a phone
BUDGET = 120_000    # characters of data URI: past this a page starts to feel heavy
# The placeholder the templates ship: a div carrying the photo class, whatever else it
# carries with it. It is replaced whole, because an img is what the page wants there.
SLOT = re.compile(r'<div class="photo[^"]*"[^>]*>.*?</div>', re.S)


def abort(message):
    print(f'ABORT: {message}', file=sys.stderr)
    raise SystemExit(1)


def square(image):
    """The middle square, because a face sits in the middle and a card is round."""
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def data_uri(path, size=SIZE):
    try:
        from PIL import Image
    except ImportError:
        abort('Pillow is missing. Run: python3 -m pip install -r requirements.txt')
    try:
        image = Image.open(path)
    except OSError as error:
        abort(f'{path} could not be read as an image: {error}')
    image = square(image.convert('RGB')).resize((size, size), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=82, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/jpeg;base64,{encoded}'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('photo')
    ap.add_argument('--into', help='a pitch page: the photo slot is filled in place')
    ap.add_argument('--size', type=int, default=SIZE)
    args = ap.parse_args(argv)
    source = pathlib.Path(args.photo).expanduser()
    if not source.is_file():
        abort(f'{source} is not a file.')
    uri = data_uri(source, args.size)
    if len(uri) > BUDGET:
        abort(f'the encoded photo is {len(uri):,} characters, over the {BUDGET:,} this page '
              f'should carry. Try --size {args.size // 2}.')
    if not args.into:
        print(uri)
        return 0
    page = pathlib.Path(args.into)
    if not page.is_file():
        abort(f'{page} does not exist yet. Build the page first.')
    text = page.read_text(encoding='utf-8')
    if not SLOT.search(text):
        abort('this page has no <div class="photo"> slot, so there is nothing to fill.')
    filled = SLOT.sub(f'<img class="photo" src="{uri}" alt="" />', text, count=1)
    page.write_text(filled, encoding='utf-8')
    print(f'{page}: photo embedded, {len(uri):,} characters.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
