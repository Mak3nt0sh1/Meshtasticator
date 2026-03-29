#!/usr/bin/env python3
""" Simulator for letting multiple instances of native programs communicate via TCP as if they did via their LoRa chip.
    Usage: python3 interactiveSim.py [nrNodes] [-p <full-path-to-program>] [-d] [-s]
    Use '-d' for Docker.
    Use '-s' to specify what should be sent using this script.
"""
import os
import time
import argparse
from lib.interactive import InteractiveSim, CommandProcessor

parser = argparse.ArgumentParser(prog='interactiveSim')
parser.add_argument('-s', '--script', action='store_true')
parser.add_argument('-d', '--docker', action='store_true')
parser.add_argument('--from-file', action='store_true')
parser.add_argument('-f', '--forward', action='store_true')
parser.add_argument('-p', '--program', type=str, default=os.getcwd())
parser.add_argument('-c', '--collisions', action='store_true')
parser.add_argument('nrNodes', type=int, nargs='?', choices=range(0, 11), default=0)

sim = InteractiveSim(parser.parse_args())  # Start the simulator

if sim.script:  # Use '-s' as argument if you want to specify what you want to send here
    try:
        # Ждём пока ноды обменяются NodeInfo
        print('Ожидание обмена NodeInfo между нодами...')
        time.sleep(15)

        print('Начинаем воспроизведение реальных сообщений...')

        # 11:07:16 | Meshtastic 2774 | dist=53m | snr=8.5 rssi=-89
        sim.send_broadcast('Я редко когда думаю, а ещё реже думаю', 1)

        time.sleep(42)  # пауза 42с
        # 11:07:58 | Meshtastic 2774 | dist=70m | snr=9.0 rssi=-92
        sim.send_broadcast('Чё там когда всё то? Мб в 11 10 закончить?', 1)

        time.sleep(20)  # пауза 20с
        # 11:08:18 | Meshtastic 2774 | dist=68m | snr=9.25 rssi=-93
        sim.send_broadcast('У меня в первые две минуты уже 25 пакетов капнуло', 1)

        time.sleep(5)  # пауза сокращена с 228с до 5с
        # 11:12:06 | Meshtastic 2774 | dist=54m | snr=9.0 rssi=-93
        sim.send_broadcast('Точно надо до 30 стоять? У меня в первые две минуты 25 пакетов капнуло.', 1)

        time.sleep(49)  # пауза 49с
        # 11:12:55 | Meshtastic 2774 | dist=62m | snr=8.75 rssi=-95
        sim.send_broadcast('Сейчас 200+', 1)

        time.sleep(5)  # пауза сокращена с 484с до 5с
        # 11:20:59 | Meshtastic 2778 | dist=43m | snr=6.5 rssi=-88
        sim.send_broadcast('обязательно до 30 стоять?', 2)

        time.sleep(30)  # пауза 30с
        # 11:21:29 | Meshtastic 282c | dist=48m | snr=10.5 rssi=-79
        sim.send_broadcast('Ну 9 минут осталось, в что?', 0)

        print('Все сообщения отправлены!')
        time.sleep(10)  # ждём доставки последних пакетов
        

        print('Строим графики...')
        sim.graph.init_routes(sim)
        sim.graph.plot_route(0)
        sim.graph.plot_route(1)
        sim.graph.plot_route(2)
        sim.graph.plot_route(3)
        sim.graph.plot_route(4)
        sim.graph.plot_metrics(sim.nodes)
        import matplotlib.pyplot as plt
        plt.show(block=True)
    except KeyboardInterrupt:
        sim.graph.plot_metrics(sim.nodes)
        sim.graph.init_routes(sim)
else:  # Normal usage with commands
    CommandProcessor().cmdloop(sim)
