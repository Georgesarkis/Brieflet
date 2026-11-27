"""A model's reply → the JSON object in it (or None). Tolerates prose around the object."""
from __future__ import annotations

import json
import re


def parse_json(text: str):
    try:
        return json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text or "", re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None
