#!/bin/bash
# Седмично обновяване на участъците от Mac (BG TOLL не допуска заявки от сървърите на GitHub).
# Пуска се от LaunchAgent bg.avgspeed.update; лог: ~/Library/Logs/avgspeed-update.log
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
echo "=== $(date '+%Y-%m-%d %H:%M') ==="

git pull --ff-only -q
/Users/macbookpro/.pyenv/versions/3.11.7/bin/python3 -I -u tools/update.py

if [[ -n "$(git status --porcelain sections.json)" ]]; then
    VERSION=$(/Users/macbookpro/.pyenv/versions/3.11.7/bin/python3 -c 'import json;print(json.load(open("sections.json"))["version"])')
    git add sections.json
    git -c user.name="avgspeed-bot" -c user.email="avgspeed-bot@users.noreply.github.com" \
        commit -q -m "Участъци: $VERSION"
    git push -q
    echo "Публикувана версия $VERSION"
else
    echo "Без промяна."
fi
