# WorldSim

**WorldSim** — приложение-симулятор эволюции мира: процедурная генерация
карты, геополитика фракций, экономика, войны, культура и религия, летопись
событий и «машина времени» на git-подобном репозитории версий.

> **Статус:** этапы 0–4 закрыты: домен, генерация, движок правил, VCS,
> ИИ-помощник, культура, ресурсы и торговля. Остались производительность
> (T38) и магия (T44–T45). План и статусы — в [backlog.md](backlog.md).

## Возможности

- Процедурная карта с биомами, реками, ресурсами, маной и лей-линиями.
- Фракции с идеологиями, культурой, экономикой, армией и дипломатией.
- Правила симуляции: рост населения, голод, эпидемии, экспансия, войны,
  оккупация, мирные договоры, социальная динамика, культура и торговля.
- Летопись событий с фильтрами и markdown-выгрузкой.
- Версии мира: коммиты, ветки, теги, diff и альтернативные реальности в
  каталоге `.worldsim/`.
- ИИ-функции (опционально): генерация мира по описанию и главы летописи;
  без ключей приложение работает в ручном режиме.

## Быстрый старт

Требуется Python 3.11 или 3.12.

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
worldsim
```

Приложение открывается на <http://localhost:8501>. Эквивалентный запуск —
`python -m worldsim`; аргументы Streamlit передаются напрямую:

```bash
worldsim --server.port 8600 --server.headless true
```

В интерфейсе три вкладки: **Мир** (карта, фракции, тайл, летопись),
**История** (таймлайн, checkout, ветки, diff) и **ИИ** (мир по описанию,
глава летописи). Мир генерируется кнопкой в сайдбаре.

## Команды

| Команда | Назначение |
| --- | --- |
| `worldsim` / `python -m worldsim` | запуск веб-приложения |
| `python scripts/run_sim.py --years 10` | симуляция без интерфейса |
| `python scripts/run_sim.py --plugin plugins/mana_rule.py` | запуск с плагином |
| `pytest` | все тесты |
| `pytest --cov=worldsim --cov-report=term-missing` | тесты с покрытием |
| `mypy src` | строгая проверка типов |
| `ruff check .` / `ruff format --check .` | линтер и формат |
| `python scripts/check_docs.py` | ссылки, якоря и docstring'и |

Симуляция из CLI:

```bash
python scripts/run_sim.py --seed 42 --size 64 --years 20
python scripts/run_sim.py --plugin plugins/mana_rule.py --years 20
```

## ИИ-провайдеры

Скопируйте [.env.example](.env.example) в `.env` и заполните ключи. Файл
`.env` закрыт `.gitignore` и не попадает в репозиторий.

```bash
WORLDSIM_AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
```

Поддерживаются OpenAI, Groq и локальный Ollama. Без ключей вкладка «ИИ»
показывает предупреждение и предлагает ручную конфигурацию/fallback-главу.

## Версии и альтернативные реальности

История мира хранится в `.worldsim/` в корне проекта (путь можно изменить
в сайдбаре). Коммит сохраняет снимок и летопись; checkout возвращает
прошлый год, новая ветка запускает независимую реальность, diff показывает
изменения к родителю. Слияние веток не поддерживается — это осознанное
решение, см. [ADR 0004](docs/adr/0004-json-vcs.md).

## Плагины

Правило — это класс с `name`, `priority` и `apply(state, ctx)`. Положите
файл `*_rule.py` в `plugins/` и экспортируйте `RULES`, `RULE` или сам класс;
`load_rules` проверит протокол, конфликты имён и изолирует падения.
Пример — [plugins/mana_rule.py](plugins/mana_rule.py).

## Разработка

```bash
pip install -e ".[dev]"
pytest
mypy src
ruff check .
ruff format --check .
python scripts/check_docs.py
```

Отладочный запуск без entry point:

```bash
streamlit run src/worldsim/ui/app.py
```

## Структура проекта

```text
src/worldsim/
├── __main__.py     # python -m worldsim
├── launcher.py     # команда worldsim
├── core/           # модели: карта, фракции, события, летопись, культуры, ресурсы, снимок
├── generator/      # генерация мира, фракций и территорий
├── engine/         # движок, правила, метрики, плагины
├── vcs/            # коммиты, ветки, теги, diff, файловый репозиторий
├── ai/             # клиент LLM, хронист, генератор конфигурации
└── ui/             # Streamlit, фигуры Plotly, обёртки истории и ИИ
tests/              # модульные, интеграционные и UI-тесты
docs/               # ТЗ, промпты, архитектура, ADR
plugins/            # примеры правил-плагинов
scripts/            # CLI симуляции и проверка документации
```

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — слои, поток данных,
  инварианты, формат `.worldsim/` и таблица правил.
- [docs/adr/](docs/adr/) — архитектурные решения:
  [0001-src-layout](docs/adr/0001-src-layout.md),
  [0002-frozen-pydantic](docs/adr/0002-frozen-pydantic.md),
  [0003-bst-chronicle](docs/adr/0003-bst-chronicle.md),
  [0004-json-vcs](docs/adr/0004-json-vcs.md),
  [0005-rules-protocol](docs/adr/0005-rules-protocol.md),
  [0006-seeded-rng](docs/adr/0006-seeded-rng.md).
- [docs/OBSIDIAN.md](docs/OBSIDIAN.md) — импорт ADR в Obsidian.
- [docs/TASK.md](docs/TASK.md) — техническое задание.
- [docs/PROMPTS.md](docs/PROMPTS.md) — промпты задач и журнал изменений.
- [backlog.md](backlog.md) — todo-лист и статусы задач.
