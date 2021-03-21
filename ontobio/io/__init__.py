from __future__ import absolute_import
from .ontol_renderers import GraphRenderer
from .assocwriter import GafWriter, GpadWriter

import re
parser_version_regex = re.compile(r"!([\w]+)-version:[\s]*([\d]+\.[\d]+(\.[\d]+)?)")

