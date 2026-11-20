"""Serial delivery to estacion2 station_listener (one JPEG, trigger, ACK)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from .client_e2 import _atomic_bytes


def drain(outbox: Path, channel: Path, timeout: float = 10.0) -> int:
    """One exclusive sender. Preserve in-flight work on timeout; never overwrite it."""
    channel.mkdir(parents=True, exist_ok=True)
    receipts = outbox / '.e2_receipts'
    receipts.mkdir(parents=True, exist_ok=True)
    lock = channel / 'estacion1_sender.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    pending = channel / 'estacion1_pending.json'
    trigger, ack = channel/'estacion_trigger.flag', channel/'estacion_ack.flag'
    result_path = channel/'estacion2_result.json'
    count = 0
    try:
        for manifest in sorted(outbox.rglob('*.json')):
            if '.e2_receipts' in manifest.parts:
                continue
            metadata = json.loads(manifest.read_text(encoding='utf-8'))
            if metadata.get('estado_captura') != 'aceptada':
                continue
            if not metadata.get('vistas') or any(v.get('metodo_posicion') != 'yolo'
                                                 for v in metadata['vistas']):
                continue  # Never send old captures accepted using scene/background checks.
            for view in metadata['vistas']:
                key = metadata['id_captura'] + '_' + view['camara']
                receipt = receipts / (key + '.json')
                if receipt.exists():
                    continue
                photo = manifest.parent / Path(view['imagen']).name
                data = photo.read_bytes()
                if hashlib.sha256(data).hexdigest() != view['sha256']:
                    raise ValueError(f'Hash incorrecto: {photo}')
                identity = {'key': key, 'id_fruta': metadata['id_fruta'],
                            'id_lote': metadata['id_lote'], 'camara': view['camara'],
                            'id_rafaga': metadata.get('id_rafaga'),
                            'indice_rafaga': metadata.get('indice_rafaga')}
                if pending.exists():
                    previous = json.loads(pending.read_text(encoding='utf-8'))
                    if previous != identity:
                        raise RuntimeError('Hay otra imagen pendiente en el canal; no se sobrescribe')
                else:
                    if trigger.exists():
                        raise RuntimeError('Canal ocupado por una imagen anterior')
                    ack.unlink(missing_ok=True)
                    result_path.unlink(missing_ok=True)
                    _atomic_bytes(channel/'estacion_frame.jpg', data)
                    _atomic_bytes(pending, json.dumps(identity).encode('utf-8'))
                    _atomic_bytes(trigger, str(time.time()).encode('ascii'))
                deadline = time.monotonic() + timeout
                while not (ack.exists() and result_path.exists() and not trigger.exists()):
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Estación 2 no confirmó; imagen pendiente preservada. Reejecuta el envío tras iniciar el receptor')
                    time.sleep(0.01)
                result = json.loads(result_path.read_text(encoding='utf-8'))
                if result.get('station_id') != 2 or 'predicted_class' not in result:
                    raise ValueError('Respuesta inesperada de estación 2')
                _atomic_bytes(receipt, json.dumps({**identity, 'resultado_e2': result},
                                                ensure_ascii=False, indent=2).encode('utf-8'))
                pending.unlink()
                count += 1
        return count
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outbox', type=Path, default=Path('salidas_estacion2'))
    parser.add_argument('--channel', type=Path, required=True,
                        help='Misma carpeta que --shm-dir del listener E2, en el mismo equipo')
    parser.add_argument('--timeout', type=float, default=10)
    args = parser.parse_args()
    print(f'Vistas confirmadas por E2: {drain(args.outbox, args.channel, args.timeout)}')


if __name__ == '__main__':
    main()
