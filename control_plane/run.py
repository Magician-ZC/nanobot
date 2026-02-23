#!/usr/bin/env python3
"""Control Plane 启动入口

独立部署时，将整个 control_plane/ 目录拷贝出去，
目录本身就是 Python 包，run.py 在包内部。

启动方式：
  cd control_plane
  python run.py

或从外部：
  python -m control_plane.run
  uvicorn control_plane.app:create_app --factory --host 0.0.0.0 --port 8080
"""

import argparse
import os
import sys
from pathlib import Path

# 确保父目录在 sys.path 中，使 `from control_plane.xxx` 能正常工作
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)


def main():
    parser = argparse.ArgumentParser(description="Nanobot Control Plane")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", "-p", type=int, default=8080, help="监听端口 (默认: 8080)")
    parser.add_argument("--db", default=None, help="数据库文件路径 (默认: data/control_plane.db)")
    args = parser.parse_args()

    import uvicorn
    from control_plane.app import create_app

    db_path = Path(args.db) if args.db else None
    app = create_app(db_path=db_path)

    print(f"🚀 启动 Control Plane 服务...")
    print(f"   地址: http://{args.host}:{args.port}")
    print(f"   数据库: {args.db or 'data/control_plane.db'}")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
