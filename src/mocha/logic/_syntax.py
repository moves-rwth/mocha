"""Shared lexical definitions for formula parsing and formatting."""

import re


LTL_KEYWORDS = {"true", "false", "X", "F", "G", "U", "W", "R"}

LTL_TEMPORAL_CHAIN = re.compile(r"[XFG]+")
