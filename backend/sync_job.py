"""Executa sync do Blackboard e imprime JSON no stdout."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.scraper.sync import sync_blackboard


def main() -> None:
    result = asyncio.run(sync_blackboard())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
