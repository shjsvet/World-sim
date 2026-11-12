# WorldSim

**WorldSim** — приложение-симулятор эволюции мира: процедурная генерация карты,
геополитика фракций, летопись событий и «машина времени», позволяющая
возвращаться к прошлым годам и создавать альтернативные ветки истории.

> **Статус:** 🟡 ранний каркас. Запускается веб-приложение с пустой стартовой
> страницей; генерация мира и карта появятся в задачах T12–T15. План работ и статусы — в [backlog.md](backlog.md),
> промпты задач — в [docs/PROMPTS.md](docs/PROMPTS.md), требования — в
> [docs/TASK.md](docs/TASK.md).

## Запуск приложения

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e .

worldsim
```

Приложение открывается в браузере на <http://localhost:8501>.
Эквивалентный запуск без консольной команды — `python -m worldsim`.

Аргументы передаются Streamlit напрямую:

```bash
worldsim --server.port 8600 --server.headless true
```

## Режим разработки

```bash
pip install -e ".[dev]"
streamlit run src/worldsim/ui/app.py   # отладочный запуск без entry point
```

## Проверка качества

```bash
pytest                                           # тесты
pytest --cov=worldsim --cov-report=term-missing  # покрытие
mypy src                                         # статическая типизация (strict)
ruff check .                                     # линтер
ruff format --check .                            # форматирование
```

## ИИ-модуль (этап 3)

```bash
pip install -e ".[ai]"
```

Скопируйте `.env.example` в `.env` и заполните ключи провайдера. Файл `.env`
в репозиторий не попадает — он закрыт `.gitignore`.

## Структура проекта

```text
src/worldsim/
├── __main__.py # python -m worldsim
├── launcher.py # точка входа worldsim
├── core/       # доменные модели: деревья, карта, события, снимок мира, летопись
├── generator/  # процедурная генерация стартового мира и фракций
├── engine/     # правила симуляции и шаг времени
├── vcs/        # коммиты, ветвление, diff снимков мира
├── ai/         # ИИ-хроника и генерация конфигураций мира
└── ui/         # Streamlit-интерфейс приложения
tests/          # модульные и интеграционные тесты
docs/           # ТЗ, реестр промптов, архитектурные решения
```

## Документация

- [docs/TASK.md](docs/TASK.md) — техническое задание.
- [backlog.md](backlog.md) — todo-лист и статусы задач.
- [docs/PROMPTS.md](docs/PROMPTS.md) — промпты атомарных задач и журнал их изменений.
