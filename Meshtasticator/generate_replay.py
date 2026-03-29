#!/usr/bin/env python3
"""
generate_replay.py
==================
Читает реальные замеры из output.xlsx и генерирует:
  1. out/nodeConfig.yaml  — координаты нод для симулятора
  2. out/replay_script.py — скрипт воспроизведения для запуска с флагом -s
  3. out/real_stats.txt   — статистика реальных замеров для сравнения

Использование:
  python3 generate_replay.py --xlsx output.xlsx --out-dir out/

Затем запускай симуляцию:
  python3 interactiveSim.py 3 -s -p ../firmware/.pio/build/native/program
"""

import argparse
import os
import datetime
from collections import defaultdict

try:
    import openpyxl
except ImportError:
    print("Установи openpyxl: pip install openpyxl")
    exit(1)

try:
    import yaml
except ImportError:
    print("Установи pyyaml: pip install pyyaml")
    exit(1)


def load_data(xlsx_path):
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    return rows


def extract_nodes(rows):
    """Извлекаем уникальные ноды с их координатами."""
    nodes = {}
    for r in rows:
        node_id = r[2]
        if node_id and node_id not in nodes:
            nodes[node_id] = {
                "name": r[3],
                "lat": r[4],
                "lon": r[5],
                "alt": r[12] if r[12] else 0,
            }
    return nodes


def extract_messages(rows):
    """Извлекаем только текстовые сообщения (не POSITION/TELEMETRY)."""
    messages = []
    for r in rows:
        payload = r[8]
        if payload and payload not in ("<POSITION_APP>", "<TELEMETRY_APP>"):
            messages.append({
                "time": r[1],
                "from_id": r[2],
                "from_name": r[3],
                "dist": r[6],
                "hop": r[7],
                "snr": float(str(r[13]).replace(",", ".")) if r[13] else None,
                "rssi": r[14],
                "airtime": r[9],
                "text": payload,
            })
    return messages


def extract_stats(rows):
    """Считаем статистику по реальным замерам."""
    stats = defaultdict(lambda: {
        "packets": 0, "snr_vals": [], "rssi_vals": [],
        "dist_vals": [], "airtime_total": 0
    })

    for r in rows:
        name = r[3]
        snr = float(str(r[13]).replace(",", ".")) if r[13] else None
        rssi = r[14]
        dist = r[6]
        airtime = r[9] if r[9] else 0

        stats[name]["packets"] += 1
        if snr is not None:
            stats[name]["snr_vals"].append(snr)
        if rssi:
            stats[name]["rssi_vals"].append(rssi)
        if dist:
            stats[name]["dist_vals"].append(dist)
        stats[name]["airtime_total"] += airtime

    return stats


def gps_to_meters(lat, lon, alt, ref_lat, ref_lon, ref_alt):
    """Конвертируем GPS координаты в метры относительно референсной точки."""
    import math
    R = 6371000  # радиус Земли в метрах
    x = math.radians(lon - ref_lon) * R * math.cos(math.radians(ref_lat))
    y = math.radians(lat - ref_lat) * R
    z = (alt if alt else 0) - (ref_alt if ref_alt else 0)
    return round(x, 2), round(y, 2), round(z, 2)


def write_node_config(nodes, out_dir):
    """Генерируем nodeConfig.yaml в формате который ожидает симулятор."""
    import yaml

    # Центральная точка — средняя из всех нод
    lats = [info['lat'] for info in nodes.values()]
    lons = [info['lon'] for info in nodes.values()]
    alts = [info['alt'] for info in nodes.values() if info['alt']]
    ref_lat = sum(lats) / len(lats)
    ref_lon = sum(lons) / len(lons)
    ref_alt = sum(alts) / len(alts) if alts else 0

    node_dict = {}
    for i, (node_id, info) in enumerate(nodes.items()):
        x, y, z = gps_to_meters(info['lat'], info['lon'], info['alt'], ref_lat, ref_lon, ref_alt)
        node_dict[i] = {
            'x': x,
            'y': y,
            'z': z,
            'isRouter': False,
            'isRepeater': False,
            'isClientMute': False,
            'hopLimit': 3,
            'antennaGain': 0,
            'neighborInfo': False,
        }
        print(f"  Нода {i} ({info['name']}): x={x}м, y={y}м, z={z}м")

    path = os.path.join(out_dir, "nodeConfig.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(node_dict, f)
    print(f"[✓] Записан {path}")
    return path


def write_replay_script(nodes, messages, out_dir):
    """
    Генерируем скрипт для вставки в блок try в interactiveSim.py.
    Симулятор запускается с -s флагом и читает этот скрипт.
    """
    # Маппинг node_id -> индекс (0,1,2...)
    node_index = {nid: i for i, nid in enumerate(nodes.keys())}

    path = os.path.join(out_dir, "replay_script.py")

    lines = [
        "# ============================================================",
        "# Автогенерированный replay из реальных замеров output.xlsx",
        f"# Нод: {len(nodes)}, сообщений: {len(messages)}",
        f"# Сгенерирован: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "# ============================================================",
        "",
        "# Вставь этот код в блок try в interactiveSim.py",
        "# вместо существующего содержимого try-блока.",
        "",
        "import time",
        "",
        "# Ждём пока ноды обменяются NodeInfo",
        "print('Ожидание обмена NodeInfo между нодами...')",
        "time.sleep(15)",
        "",
        "print('Начинаем воспроизведение реальных сообщений...')",
        "",
    ]

    # Сортируем сообщения по времени
    def parse_time(t):
        if isinstance(t, datetime.time):
            return t
        try:
            return datetime.datetime.strptime(str(t), "%H:%M:%S").time()
        except:
            return datetime.time(0, 0, 0)

    sorted_msgs = sorted(messages, key=lambda m: parse_time(m["time"]))

    prev_time = None
    for msg in sorted_msgs:
        t = parse_time(msg["time"])
        from_idx = node_index.get(msg["from_id"], 0)
        text = msg["text"].replace('"', '\\"').replace("'", "\\'")

        # Пауза между сообщениями
        if prev_time is not None:
            prev_dt = datetime.datetime.combine(datetime.date.today(), prev_time)
            curr_dt = datetime.datetime.combine(datetime.date.today(), t)
            delta = (curr_dt - prev_dt).total_seconds()
            if 0 < delta <= 120:
                lines.append(f"time.sleep({int(delta)})  # пауза {delta:.0f}с")
            elif delta > 120:
                lines.append(f"time.sleep(5)  # пауза сокращена с {delta:.0f}с до 5с")
        prev_time = t

        snr_info = f"snr={msg['snr']}" if msg['snr'] else ""
        rssi_info = f"rssi={msg['rssi']}" if msg['rssi'] else ""
        lines.append(
            f"# {msg['time']} | {msg['from_name']} | dist={msg['dist']}m | {snr_info} {rssi_info}"
        )
        lines.append(
            f"sim.send_broadcast('{text}', {from_idx})"
        )
        lines.append("")

    lines += [
        "print('Все сообщения отправлены!')",
        "time.sleep(10)  # ждём доставки последних пакетов",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[✓] Записан {path}")
    return path


def write_stats(rows, nodes, messages, out_dir):
    """Записываем статистику реальных замеров для сравнения с симулятором."""
    stats = extract_stats(rows)
    path = os.path.join(out_dir, "real_stats.txt")

    lines = [
        "=" * 60,
        "СТАТИСТИКА РЕАЛЬНЫХ ЗАМЕРОВ",
        "=" * 60,
        f"Всего пакетов: {len(rows)}",
        f"Текстовых сообщений: {len(messages)}",
        f"Нод: {len(nodes)}",
        "",
        "ПО НОДАМ:",
        "-" * 40,
    ]

    for name, s in stats.items():
        avg_snr = sum(s["snr_vals"]) / len(s["snr_vals"]) if s["snr_vals"] else 0
        avg_rssi = sum(s["rssi_vals"]) / len(s["rssi_vals"]) if s["rssi_vals"] else 0
        avg_dist = sum(s["dist_vals"]) / len(s["dist_vals"]) if s["dist_vals"] else 0
        lines += [
            f"Нода: {name}",
            f"  Пакетов:       {s['packets']}",
            f"  Avg SNR:       {avg_snr:.2f} dB",
            f"  Min/Max SNR:   {min(s['snr_vals']):.1f} / {max(s['snr_vals']):.1f} dB",
            f"  Avg RSSI:      {avg_rssi:.1f} dBm",
            f"  Min/Max RSSI:  {min(s['rssi_vals'])} / {max(s['rssi_vals'])} dBm",
            f"  Avg дистанция: {avg_dist:.1f} м",
            f"  Airtime total: {s['airtime_total']} мс",
            "",
        ]

    # Общая статистика
    all_snr = [float(str(r[13]).replace(",", ".")) for r in rows if r[13]]
    all_rssi = [r[14] for r in rows if r[14]]
    all_dist = [r[6] for r in rows if r[6]]

    lines += [
        "ОБЩАЯ СТАТИСТИКА:",
        "-" * 40,
        f"SNR:   avg={sum(all_snr)/len(all_snr):.2f}, min={min(all_snr)}, max={max(all_snr)}",
        f"RSSI:  avg={sum(all_rssi)/len(all_rssi):.1f}, min={min(all_rssi)}, max={max(all_rssi)}",
        f"Dist:  avg={sum(all_dist)/len(all_dist):.1f}м, min={min(all_dist)}м, max={max(all_dist)}м",
        "",
        "ТЕКСТОВЫЕ СООБЩЕНИЯ:",
        "-" * 40,
    ]
    for msg in messages:
        lines.append(
            f"  {msg['time']} | {msg['from_name']:20s} | "
            f"snr={msg['snr']:6} | rssi={msg['rssi']:5} | {msg['text']}"
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[✓] Записан {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description="Генератор replay для Meshtasticator")
    parser.add_argument("--xlsx", default="output.xlsx", help="Путь к xlsx файлу")
    parser.add_argument("--out-dir", default="out", help="Папка для выходных файлов")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"Читаю {args.xlsx}...")
    rows = load_data(args.xlsx)
    print(f"  Загружено {len(rows)} строк")

    nodes = extract_nodes(rows)
    messages = extract_messages(rows)
    print(f"  Нод: {len(nodes)}, текстовых сообщений: {len(messages)}")

    write_node_config(nodes, args.out_dir)
    write_replay_script(nodes, messages, args.out_dir)
    write_stats(rows, nodes, messages, args.out_dir)

    print()
    print("=" * 60)
    print("ГОТОВО! Дальнейшие шаги:")
    print("=" * 60)
    print()
    print("1. Скопируй out/nodeConfig.yaml в папку Meshtasticator/out/")
    print()
    print("2. Открой interactiveSim.py и найди блок try:")
    print("   Замени его содержимое на код из out/replay_script.py")
    print()
    print("3. Запускай симуляцию:")
    print("   python3 interactiveSim.py --from-file -s -p ../firmware/.pio/build/native/program")
    print()
    print("4. После завершения введи 'plot' для графиков")
    print("   Сравни результаты с out/real_stats.txt")


if __name__ == "__main__":
    main()
