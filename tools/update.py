#!/usr/bin/env python3
"""Пълно обновяване на участъците за средна скорост.

1. Тегли списъка на BG TOLL (сертифицирани отсечки).
2. Тегли от OpenStreetMap (Overpass) тол рамките, населените места и пътищата.
3. Пуска build.py/build6.py (координати) и limits.py (ограничения).
4. Ако резултатът се различава от публикувания sections.json и мине проверките,
   записва нова версия чрез publish.py.

Употреба (от корена на хранилището):  python3 tools/update.py
Изход: в $GITHUB_OUTPUT се записва changed=true/false.
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PUBLISHED = os.path.join(ROOT, "sections.json")
BGTOLL_URL = "https://www.bgtoll.bg/vaprosi-i-otgovori/sredna-skorost/wim"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
UA = "avgspeed-bg-data/1.0 (+github actions)"

MOTORWAYS = {"Тракия": "A 1", "Хемус": "A 2", "Струма": "A 3", "Марица": "A 4",
             "Черно море": "A 5", "Европа": "A 6", "Русе": "A 7"}


def http_get(url, data=None, timeout=300):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def overpass(query, out, min_elements):
    """Заявка към Overpass. Отговорът се приема само ако има поне `min_elements` елемента
    и няма съобщение за грешка – претоварен сървър или огледало с остарели данни връщат
    „празен“, но синтактично валиден JSON, който не бива да стига до изчисленията."""
    body = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for attempt in range(6):
        url = OVERPASS[attempt % len(OVERPASS)]
        try:
            raw = http_get(url, body, timeout=320)
            d = json.loads(raw)
            n = len(d.get("elements", []))
            remark = d.get("remark", "")
            if remark or n < min_elements:
                raise ValueError(f"{url}: {n} елемента{', ' + remark[:120] if remark else ''}")
            open(out, "wb").write(raw)
            print(f"   {out}: {n} елемента")
            return
        except Exception as e:  # сървърът често е зает – опитваме пак
            last = e
            print(f"   опит {attempt + 1}: {e}")
            time.sleep(30)
    raise RuntimeError(f"Overpass не даде пълни данни: {last}")


def road_ref(road):
    for name, ref in MOTORWAYS.items():
        if name in road:
            return ref
    m = re.match(r"^(I{1,3})-(\d+)$", road.strip())
    if m:
        return m.group(2)
    raise ValueError(f"Непознат път: {road}")


def parse_bgtoll(page):
    tables = re.findall(r"<table.*?</table>", page, re.S)
    out = []
    for ti, t in enumerate(tables):
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            if len(cells) < 3:
                continue

            def pt(c):
                m = re.match(r"(.+?)\s*\(км\s*(\d+)\+(\d+)\)\s*(.*)", c)
                if not m:
                    raise ValueError(f"Не мога да прочета точка: {c}")
                return dict(name=m.group(1).strip(), km=int(m.group(2)) + int(m.group(3)) / 1000,
                            note=m.group(4).strip())
            out.append(dict(road=cells[0], start=pt(cells[1]), end=pt(cells[2]), pending=ti > 0))
    return out


def comparable(sections):
    """Съдържанието без служебни полета – за да не публикуваме версия без промяна."""
    return json.dumps(sorted(sections, key=lambda s: (s["road"], s["start"]["km"], s["end"]["km"])),
                      ensure_ascii=False, sort_keys=True)


def set_output(changed):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


def main():
    work = tempfile.mkdtemp(prefix="avgspeed-")
    for f in ("build.py", "build6.py", "limits.py"):
        shutil.copy(os.path.join(TOOLS, f), work)
    os.chdir(work)

    print("1/4 BG TOLL…")
    secs = parse_bgtoll(http_get(BGTOLL_URL, timeout=60).decode("utf-8"))
    if len(secs) < 10:
        sys.exit(f"Подозрително малко участъци на BG TOLL ({len(secs)}) – спирам.")
    json.dump(secs, open("sections.json", "w"), ensure_ascii=False)
    refs = {s["road"]: road_ref(s["road"]) for s in secs}
    json.dump(refs, open("roadref.json", "w"), ensure_ascii=False)
    print(f"   {len(secs)} участъка, пътища: {sorted(set(refs.values()))}")

    print("2/4 OpenStreetMap…")
    area = 'area["ISO3166-1"="BG"][admin_level=2]->.a;'
    overpass(f'[out:json][timeout:200];{area}(relation["type"="enforcement"](area.a););out body;'
             f'(node["highway"="speed_camera"](area.a);node["highway"="toll_gantry"](area.a););out;', "osm1.json", 150)
    overpass(f'[out:json][timeout:200];{area}node[place~"^(city|town|village|hamlet)$"](area.a);out;', "osm3.json", 4000)
    ref_re = "|".join(re.escape(r) for r in sorted(set(refs.values())))
    overpass(f'[out:json][timeout:300];{area}way[highway~"^(motorway|trunk|primary|secondary)$"]'
             f'[ref~"^({ref_re})(;|$)"](area.a);out tags geom;', "roads.json", 3000)

    print("3/4 Координати и ограничения…")
    subprocess.run([sys.executable, "-I", "build6.py"], check=True)
    subprocess.run([sys.executable, "-I", "limits.py"], check=True)
    data = json.load(open("avg_sections_limits.json"))
    for o in data:  # предпазлива стойност по подразбиране
        w = o.get("weightedLimit") or o["speedLimit"]
        o["speedLimit"] = min(o["speedLimit"], int(w // 10 * 10))
    json.dump(data, open("array.json", "w"), ensure_ascii=False)

    print("4/4 Сравнение и публикуване…")
    prev = json.load(open(PUBLISHED)) if os.path.exists(PUBLISHED) else {"sections": []}
    if prev["sections"] and len(data) < 0.8 * len(prev["sections"]):
        sys.exit(f"Броят падна от {len(prev['sections'])} на {len(data)} – не публикувам, нужна е ръчна проверка.")
    prev_ok = sum(1 for s in prev["sections"] if s.get("verified"))
    now_ok = sum(1 for s in data if s.get("verified"))
    if prev_ok and now_ok < prev_ok - 3:
        sys.exit(f"Верифицираните участъци паднаха от {prev_ok} на {now_ok} – не публикувам, нужна е ръчна проверка.")
    if comparable(data) == comparable(prev["sections"]):
        print("Няма промяна.")
        set_output(False)
        return
    subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "publish.py"), "array.json", PUBLISHED,
                    "--previous", PUBLISHED] if os.path.exists(PUBLISHED) else
                   [sys.executable, "-I", os.path.join(TOOLS, "publish.py"), "array.json", PUBLISHED], check=True)
    unverified = [f"{o['road']} {o['start']['name']}→{o['end']['name']}" for o in data if not o["verified"]]
    if unverified:
        print("Неверифицирани участъци (проверете ръчно):", *unverified, sep="\n  ")
    set_output(True)


if __name__ == "__main__":
    main()
