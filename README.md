# Meshtasticator — Интерактивный симулятор Meshtastic

Форк [meshtastic/Meshtasticator](https://github.com/meshtastic/Meshtasticator) с поддержкой
воспроизведения реальных замеров из xlsx и сборкой прошивки через PlatformIO на Linux.

---

## Структура репозитория

```
Meshtasticator/          ← корень репозитория
├── firmware/            ← субмодуль meshtastic/firmware
├── Meshtasticator/      ← симулятор
│   ├── lib/
│   ├── out/             ← генерируется автоматически
│   ├── interactiveSim.py
│   ├── requirements.txt
│   ├── generate_replay.py   ← скрипт генерации replay
│   └── output.xlsx          ← файл с реальными замерами
└── .gitignore
```

---

## Требования

- Ubuntu / Debian Linux
- Python 3.10+
- sudo доступ (для системных библиотек)

---

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/Mak3nt0sh1/Meshtasticator.git
cd Meshtasticator
git submodule update --init --recursive
```

> Субмодуль firmware качается долго (~80k объектов) — это нормально.

### 2. Системные зависимости

```bash
sudo apt update
sudo apt install -y \
  python3 python3-pip python3.12-venv \
  libgpiod-dev libyaml-cpp-dev libbluetooth-dev \
  libusb-1.0-0-dev libi2c-dev libuv1-dev \
  pkg-config xterm
```

### 3. Python виртуальное окружение

Создаём окружение в корне репозитория:

```bash
python3 -m venv venv
source venv/bin/activate
```

> Активируй окружение командой `source venv/bin/activate` каждый раз при открытии нового терминала.

### 4. Установка зависимостей

```bash
pip install platformio openpyxl pyyaml

# pandas (старая версия из requirements.txt несовместима с Python 3.12)
pip install "pandas>=2.0" --only-binary=:all:

# Остальные зависимости без pandas
grep -v "pandas" Meshtasticator/requirements.txt > /tmp/req_no_pandas.txt
pip install -r /tmp/req_no_pandas.txt
```

---

## Сборка прошивки

### 5. Сборка native бинарника через PlatformIO

```bash
cd firmware
pio run -e native
```

Сборка занимает 5–10 минут. После успешного завершения бинарник находится здесь:

```
firmware/.pio/build/native/meshtasticd
```

### 6. Создание симлинка

Симулятор ищет файл с именем `program` — создаём симлинк (выполнять из корня репозитория):

```bash
ln -sf "$(pwd)/firmware/.pio/build/native/meshtasticd" \
       "$(pwd)/firmware/.pio/build/native/program"
```

Проверка:
```bash
ls -la firmware/.pio/build/native/program
# → firmware/.pio/build/native/program -> .../meshtasticd
```

---

## Запуск симулятора

### Базовый запуск

```bash
cd Meshtasticator
python3 interactiveSim.py 3 -p ../firmware/.pio/build/native
```

Параметры:
- `3` — количество симулируемых нод (можно менять)
- `-p ../firmware/.pio/build/native` — путь к папке с бинарником

После запуска откроется GUI с картой нод и консоль для ввода команд.

### Команды симулятора

| Команда | Описание |
|---|---|
| `broadcast <fromNode> <text>` | Широковещательное сообщение от ноды |
| `DM <fromNode> <toNode> <text>` | Личное сообщение между нодами |
| `ping <fromNode> <toNode>` | Пинг между нодами |
| `traceroute <fromNode> <toNode>` | Трассировка маршрута |
| `nodes <id>` | Список нод как видит нода id |
| `plot` | Построить графики маршрутов и метрик |
| `exit` | Выйти без графиков |

### Повторный запуск с сохранёнными координатами

После расстановки нод вручную конфигурация сохраняется в `out/nodeConfig.yaml`.
Для повторного запуска с теми же координатами:

```bash
python3 interactiveSim.py --from-file -p ../firmware/.pio/build/native
```

---

## Replay реальных замеров

Если есть файл `output.xlsx` с реальными замерами из Meshtastic — можно воспроизвести
реальную сессию в симуляторе.

### Формат входного файла

Файл должен содержать колонки:
```
date, time, from, sender name, sender lat, sender long, distance,
hop limit, payload, airtime, rx pos lat, rx pos long, rx pos alt,
rx pos snr, rx pos rssi, ...
```

### Генерация конфигурации

```bash
cd Meshtasticator
python3 generate_replay.py --xlsx output.xlsx --out-dir out
```

Скрипт создаст в папке `out/`:

| Файл | Описание |
|---|---|
| `nodeConfig.yaml` | Координаты нод в метрах (конвертированы из GPS) |
| `replay_script.py` | Сообщения в реальном порядке с паузами |
| `real_stats.txt` | Статистика реальных замеров для сравнения |

### Исправление высоты нод

После генерации нужно выставить минимальную высоту антенны (иначе `log10(0)` вызовет ошибку):

```bash
sed -i 's/z: 0.0/z: 1.5/g' out/nodeConfig.yaml
```

### Вставка replay скрипта в симулятор

Открой `interactiveSim.py` и найди блок `try:` (строки ~25–65).
Замени его содержимое на код из `out/replay_script.py`.

Найти нужное место:
```bash
grep -n "try:\|except KeyboardInterrupt" interactiveSim.py
```

Пример блока после замены:
```python
try:
    import time

    print('Ожидание обмена NodeInfo между нодами...')
    time.sleep(15)

    print('Начинаем воспроизведение реальных сообщений...')

    sim.send_broadcast('Привет!', 1)
    time.sleep(30)
    sim.send_broadcast('Как слышно?', 2)

    print('Все сообщения отправлены!')
    time.sleep(10)
except KeyboardInterrupt:
    pass
```

### Запуск с реальными данными

```bash
python3 interactiveSim.py --from-file -p ../firmware/.pio/build/native
```

> Запускай **без флага `-s`** — тогда после выполнения скрипта симулятор
> остаётся в интерактивном режиме и можно ввести `plot` для графиков.

### Просмотр графиков

После отправки всех сообщений введи в консоли симулятора:
```
plot
```

Откроются окна:
- **Карта маршрутов** — стрелки между нодами показывают пути пакетов
- **Channel utilization** — загрузка канала по времени
- **Air utilization TX** — эфирное время передачи

Сравни результаты с файлом `out/real_stats.txt`.

---

## Возможные ошибки

### `uv.h: No such file or directory`
```bash
sudo apt install -y libuv1-dev
```

### `pandas` не устанавливается
```bash
pip install "pandas>=2.0" --only-binary=:all:
```

### `math domain error` в phy.py
```bash
sed -i 's/z: 0.0/z: 1.5/g' out/nodeConfig.yaml
```

### Симлинк `program` слетел
```bash
# Из корня репозитория:
ln -sf "$(pwd)/firmware/.pio/build/native/meshtasticd" \
       "$(pwd)/firmware/.pio/build/native/program"
```

### `KeyError: 0` при запуске с `--from-file`
Неправильный формат `nodeConfig.yaml`. Пересоздай через:
```bash
python3 generate_replay.py --xlsx output.xlsx --out-dir out
sed -i 's/z: 0.0/z: 1.5/g' out/nodeConfig.yaml
```

---

## Быстрый старт (шпаргалка)

```bash
# Клонировать и инициализировать
git clone https://github.com/Mak3nt0sh1/Meshtasticator.git
cd Meshtasticator
git submodule update --init --recursive

# Подготовить окружение
python3 -m venv venv && source venv/bin/activate
sudo apt install -y libgpiod-dev libyaml-cpp-dev libbluetooth-dev libusb-1.0-0-dev libi2c-dev libuv1-dev xterm
pip install platformio openpyxl pyyaml "pandas>=2.0" --only-binary=pandas
grep -v "pandas" Meshtasticator/requirements.txt | pip install -r /dev/stdin

# Собрать прошивку
cd firmware && pio run -e native && cd ..
ln -sf "$(pwd)/firmware/.pio/build/native/meshtasticd" \
       "$(pwd)/firmware/.pio/build/native/program"

# Запустить симулятор
cd Meshtasticator
python3 interactiveSim.py 3 -p ../firmware/.pio/build/native
# > broadcast 0 "hello"
# > plot
```
