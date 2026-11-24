# WorldSim

**WorldSim** — приложение-симулятор эволюции мира: процедурная карта,
фракции, экономика, войны, культура, магия, летопись событий и «машина
времени» на git-подобном репозитории версий.

> **Статус:** все задачи T00–T59 закрыты, CI на GitHub Actions зелёный.
> План и журнал — в [backlog.md](backlog.md).

## Запуск за три шага (Windows)

Понадобится Python 3.11 или 3.12 (проверить: `python --version`).

### Шаг 1. Откройте PowerShell в папке проекта

Это папка, где лежат `pyproject.toml` и каталог `src`. Например:

```powershell
cd C:\_Bubu\my_py\world-sim_2.0
```

### Шаг 2. Создайте и активируйте окружение проекта

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

В приглашении PowerShell появится `(.venv)`. Важно: это должно быть
окружение **внутри папки проекта**, а не соседнее `C:\_Bubu\my_py\.venv`.

Если PowerShell запрещает запуск скрипта активации:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Шаг 3. Установите приложение и запустите

```powershell
pip install -e ".[dev]"
worldsim --server.port 8600
```

Откройте в браузере <http://localhost:8600>. Остановить приложение —
`Ctrl+C` в PowerShell.

Если `worldsim` уже установлен, при следующих запусках достаточно:

```powershell
cd C:\_Bubu\my_py\world-sim_2.0
.\.venv\Scripts\Activate.ps1
worldsim --server.port 8600
```

### Linux / macOS

```bash
cd world-sim_2.0
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
worldsim --server.port 8600
```

## Если `worldsim` не распознаётся

Это значит, что команда запущена не из того окружения или пакет не
установлен. Проверьте по порядку:

1. **Вы в папке проекта?** В приглашении должно быть
   `...\world-sim_2.0>`, а не `...\my_py>`. Перейдите:
   ```powershell
   cd C:\_Bubu\my_py\world-sim_2.0
   ```
2. **Активно проектное окружение?** В приглашении — `(.venv)`, и файл
   `.\.venv\Scripts\worldsim.exe` существует:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   Test-Path .\.venv\Scripts\worldsim.exe
   ```
3. **Пакет установлен?** Если `Test-Path` вернул `False`:
   ```powershell
   pip install -e ".[dev]"
   ```
4. **Запустите без команды `worldsim`** — так видно точную ошибку:
   ```powershell
   .\.venv\Scripts\worldsim.exe --server.port 8600
   # или
   .\.venv\Scripts\python.exe -m worldsim --server.port 8600
   ```

Другие частые случаи:

| Симптом | Что сделать |
| --- | --- |
| `No module named streamlit` | `pip install -e ".[dev]"` в активном проектном venv |
| Порт 8600 занят | `worldsim --server.port 8601` и открыть новый адрес |
| Браузер не открылся сам | открыть <http://localhost:8600> вручную |
| `Activate.ps1` заблокирован | команда `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` из шага 2 |
| Запущено из родительского `.venv` | закрыть терминал, открыть новый и повторить шаги 1–2 |

## Первый запуск в интерфейсе

1. В сайдбаре слева нажмите **«Сгенерировать мир»**.
2. Вкладка **«Мир»** — карта, фракции, параметры тайла (по ID или по
   координатам X/Y) и летопись.
3. Вкладка **«История»** — коммиты, ветки, diff и альтернативные реальности.
4. Вкладка **«ИИ»** — мир по описанию и глава летописи; ключи не обязательны.
5. Вкладка **«🧠 Мысли»** — дневники правителей с фильтром по фракции.
6. Вкладка **«💬 Переписка»** — сообщения между правителями и их фильтры.

На вкладке **«Мир»** кнопка **«🧠 ИИ-год»** запускает ход ИИ-правителей:
фракции принимают решения, а на вкладке «Мысли» появляются записи. В
«Переписке» откройте канал, выберите отправителя, получателя и тему. По
умолчанию работает fallback без ключей; LLM включается в сайдбаре.

## Возможности

- Процедурная карта с биомами, реками, ресурсами, маной и лей-линиями.
- Фракции с идеологиями, культурой, экономикой, армией и дипломатией.
- Правила: рост населения, голод, эпидемии, экспансия, войны, оккупация,
  мирные договоры, социальная динамика, культура, торговля и магия.
- Летопись событий с фильтрами и markdown-выгрузкой.
- Версии мира: коммиты, ветки, теги, diff и альтернативные реальности в
  `.worldsim/`.
- ИИ-функции (опционально): генерация мира по описанию и главы летописи.
- ИИ-правители: автономные решения фракций, дневники мыслей, автопереписка,
  объявление войн, долгосрочные приказы, религии, торговля и марши армий.
  Без ключей работает детерминированный fallback; кнопка «🧠 ИИ-год» и канал
  переписки доступны прямо в интерфейсе.
- Мир по описанию: с LLM культуры задаются моделью, без ключей — локальным
  разбором текста (например, «северные люди и южные эльфы»).

## Команды

| Команда | Назначение |
| --- | --- |
| `worldsim` | запуск веб-приложения (порт 8501 по умолчанию) |
| `worldsim --server.port 8600` | запуск на другом порту |
| `python -m worldsim` | то же без консольной команды |
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

## ИИ-провайдеры (необязательно)

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
- [docs/WORLD_PARAMETERS.md](docs/WORLD_PARAMETERS.md) — все параметры мира,
  их влияние и вклад в баланс сил.
- [docs/PERFORMANCE.md](docs/PERFORMANCE.md) — замеры шага 256×256,
  оптимизации и причины недостижения цели 50 мс.
- [docs/adr/](docs/adr/) — архитектурные решения:
  [0001-src-layout](docs/adr/0001-src-layout.md),
  [0002-frozen-pydantic](docs/adr/0002-frozen-pydantic.md),
  [0003-bst-chronicle](docs/adr/0003-bst-chronicle.md),
  [0004-json-vcs](docs/adr/0004-json-vcs.md),
  [0005-rules-protocol](docs/adr/0005-rules-protocol.md),
  [0006-seeded-rng](docs/adr/0006-seeded-rng.md),
  [0007-ai-rulers](docs/adr/0007-ai-rulers.md).
- [docs/OBSIDIAN.md](docs/OBSIDIAN.md) — импорт ADR в Obsidian.
- [docs/TASK.md](docs/TASK.md) — техническое задание.
- [docs/PROMPTS.md](docs/PROMPTS.md) — промпты задач и журнал изменений.
- [backlog.md](backlog.md) — todo-лист и статусы задач.
