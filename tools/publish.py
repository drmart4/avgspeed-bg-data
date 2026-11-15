#!/usr/bin/env python3
"""Пакетира участъците във версиониран JSON за приложението.

Употреба:
    python3 publish.py <участъци.json> <изход.json> [--previous <предишен публикуван.json>]

Входът е масивът от build6.py/limits.py. Изходът е:
    {"version": "ГГГГ-ММ-ДД.N", "generated": "...", "source": "...", "sections": [...]}
Версията расте автоматично: ако предишната е от същия ден, N се увеличава.
Преди запис данните минават същата проверка като в приложението.
"""
import datetime
import json
import sys


def validate(sections):
    assert len(sections) >= 10, "твърде малко участъци"
    ids = [s["id"] for s in sections]
    assert len(set(ids)) == len(ids), "повтарящи се ID"
    for s in sections:
        for p in (s["start"], s["end"]):
            assert 41.0 <= p["lat"] <= 44.4 and 22.2 <= p["lon"] <= 28.8, f"извън България: {s['id']}"
        assert 0.3 < s["lengthKm"] < 100, f"странна дължина: {s['id']}"
        assert 30 <= s["speedLimit"] <= 140, f"странно ограничение: {s['id']}"


def next_version(previous):
    today = datetime.date.today().isoformat()
    if previous and previous.startswith(today):
        n = int(previous.split(".")[-1]) if "." in previous else 1
        return f"{today}.{n + 1}"
    return f"{today}.1"


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    src, dst = args[0], args[1]
    prev_version = None
    if "--previous" in args:
        with open(args[args.index("--previous") + 1], encoding="utf-8") as f:
            prev = json.load(f)
            prev_version = prev.get("version") if isinstance(prev, dict) else None

    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    sections = data["sections"] if isinstance(data, dict) else data
    validate(sections)

    out = {
        "version": next_version(prev_version),
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "BG TOLL (списък на сертифицираните отсечки) + © OpenStreetMap contributors (ODbL)",
        "sections": sections,
    }
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"{dst}: версия {out['version']}, {len(sections)} участъка")


if __name__ == "__main__":
    main()
