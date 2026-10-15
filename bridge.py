# -*- coding: utf-8 -*-
"""引用ブリッジの入口。使い方は README.md と SKILL.md、ファイル形式は SPEC.md。実装は cite_bridge/ にある。

    python bridge.py <コマンド> ...    コマンドの一覧は python bridge.py --help
"""
import sys
from pathlib import Path

# python -I（isolated）で呼ばれても cite_bridge を見つけられるよう、このファイルのあるフォルダを足す
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cite_bridge.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
