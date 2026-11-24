"""Shared lexical definitions for formula parsing and formatting."""

import re


LTL_KEYWORDS = {"true", "false", "X", "F", "G", "U", "W", "R"}

LTL_TEMPORAL_CHAIN = re.compile(r"[XFG]+")

CTL_KEYWORDS = {"true", "false", "E", "A", "X", "F", "G", "U", "W"}

CTL_OPERATOR_CHAIN = re.compile(r"[EAXFGUW]+")
