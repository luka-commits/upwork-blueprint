"""Reads simple KEY=VALUE files such as .env into a dict."""
import re


def load_dotenv(path, env):
    """Load simple KEY=VALUE lines without replacing exported values.

    An empty value does not count as a value. `.env` is copied from
    `.env.example`, which lists every key with nothing after the equals sign, so
    plain setdefault let that placeholder shadow the real key in
    `~/.config/credentials.env`: setup.sh found the key, the preflight did not,
    and the member was told to buy a service they already pay for.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if value[:1] == value[-1:] and value[:1] in ('"', "'"):
            value = value[1:-1]
        if value.strip() and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) and not str(env.get(key) or '').strip():
            env[key] = value
