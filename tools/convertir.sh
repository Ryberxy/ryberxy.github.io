#!/usr/bin/env bash
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
FILTRO="$RAIZ/tools/filtro.lua"
FORZAR=0
[[ "${1:-}" == "-f" ]] && FORZAR=1

command -v pandoc >/dev/null || { echo "Falta pandoc (sudo apt install pandoc)"; exit 1; }

find "$RAIZ/content/posts" -mindepth 1 -iname "*.docx" -print0 |
while IFS= read -r -d '' docxpath; do
  dir="$(dirname "$docxpath")"
  archivo="$(basename "$docxpath")"
  nombre="${archivo%.docx}"

  if [[ -f "$dir/index.md" && $FORZAR -eq 0 ]]; then continue; fi

  categoria="$(basename "$(dirname "$dir")")"
  titulo="${nombre//\"/\\\"}"

  echo "→ Convirtiendo: $docxpath"

  # Crea _index.md en cada carpeta de categoría intermedia que no lo tenga
  ancestor="$(dirname "$dir")"
  while [[ "$ancestor" != "$RAIZ/content/posts" && "$ancestor" != "/" ]]; do
    if [[ ! -f "$ancestor/_index.md" ]]; then
      nombre_cat="$(basename "$ancestor")"
      titulo_cat="$(echo "$nombre_cat" | sed 's/-/ /g' | sed 's/\b\(.\)/\u\1/g')"
      cat > "$ancestor/_index.md" <<CAT
---
title: "$titulo_cat"
---
CAT
    fi
    ancestor="$(dirname "$ancestor")"
  done

  if [[ -f "$dir/index.md" ]]; then
    awk '/^---$/{c++} {print} c==2{exit}' "$dir/index.md" > "$dir/.front.md"
    echo "" >> "$dir/.front.md"
  else
    cat > "$dir/.front.md" <<FRONT
---
title: "$titulo"
date: $(date +%F)
description: ""
tags: []
---

FRONT
  fi

  ( cd "$dir" && pandoc "$archivo" -t gfm --wrap=none --extract-media=. \
      --lua-filter="$FILTRO" -o .cuerpo.md )

  cat "$dir/.front.md" "$dir/.cuerpo.md" > "$dir/index.md"
  rm -f "$dir/.front.md" "$dir/.cuerpo.md"

  if ! ls "$dir"/featured.* >/dev/null 2>&1; then
    img="$(grep -oEm1 'media/[A-Za-z0-9_.-]+\.(png|jpe?g|gif|webp)' "$dir/index.md" || true)"
    if [[ -n "$img" ]]; then
      cp "$dir/$img" "$dir/featured.${img##*.}"
    fi
  fi

  echo "  ✔ $dir index.md listo"
done
