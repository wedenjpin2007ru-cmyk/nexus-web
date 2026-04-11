# NEXUS Unified Client

Единое приложение для всех функций NEXUS в современном интерфейсе 2099.

## Возможности

- ⚡ Управление подпиской
- 🚀 Автоматизация Cursor
- 🎨 Современный киберпанк UI
- 💻 Нативное окно или браузер
- 🔄 Автообновление статуса

## Быстрый старт

### Windows

```cmd
start_unified.cmd
```

### Ручной запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск
python nexus_unified.py
```

## Требования

- Python 3.10+
- Windows 10/11
- Интернет соединение

## Структура

- `nexus_unified.py` - Главное приложение
- `nexus_client.py` - Модуль работы с подпиской
- `launcher.py` - Модуль автоматизации
- `start_unified.cmd` - Быстрый запуск

## Особенности

### Нативное окно

Если установлен `pywebview`, приложение откроется в нативном окне без браузера.

### Браузерный режим

Если `pywebview` недоступен, откроется в браузере по умолчанию.

### Порт

По умолчанию: `7777`

Изменить: `set NEXUS_PORT=8888`

## Интерфейс

- **Подписка** - статус, email, срок действия
- **Автоматизация** - запуск сценариев
- **Быстрые действия** - логи, документация, выход

## Troubleshooting

### Порт занят

```cmd
set NEXUS_PORT=8888
python nexus_unified.py
```

### Python не найден

Установи Python с [python.org](https://python.org) и добавь в PATH.

### Ошибка импорта

```cmd
pip install --upgrade -r requirements.txt
```

## Логи

Логи сохраняются в:
```
%APPDATA%\Nexus\nexus_client.log
```

## Поддержка

- GitHub: [nexus-web](https://github.com/wedenjpin2007ru-cmyk/nexus-web)
- Кабинет: Railway deployment
