#!/usr/bin/env bash
# Kopiuje biblioteki Hikvision SDK do katalogu add-ona.
# Uruchom raz przed git add/push.
#
# Użycie:  ./setup-sdk.sh
#          ./setup-sdk.sh /inna/sciezka/do/Hikvision-Addons

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HIK_ROOT="${1:-${SCRIPT_DIR}/../MultiWAN/Hikvision-Addons/hikvision-doorbell}"
DEST="${SCRIPT_DIR}/hikvision-relay/sdk"

if [ ! -d "$HIK_ROOT" ]; then
    echo "BŁĄD: nie znaleziono Hikvision-Addons w: $HIK_ROOT"
    echo "Podaj ścieżkę jako argument:  ./setup-sdk.sh /sciezka/do/Hikvision-Addons/hikvision-doorbell"
    exit 1
fi

for ARCH in aarch64 amd64; do
    SRC="${HIK_ROOT}/lib-${ARCH}"
    DST="${DEST}/${ARCH}"
    if [ ! -d "$SRC" ]; then
        echo "POMINIĘTO: brak ${SRC}"
        continue
    fi
    mkdir -p "$DST"
    rsync -a --delete "${SRC}/" "${DST}/"
    echo "OK: skopiowano ${ARCH} → ${DST}"
done

echo ""
echo "Gotowe! Teraz możesz:"
echo "  cd ${SCRIPT_DIR}"
echo "  git init && git add -A && git commit -m 'initial'"
echo "  git remote add origin https://github.com/TWOJ_USER/TWOJE_REPO.git"
echo "  git push -u origin main"
