#!/usr/bin/env python3
"""输出当前日期（本地时区），供深度检索的时效判定作基准。

用法:
  python -X utf8 today.py                    # 默认 Asia/Shanghai，输出 YYYY-MM-DD
  python -X utf8 today.py --full             # 附加星期与时间
  python -X utf8 today.py --timezone UTC     # 覆盖时区
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def resolve_timezone(name: str):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name.upper() in ("UTC", "ETC/UTC"):
            return timezone.utc
        if name == "Asia/Shanghai":
            return timezone(timedelta(hours=8), name="Asia/Shanghai")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="输出当前日期")
    parser.add_argument("--full", action="store_true", help="附加星期与时间")
    parser.add_argument(
        "--timezone",
        default="Asia/Shanghai",
        help="IANA 时区名，默认 Asia/Shanghai",
    )
    args = parser.parse_args()
    try:
        zone = resolve_timezone(args.timezone)
    except ZoneInfoNotFoundError:
        parser.error(f"未知时区: {args.timezone}")
    now = datetime.now(zone)
    if args.full:
        weekdays = "一二三四五六日"
        print(f"{now:%Y-%m-%d} 星期{weekdays[now.weekday()]} {now:%H:%M:%S} {now:%z}")
    else:
        print(f"{now:%Y-%m-%d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
