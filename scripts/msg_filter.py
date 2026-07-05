"""Git msg-filter: strip Cursor co-author trailer from commit messages."""
from __future__ import annotations

import re
import sys

COAUTHOR = re.compile(r"^Co-authored-by: Cursor <cursoragent@cursor\.com>\s*\n?", re.MULTILINE)

text = sys.stdin.read()
text = COAUTHOR.sub("", text)
text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
sys.stdout.write(text)
