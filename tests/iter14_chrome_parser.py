# Unit check of desktop read_chrome_bookmarks (run: PYTHONPATH=backend:desktop:desktop/shadow_helper python tests/iter14_chrome_parser.py)
import json
import tempfile
from pathlib import Path

import core

tmp = Path(tempfile.mkdtemp())
core.chrome_user_data = lambda: tmp
try:
    core.read_chrome_bookmarks()
    print("FAIL no error when no files")
except ValueError as e:
    print("OK no files ->", e)

data = {"roots": {
    "bookmark_bar": {"type": "folder", "name": "Bookmarks bar", "children": [
        {"type": "url", "name": "Top", "url": "https://top.example.com"},
        {"type": "url", "name": "JS", "url": "javascript:void(0)"},
        {"type": "url", "name": "Chrome", "url": "chrome://settings"},
        {"type": "folder", "name": "Work", "children": [
            {"type": "url", "name": "", "url": "http://work.example.com"},
            {"type": "folder", "name": "Deep", "children": [{"type": "url", "name": "D", "url": "https://deep.example.com"}]}]}]},
    "other": {"type": "folder", "name": "Other", "children": [{"type": "url", "name": "O", "url": "https://other.example.com"},
                                                               {"type": "url", "name": "Dup", "url": "https://top.example.com"}]},
    "synced": {"type": "folder", "name": "Mobile", "children": [{"type": "url", "name": "M", "url": "https://m.example.com"}]}}}
(tmp / "Default").mkdir()
(tmp / "Default" / "Bookmarks").write_text(json.dumps(data))
(tmp / "Profile 1").mkdir()
(tmp / "Profile 1" / "Bookmarks").write_text("not json")
out = core.read_chrome_bookmarks()
for o in out:
    print(o)
exp = [("https://top.example.com", ""), ("http://work.example.com", "Work"), ("https://deep.example.com", "Work / Deep"),
       ("https://other.example.com", "Other bookmarks"), ("https://m.example.com", "Mobile bookmarks")]
got = [(o["url"], o["folder"]) for o in out]
print("PASS" if got == exp else f"FAIL expected {exp}")
assert out[1]["title"] == "http://work.example.com"
print("limit:", len(core.read_chrome_bookmarks(limit=2)))
