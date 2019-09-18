#!/usr/bin/env python3
"""
Clears cache from the default tmp directory
"""
from diskcache import Cache
import tempfile

cache = Cache(tempfile.gettempdir())
cache.clear()
