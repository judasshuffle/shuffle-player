"""Centralised paths for shuffle-player. Override via environment variables."""
import os

# Env var names (optional overrides)
_ENV_MUSIC_ROOT = "JUKEBOX_MUSIC_ROOT"
_ENV_DB_PATH = "JUKEBOX_DB_PATH"
_ENV_INDEX_JSON_PATH = "JUKEBOX_INDEX_JSON_PATH"
_ENV_ARTISTS_PATH = "JUKEBOX_ARTISTS_PATH"

# Defaults
_DEFAULT_MUSIC_ROOT = "/mnt/lossless"
_DEFAULT_DB_PATH = "/home/dan/jukebox.db"
_DEFAULT_INDEX_JSON_PATH = "/home/dan/jukebox_index.json"
_DEFAULT_ARTISTS_PATH = "artists.txt"

MUSIC_ROOT = os.environ.get(_ENV_MUSIC_ROOT, _DEFAULT_MUSIC_ROOT)
DB_PATH = os.environ.get(_ENV_DB_PATH, _DEFAULT_DB_PATH)
INDEX_JSON_PATH = os.environ.get(_ENV_INDEX_JSON_PATH, _DEFAULT_INDEX_JSON_PATH)
ARTISTS_PATH = os.environ.get(_ENV_ARTISTS_PATH, _DEFAULT_ARTISTS_PATH)
