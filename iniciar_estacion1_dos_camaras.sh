#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

if [[ -x ".venv/bin/python" ]]; then
    python=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    python="$(command -v python3)"
else
    printf 'Error: no se encontró Python 3.\n' >&2
    exit 1
fi

if ! command -v udevadm >/dev/null 2>&1; then
    printf 'Error: no se encontró udevadm; se necesita para identificar cámaras USB.\n' >&2
    exit 1
fi

shopt -s nullglob
candidates=(/dev/v4l/by-id/*-video-index0 /dev/v4l/by-path/*usb*-video-index0)
declare -A seen
devices=()
labels=()

for candidate in "${candidates[@]}"; do
    resolved="$(readlink -f "$candidate")"
    [[ -n "${seen[$resolved]:-}" ]] && continue
    properties="$(udevadm info --query=property --name="$resolved" 2>/dev/null || true)"
    grep -q '^ID_BUS=usb$' <<<"$properties" || continue
    grep -q '^ID_V4L_CAPABILITIES=.*:capture:' <<<"$properties" || continue
    seen[$resolved]=1
    devices+=("$candidate")
    model="$(sed -n 's/^ID_MODEL_FROM_DATABASE=//p; s/^ID_MODEL=//p' <<<"$properties" | head -n 1)"
    labels+=("${model:-Cámara USB} — $candidate")
done

if (( ${#devices[@]} < 2 )); then
    printf 'Error: se encontraron %d cámaras USB de captura; se necesitan al menos dos.\n' "${#devices[@]}" >&2
    printf 'Conecta ambas cámaras y revisa /dev/v4l/by-id o /dev/v4l/by-path.\n' >&2
    exit 1
fi

selected=()
if (( ${#devices[@]} == 2 )); then
    selected=(0 1)
else
    printf 'Se detectaron %d cámaras USB; elige las dos cámaras externas (no la integrada):\n' "${#devices[@]}"
    for i in "${!devices[@]}"; do
        printf '  %d) %s\n' "$((i + 1))" "${labels[$i]}"
    done
    for position in 1 2; do
        while true; do
            read -r -p "Número de la cámara USB externa $position: " choice
            if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#devices[@]} )); then
                index=$((choice - 1))
                if [[ ! " ${selected[*]:-} " =~ " $index " ]]; then
                    selected+=("$index")
                    break
                fi
            fi
            printf 'Selección no válida; elige una cámara distinta de la anterior.\n' >&2
        done
    done
fi

printf 'Cámara USB 1: %s\nCámara USB 2: %s\n' \
    "${labels[${selected[0]}]}" "${labels[${selected[1]}]}"
read -r -p "ID del lote (ej. Prueba_001) [Prueba_001]: " lot
lot="${lot:-Prueba_001}"
read -r -p "¿Captura automática al pasar la fruta? (S/N) [N]: " auto_mode

args=( -m src.paired_capture --lot "$lot"
       --camera "${devices[${selected[0]}]}"
       --camera-2 "${devices[${selected[1]}]}" )
if [[ "$auto_mode" =~ ^[sS]$ ]]; then
    args+=(--auto)
fi

exec "$python" "${args[@]}"
