# PROMPTS — реестр атомарных задач WorldSim

**Проект:** WorldSim — симулятор эволюции мира с геополитикой и контролем версий.
**Источник требований:** [TASK.md](./TASK.md) · **Todo-лист и статусы:** [../backlog.md](../backlog.md).
**Назначение файла:** промпты атомарных задач и журнал их изменений. Статусы задач здесь не ведутся.

## Содержание

- [Как пользоваться этим файлом](#как-пользоваться-этим-файлом)
- [Общий Definition of Done](#общий-definition-of-done)
- [Исходные промпты](#исходные-промпты)
- [Промпты задач](#промпты-задач)
- [Журнал изменений промптов](#журнал-изменений-промптов)
- [Новые задачи, добавленные при декомпозиции](#новые-задачи-добавленные-при-декомпозиции)

## Как пользоваться этим файлом

1. Статусы задач ведутся в [../backlog.md](../backlog.md) — это единственное место, где они меняются. Здесь хранятся только формулировки промптов.
2. Задача берётся в работу, когда все её зависимости имеют статус ✅ в `backlog.md`.
3. **После каждой атомарной задачи делается коммит** в формате `task(T05): <что сделано>`, строка добавляется в журнал выполнения `backlog.md`, а изменение промпта (если оно было) — в [журнал изменений промптов](#журнал-изменений-промптов).
4. После коммита работа останавливается и запрашивается подтверждение на переход к следующей задаче.
5. Промпт задачи копируется в чат/агенту целиком: он самодостаточен и не требует чтения остального файла.
6. Возникшая по ходу дела новая задача получает следующий свободный номер, строку в `backlog.md` и свой промпт здесь; номера существующих задач не переиспользуются.
7. Секреты (ключи API, токены, пароли) хранятся только в локальном `.env` и никогда не попадают в репозиторий, тесты и летопись.

## Общий Definition of Done

Задача считается выполненной, только если одновременно выполнено всё перечисленное:

- [ ] код лежит в `src/worldsim/<модуль>/` по src-layout, публичные сущности имеют docstrings;
- [ ] добавлены тесты в `tests/<модуль>/`, `pytest` проходит полностью;
- [ ] `mypy src` проходит в strict-режиме без новых ошибок;
- [ ] `ruff check .` и `ruff format --check .` проходят;
- [ ] нет обращений к глобальному `random`, `datetime.now()` и времени внутри моделей — детерминизм сохранён;
- [ ] новые зависимости внесены в `pyproject.toml`, секретов в коде нет;
- [ ] приложение запускается командой `worldsim` (`python -m worldsim`) и открывает интерфейс;
- [ ] статус обновлён в `backlog.md`, запись добавлена в журнал выполнения, создан коммит.

## Исходные промпты

### Первичный промпт (дословно)

```text
Изучи задачу. Декомпазируй задачу на атомарные составляющие. Для каждой атомарной задачи напиши промпт. Для возникающих новых задач добавляй промпт и включай в список задач. После каждой атомарной задачи делай commit и спрашивай подтверждение для перехода к следующей. Файлы с конфиденциальной информацией, ключами, паролями должны быть добавлены в gitignore.
```

### Задача 01 (дословно)

```text
Поправь разметку всех файлов проекта
```

## Промпты задач

Формат задачи: заголовок → строка метаданных → промпт для агента (блок цитаты) → критерии готовности.

### T00 — Декомпозиция ТЗ и промпты (первичный промпт)

*Этап 0.1 · P0 · зависит: —*

**Промпт:** выполнен — прочитать `docs/TASK.md`, разбить работу на атомарные задачи, написать для каждой самодостаточный промпт, завести `.gitignore` для секретов, сделать коммит.

**Готово, когда:** реестр задач с промптами существует, `.gitignore` закрывает `.env` и ключи, создан первый коммит.

---

### T01 — Поправить разметку всех файлов проекта

*Этап 0.1 · P0 · зависит: T00*

**Промпт:**

> Приведи разметку всех файлов проекта к единому аккуратному виду, не меняя смысл текста.
> - Проверь каждый Markdown-файл: заголовки идут по уровням без пропусков, между блоками есть пустые строки, код-блоки имеют язык и закрыты, списки используют единый маркер, таблицы выровнены, нет хвостовых пробелов и лишних пустых строк, файл заканчивается одним переводом строки.
> - В `docs/TASK.md` восстанови разорванную структуру: `4.`, `5.`, `6.` должны стать заголовками второго уровня, `Этап 1–4` — третьего, пункты `1.1–4.3` — вложенными списками с идентификатором задачи из `docs/PROMPTS.md`.
> - Добавь в `docs/TASK.md` оглавление и честную пометку о текущем состоянии репозитория (код ещё не реализован), чтобы разделы «Готово» не вводили в заблуждение.
> - В `docs/PROMPTS.md` проверь единообразие: одинаковые символы статусов, одинаковый формат метаданных задач, рабочие относительные ссылки.
> - Нормализуй переводы строк (LF в репозитории) и кодировку UTF-8 без BOM.
> **Готово, когда:** все файлы рендерятся без битых заголовков и блоков, оглавление ссылается на существующие разделы, `git diff` содержит только правки разметки и согласованные с ними уточнения.

---

### T02 — Каркас Python-проекта

*Этап 0.1 · P0 · зависит: T01*

**Промпт:**

> Создай устанавливаемый каркас Python-пакета по src-layout, чтобы проект можно было импортировать и тестировать.
> - `pyproject.toml`: build-backend `setuptools.build_meta`, `project.name = "worldsim"`, `version = "0.1.0"`, `requires-python = ">=3.11"`, зависимости `pydantic>=2.7`, `streamlit>=1.35`, `plotly>=5.22`; extras `dev = [pytest, pytest-cov, mypy, ruff]`, `ai = [openai, httpx, python-dotenv]`; `[tool.setuptools.packages.find] where = ["src"]`.
> - `src/worldsim/__init__.py` с `__version__` и docstring; пустой `src/worldsim/py.typed`; подпакеты `core/`, `generator/`, `engine/`, `vcs/`, `ai/`, `ui/` с `__init__.py` и docstring-описанием назначения.
> - `README.md`: назначение проекта, быстрый старт (`python -m venv .venv`, `pip install -e ".[dev]"`, `pytest`, запуск Streamlit), структура каталогов, ссылки на `docs/TASK.md` и `docs/PROMPTS.md`.
> - `.env.example` со всеми переменными ИИ (`WORLDSIM_AI_PROVIDER=`, `OPENAI_API_KEY=`, `GROQ_API_KEY=`, `OLLAMA_HOST=`) и пустыми значениями; убедись, что `.env` и ключи закрыты `.gitignore`.
> **Готово, когда:** `pip install -e ".[dev]"` проходит в чистом venv, `python -c "import worldsim; print(worldsim.__version__)"` печатает `0.1.0`, команды в README рабочие.

> **Примечание (T39):** пункт про `py.typed` и библиотечные формулировки отменён — проект переведён в приложение, см. задачу T39.

---

### T03 — Тесты и качество кода

*Этап 0.1 · P0 · зависит: T02*

**Промпт:**

> Настрой инструменты качества и каркас тестов.
> - В `pyproject.toml` добавь `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `addopts = "-q --strict-markers"`, маркеры `slow`, `integration`, `ai`), `[tool.mypy]` (`strict = true`, `python_version = "3.11"`, `files = ["src"]`, `warn_unreachable = true`), `[tool.ruff]` (`line-length = 100`, `target-version = "py311"`, `select = ["E", "F", "I", "B", "UP", "SIM", "RUF"]`), исключения для тестов, `[tool.coverage.run]` (`source = ["worldsim"]`, `branch = true`). Для пакетов без типов (`streamlit`, `plotly`) добавь `[[tool.mypy.overrides]]` с `ignore_missing_imports = true`.
> - Создай `tests/` с `conftest.py`: фикстура `seed -> 42` и хелпер `deterministic_rng`.
> - `tests/test_package.py`: проверка версии и импорта всех подпакетов.
> - Зафиксируй команды проверки в `README.md` (раздел «Проверка качества»).
> **Готово, когда:** `pytest`, `mypy src`, `ruff check .`, `ruff format --check .` проходят на пустом каркасе, coverage-отчёт формируется.

---

### T04 — CI на GitHub Actions

*Этап 0.1 · P2 · зависит: T03*

**Промпт:**

> Добавь `.github/workflows/ci.yml`: триггеры `push` и `pull_request` в `master`; матрица Python 3.11 и 3.12; шаги: checkout, `setup-python` с кешем pip, `pip install -e ".[dev]"`, `ruff check .`, `ruff format --check .`, `mypy src`, `pytest --cov --cov-report=xml`; загрузка coverage-артефакта. Добавь бейдж CI в `README.md`.
> **Готово, когда:** YAML валиден, шаги повторяют локальный чек-лист, бейдж добавлен; отметить в журнале, что удалённый репозиторий пока не подключён.

---

### T05 — BST-дерево (`core/tree.py`)

*Этап 0.2 Домен · P0 · зависит: T03*

**Промпт:**

> Реализуй `src/worldsim/core/tree.py` — бинарное дерево поиска, основу летописи.
> - Дженерик-класс `BinarySearchTree[K, V]` без глобального состояния.
> - Методы: `insert(key, value)` — при равном ключе значение добавляется в список (мультимножество: в одном году бывает несколько событий); `get(key) -> V | None`, `get_all(key) -> list[V]`, `contains(key)`, `min_key()`, `max_key()`, `__len__`, `__iter__` (in-order по возрастанию ключа), `items() -> Iterator[tuple[K, V]]`, `range_query(lo, hi, inclusive=True) -> Iterator[tuple[K, V]]`, `height()`, `clear()`, `to_dict()` / `from_dict()` в JSON-совместимом виде, `remove(key)`.
> - Обход и вставку сделай итеративными или с защитой от `RecursionError`; docstrings и полная типизация под mypy strict.
> - Тесты `tests/core/test_tree.py`: порядок in-order, дубликаты ключей, границы `range_query` (включительно и исключительно), пустое дерево, 10 000 вставок без `RecursionError`, round-trip `to_dict` / `from_dict`.
> **Готово, когда:** тесты зелёные, mypy strict без `Any`-дыр, модуль не использует `random`.

---

### T06 — N-арное дерево (`core/ntree.py`)

*Этап 0.2 Домен · P0 · зависит: T05*

**Промпт:**

> Реализуй `src/worldsim/core/ntree.py` — N-арное дерево (Composite) для иерархий: континент → регион → тайл, фракция → вассалы.
> - `Node[T]`: `id: int`, `name: str`, `value: T | None`, `parent: Node[T] | None`, `children: list[Node[T]]`.
> - Методы: `add_child(node)` (запрет самоприсоединения, повторного родителя и создания цикла через `is_ancestor`), `remove_child(node)`, `find(node_id)` (поиск по всему дереву), `path_to_root()`, `depth()`, `is_ancestor(other)`, `walk()` (pre-order генератор), `walk_postorder()`, `leaves()`, `move_to(new_parent)` с повторной проверкой циклов.
> - `to_dict()` / `from_dict()` с восстановлением ссылок `parent`, JSON-сериализуемо; `__repr__` не должен рекурсивно печатать детей.
> - Тесты `tests/core/test_ntree.py`: запрет цикла через `add_child` и через `move_to`, перенос узла, сериализация, глубокое дерево (10 000 узлов) без падения.
> **Готово, когда:** тесты зелёные, цикл невозможно создать ни одним путём, mypy strict.

---

### T07 — Детерминированный RNG (`core/rng.py`)

*Этап 0.2 Домен · P0 · зависит: T03*

**Промпт:**

> Реализуй `src/worldsim/core/rng.py` — единственный источник случайности в симуляции.
> - Глобальный `random` запрещён: весь код получает случайность через экземпляр `Rng`, обёртки над `random.Random`.
> - `Rng(seed: int)`: `int(a, b)`, `uniform(a, b)`, `choice(seq)`, `weighted_choice(items: Mapping[T, float])`, `shuffle(seq)`, `chance(probability)`, `fork(label: str) -> Rng` (подпоток с сидом `sha256(f"{seed}:{label}")` — стабилен между запусками и ОС, не зависит от порядка вызовов), `getstate()` / `setstate()` для сериализации в снимок.
> - Тесты `tests/core/test_rng.py`: одинаковый seed → одинаковая последовательность; разные seed → разные; `fork("a")` повторяем; `weighted_choice` с нулевыми весами; восстановление через `getstate` / `setstate`; `chance(0)` и `chance(1)` — границы.
> **Готово, когда:** тесты зелёные, детерминизм подтверждён между процессами, grep не находит `import random` вне `rng.py`.

---

### T08 — Модели карты (`core/geography.py`)

*Этап 0.2 Домен · P0 · зависит: T07*

**Промпт:**

> Реализуй `src/worldsim/core/geography.py` — модели тайлов и карты. Полный список полей и их влияния — `docs/TASK.md`, раздел 7.
> - `Biome(StrEnum)`: `OCEAN, COAST, PLAINS, FOREST, HILLS, MOUNTAINS, DESERT, TUNDRA, SWAMP`; свойства `is_water`, `emoji`, `color` (hex для Plotly), `base_fertility` (пустыня 10, равнины 80), `base_elevation`, `movement_cost`, `defense_bonus`.
> - `ResourceType(StrEnum)`: `NONE, FOOD, WOOD, IRON, GOLD, MANA` — главный ресурс тайла (один на тайл); `ClimateZone(StrEnum)`: `TROPICAL, TEMPERATE, ARCTIC` — задел на будущее (глобальное похолодание), по умолчанию `TEMPERATE`.
> - `RegionData(BaseModel, frozen=True)`: `id: int >= 0`; `x: int >= 0`; `y: int >= 0`; `biome: Biome`; `fertility: float` в `[0, 100]`; `elevation: float` в `[0, 9000]`; `has_river: bool = False`; `climate_zone: ClimateZone = TEMPERATE`; `resource_type: ResourceType = NONE`; `resource_amount: float >= 0 = 0`; `resource_depletion: float >= 0 = 0`; `infrastructure: float` в `[0, 100] = 0`; `population: int >= 0`; `population_capacity: int >= 0`; `culture: str | None` (1..64 или `None`); `happiness: float` в `[0, 100] = 50`; `urbanization: float` в `[0, 100] = 0`; `owner_id: int | None = None`; `army_presence: int >= 0 = 0`; `fortification: float` в `[0, 100] = 0`; `unrest: float` в `[0, 100] = 0`; `assimilation: float` в `[0, 1] = 0`; `mana_density: int` в `[0, 100] = 0`; `mana_regeneration: int >= 0 = 0`; `ley_line: bool = False`.
> - Вычисляемые свойства: `is_land`, `is_city` (`population > CITY_POPULATION_THRESHOLD` (`1000`) и `urbanization >= 50`), `defense_multiplier()` (`1 + fortification / 200 + biome.defense_bonus`), `food_output()` (`population * fertility / 100 * biome.food_modifier * (1 + 0.1 * has_river + infrastructure / 200)`) — формулу использует T19.
> - `WorldMap(BaseModel, frozen)`: `size: int` (1..1024), `tiles: tuple[RegionData, ...]`; валидатор: `len(tiles) == size * size` и координаты тайла совпадают с индексом `y * size + x`; методы `at(x, y)`, `by_id(tile_id)`, `neighbors(x, y, diagonal=False)`, `land_tiles()`, `cities()`, `tiles_with(owner_id)`, `center()`.
> - Тесты `tests/core/test_geography.py`: границы диапазонов (`fertility = 101`, `happiness = -1`, `elevation = 9001`, `assimilation = 1.1`), `is_city` на порогах 1000 и 50, `defense_multiplier` растёт с фортификацией, `food_output` учитывает реку и инфраструктуру, `mana_density` и `mana_regeneration` в диапазонах, соседи в углу, на краю и в центре, диагонали, JSON round-trip, `is_water` для каждого биома.
> **Готово, когда:** тесты зелёные, mypy strict, в моделях нет логики симуляции.

---

### T09 — Модель события (`core/events.py`)

*Этап 0.2 Домен · P0 · зависит: T03*

**Промпт:**

> Реализуй `src/worldsim/core/events.py` — модель сухого события: ИИ позже пишет по ним литературу, поэтому сами события должны быть строгими данными.
> - `EventType(StrEnum)`: `PLAGUE, FAMINE, STARVATION, EXPANSION, WAR, BATTLE_WON, BATTLE_LOST, CAPITAL_FALL, MIGRATION, CULTURE_CLASH, TRADE, RECRUITMENT, DESERTION, TECH_ADVANCE, PEACE_OFFER, PEACE_TREATY, RIOT, SECESSION, DEFECTION, CITY_RISE, RESOURCE_DEPLETED, OCCUPATION, ACADEMY_FOUNDED, MAGIC_BREAKTHROUGH, LEY_LINE_CLAIMED, CUSTOM`.
> - `Event(BaseModel, frozen=True)`: `id: int >= 0`, `year: int >= 0`, `type: EventType`, `summary: str` (одна сухая строка ≤ 300 символов), `tile_ids: tuple[int, ...] = ()`, `faction_ids: tuple[int, ...] = ()`, `severity: float` в `[0, 1]`, `payload: dict[str, int | float | str | bool | None] = {}`.
> - Фабрики `Event.plague(...)`, `Event.expansion(...)`, `Event.war(...)`, `Event.starvation(...)`, `Event.peace(...)`, чтобы правила не собирали словари руками; `as_dict()`.
> - Тесты: границы `severity`, пустой `summary` отклоняется, JSON round-trip, фабрики заполняют нужные поля.
> **Готово, когда:** тесты зелёные, события полностью сериализуемы, mypy strict.

---

### T10 — Конфиг и снимок мира (`core/state.py`)

*Этап 0.2 Домен · P0 · зависит: T08*

**Промпт:**

> Реализуй `src/worldsim/core/state.py` — конфиг и иммутабельный снимок мира.
> - `WorldConfig(BaseModel, frozen=True)`: `seed: int`, `size: int` (4..512), `initial_factions: int = 0` (0..4), `aggression: float` (0..1, дефолт 0.5), `growth_rate: float` (>= 0, дефолт 0.02), `plague_chance: float` (0..1, дефолт 0.01), `magic_level: float` (0..1, дефолт 0) — задел под фэнтези-миры.
> - `WorldState(BaseModel, frozen=True)`: `config: WorldConfig`, `year: int >= 0`, `map: WorldMap`; `evolve(**changes) -> WorldState` возвращает **новый провалидированный** снимок (не `model_copy(update=...)`, чтобы не обойти валидацию); `snapshot_hash() -> str` — sha256 от JSON (`sort_keys=True`, без пробелов), стабильный между процессами; `to_json()` / `from_json()`.
> - Ни один метод не мутирует текущий объект.
> - Тесты: frozen (присваивание → ошибка), `evolve` создаёт новый объект и валидирует, `snapshot_hash` стабилен и меняется при изменении населения, JSON round-trip.
> **Готово, когда:** тесты зелёные, hash не зависит от `id()` и времени, mypy strict.

---

### T11 — Летопись поверх BST (`core/chronicle.py`)

*Этап 0.2 Домен · P0 · зависит: T05, T09*

**Промпт:**

> Реализуй `src/worldsim/core/chronicle.py` — летопись поверх BST из T05.
> - `Chronicle`: `add(event: Event)` (ключ — год, мультимножество), `events_for_year(year)`, `between(start, end, inclusive=True)`, `all_events()` (хронологический порядок), `filter(type=None, faction_id=None, tile_id=None)`, `__len__`, `clear()`.
> - `to_markdown() -> str` — таблица `| Год | Тип | Событие |` с экранированием `|` в тексте; `to_json()` / `from_json()`.
> - Летопись не зависит от UI и не изменяет `WorldState`.
> - Тесты: порядок по годам, несколько событий в одном году, диапазон, фильтры, экранирование, JSON round-trip, 5000 событий без падения.
> **Готово, когда:** тесты зелёные, BST переиспользован (не скопирован), mypy strict.

---

### T12 — Процедурная генерация мира (`generator/`)

*Этап 0.3 Генерация и движок · P0 · зависит: T07, T08, T10*

**Промпт:**

> Реализуй процедурную генерацию мира в `src/worldsim/generator/`.
> - `terrain.py`: `generate_map(config: WorldConfig, rng: Rng) -> WorldMap`. Количество seed-точек `max(3, size*size // 20)`; биом назначается взвешенно; рост областей через BFS-flood-fill; сглаживание majority-фильтром (1–2 прохода); `COAST` добавляется по соседству с водой.
> - Поля тайла: `fertility` = `biome.base_fertility` + шум `rng.uniform(-10, 10)` + `10` за реку, границы `[0, 100]`; `elevation` = `biome.base_elevation` + шум (границы `[0, 9000]`); `has_river` — реки прокладываются от гор к ближайшей воде по убыванию высоты, на воде рек нет; вода получает `fertility = 0`, `population = 0`, `population_capacity = 0`.
> - Ресурсы: один главный ресурс на тайл по биому (лес → `WOOD`, горы/холмы → `IRON` или `GOLD`, равнины/побережье → `FOOD`, болото → `MANA`, пустыня/тундра → `GOLD` или `NONE`); `resource_amount = rng.uniform(5, 20)`; `resource_depletion = resource_amount * rng.uniform(50, 200)` (лет добычи); у воды `NONE` и нули.
> - Мана: `mana_density` = базовая плотность биома (горы 60, лес 40, болото 50, пустыня 5, равнины 10, тундра 15, побережье 15, океан 0) + шум `±10`, границы `[0, 100]`; `mana_regeneration = max(1, mana_density // 10)`; узлы лей-линий (`ley_line = True`) выбираются детерминированно на суше, `min(8, max(1, size // 12))` штук, с разносом; такому тайлу `mana_density = 100`, `mana_regeneration = 50`.
> - Стартовые значения: `population_capacity = int(fertility * 5 + 20)`; `population = rng.int(0, population_capacity // 2)` для суши; `happiness = 60`, `unrest = 0`, `infrastructure = 0`, `fortification = 0`, `army_presence = 0`, `urbanization = min(100, population / 20)`, `culture = None`, `owner_id = None`, `assimilation = 0`.
> - `world.py`: `create_world(config: WorldConfig) -> WorldState` — собирает карту через `Rng(config.seed)` и возвращает снимок года 0.
> - Время и глобальный `random` запрещены: карта полностью определяется `config.seed`.
> - Тесты `tests/generator/test_terrain.py`: одинаковый seed → идентичный `snapshot_hash`; разные seed → разные карты; на 64×64 минимум 4 биома, есть реки, тайлы с ресурсами, узлы лей-линий и тайлы с маной; вода без населения и владельца; все значения в диапазонах; детерминизм между процессами.
> **Готово, когда:** тесты зелёные, генерация 128×128 занимает меньше 2 секунд, mypy strict.

---

### T13 — Ядро движка и рост населения (`engine/`)

*Этап 0.3 Генерация и движок · P0 · зависит: T10, T11*

**Промпт:**

> Реализуй основу движка в `src/worldsim/engine/`.
> - `rules.py`: `Rule(Protocol)` с `name: str`, `priority: int`, `apply(state: WorldState, ctx: StepContext) -> RuleOutcome`; `StepContext` (frozen): `year`, `rng`, `stats` (кэш метрик), `config`; `RuleOutcome`: `tile_updates` (изменения `owner_id` и `population` по id тайла), `events`, `faction_updates`.
> - `engine.py`: `SimulationEngine(rules: Sequence[Rule], chronicle: Chronicle)`; `state`, `step() -> WorldState` — правила выполняются по `priority`, каждое получает уже обновлённый снимок, изменения применяются через `evolve`, события добавляются в летопись, год инкрементируется; `run(years: int) -> WorldState`.
> - `rules/population.py`: `PopulationGrowthRule` — рост пропорционален `fertility` и `config.growth_rate`, ограничен ёмкостью тайла; при перенаселении генерируется `FAMINE`; на воде население не растёт.
> - Тесты: год инкрементируется, население растёт, старый снимок не изменился (hash до/после), порядок правил по `priority`, два прогона с одинаковым seed идентичны.
> **Готово, когда:** тесты зелёные, движок не знает про UI и фракции, mypy strict.

---

### T14 — Случайные события движка

*Этап 0.3 Генерация и движок · P0 · зависит: T13*

**Промпт:**

> Добавь случайные события в `src/worldsim/engine/rules/random_events.py`.
> - `PlagueRule`: вероятность = `config.plague_chance`, масштабируется плотностью (`population / size²`); при срабатывании выбирает 1–3 тайла через `ctx.rng`, убивает 10–60 % населения (`severity` = доля потерь), пишет `PLAGUE`.
> - `FamineRule`: срабатывает там, где `population > capacity`; снижает население и fertility (истощение), пишет `FAMINE` с severity.
> - Все выборки только через `ctx.rng`, обход тайлов детерминирован (по id).
> - Тесты: `plague_chance=0` → событий нет; `=1` → событие в первый год; одинаковый seed → одинаковая последовательность событий; эпидемия уменьшает население и не уводит ниже нуля; famine при перенаселении; события лежат в правильном году летописи.
> **Готово, когда:** тесты зелёные, нет обращений к глобальному `random`.

---

### T15 — Базовый Streamlit-интерфейс (`ui/`)

*Этап 0.3 Генерация и движок · P1 · зависит: T12, T13, T14*

**Промпт:**

> Реализуй базовый интерфейс `src/worldsim/ui/app.py` и `src/worldsim/ui/figures.py` (Streamlit + Plotly).
> - `figures.py`: `biome_figure(state: WorldState) -> go.Figure` — точки по координатам тайлов, цвет = `Biome.color`, hover = координаты/биом/население; построители не зависят от Streamlit и тестируются юнит-тестами.
> - `app.py`: сайдбар (seed, размер 32..128, кнопки «Сгенерировать мир», «Следующий год», «+10 лет»), карта, метрики (год, население, число событий), летопись через `Chronicle.to_markdown()`.
> - `WorldState`, `Chronicle` и `SimulationEngine` хранятся в `st.session_state` и пересоздаются только по кнопке генерации; бизнес-логики в `app.py` нет.
> - Тесты `tests/ui/test_figures.py`: фигура строится, число точек равно числу тайлов, цвета соответствуют биомам, импорт не требует Streamlit.
> **Готово, когда:** `worldsim` и `python -m worldsim` (entry point из T39) открывают карту, генерация и шаг работают, тот же seed даёт ту же карту; `streamlit run src/worldsim/ui/app.py` остаётся отладочным запуском.

---

### T16 — Модель фракции (`core/faction.py`)

*Этап 1 Фракции · P1 · зависит: T10*

**Промпт:**

> Реализуй `src/worldsim/core/faction.py` — фракция со всеми параметрами, на которые опираются правила этапа 1.
> - `Ideology(StrEnum)`: `MILITARIST, MERCANTILE, AGRARIAN, THEOCRATIC, SCHOLARLY, NOMADIC`; свойства `aggression_bonus`, `army_share` (доля населения, которую фракция готова держать в армии) и `military_multiplier` (множитель боевой мощи).
> - `MagicSchool(StrEnum)`: `FIRE, ICE, NECROMANCY, NATURE` — магические школы фракции.
> - `Faction(BaseModel, frozen=True)`: `id: int >= 0`; `name: str` (1..64, strip, непустое); `color: str` (regex `^#[0-9A-Fa-f]{6}$`); `ideology: Ideology`; `capital_tile_id: int | None = None`; `culture: str` (1..64, непустая) — культурная группа («Люди», «Эльфы», «Орки»); `aggressiveness: float` в `[0, 1]` — текущая агрессивность (растёт от голода, снижается после мира); `treasury: float >= 0` — казна (тратится на армию, технологии и позже строительство); `food_stockpile: float >= 0` — запасы еды (при нуле начинается голод); `tech_level: float` в `[0, 10]` (дефолт `1.0`); `resources: dict[str, float]` — специфические ресурсы, например `{"iron": 500, "mana_crystals": 10}` (ключи непустые, значения `>= 0`); `army_size: float >= 0`; `morale: float` в `[0, 1]` (дефолт `0.8`) — боевой дух; `mana_pool: int >= 0 = 0` — накопленная мана; `magic_affinity: int` в `[0, 100] = 0` — склонность к магии; `magic_schools: tuple[MagicSchool, ...] = ()` — доступные школы (при `magic_affinity > 0` хотя бы одна).
> - `military_power` — **вычисляемое** поле (`@computed_field` над `@property`): `army_size * (1 + 0.1 * tech_level) * ideology.military_multiplier`; именно оно сравнивается при разрешении войны, поэтому не хранится как редактируемое поле и игнорируется при десериализации.
> - `magic_power() -> float` — вычисляемый метод: `(magic_affinity / 100) * (1 + 0.1 * tech_level) * (1 + 0.25 * len(magic_schools))`; используется T21 как множитель к боевой мощи и T45 для боевых заклинаний.
> - `evolve(**changes) -> Faction` — новый провалидированный объект, собранный только из `Faction.model_fields` (вычисляемые `military_power` и `magic_power()` не передаются); `resources` копируется, чтобы снимки не делили один словарь.
> - Функция `culture_conflict_factor(a: Faction, b: Faction) -> float`: одинаковая культура — `0.2`, разные — `1.0`, неизвестные пары — `CULTURE_CONFLICT_BASE = 0.5`; используется правилами T20, T21, T34.
> - Уникальность имён и цветов проверяется на уровне мира (T17), не внутри `Faction`.
> - Тесты: валидаторы полей (отрицательная казна, `tech_level > 10`, пустая культура, отрицательный ресурс), `military_power` зависит от армии, технологий и идеологии, `evolve` не мутирует исходную фракцию и её `resources`, frozen, JSON round-trip, `culture_conflict_factor` для одинаковых и разных культур, `mana_pool` неотрицателен, `magic_affinity` в `[0, 100]`, при `magic_affinity > 0` школы не пусты, `magic_power()` растёт с технологиями и числом школ.
> **Готово, когда:** тесты зелёные, mypy strict.

---

### T17 — Владение тайлом и связь фракций со снимком

*Этап 1 Фракции · P1 · зависит: T08, T16*

**Промпт:**

> Свяжи фракции с картой и снимком мира.
> - `owner_id` уже объявлен в `RegionData` (T08); свяжи его с фракциями: `owner_id` неотрицателен, водные тайлы не имеют владельца, `army_presence > 0` только у тайлов с владельцем.
> - В `WorldState` добавь `factions: tuple[Faction, ...] = ()` и `model_validator(mode="after")`: все `owner_id` ссылаются на существующие фракции; у фракций уникальные `id`, `name`, `color`; столица принадлежит своей фракции; водные тайлы не имеют владельца.
> - Обратная совместимость JSON: снимок без `owner_id` и `factions` читается со значениями по умолчанию.
> - Тесты: несуществующий `owner_id` → ошибка, дубликат цвета → ошибка, владелец воды → ошибка, старый JSON читается, тесты T08 и T10 обновлены.
> **Готово, когда:** тесты зелёные, инварианты описаны в docstring `WorldState`, mypy strict.

---

### T18 — Генератор стартовых фракций и территорий

*Этап 1 Фракции · P1 · зависит: T12, T17*

**Промпт:**

> Реализуй распределение стартовых фракций в `src/worldsim/generator/factions.py`.
> - `spawn_factions(world_map: WorldMap, config: WorldConfig, rng: Rng) -> tuple[Faction, ...]`: количество = `config.initial_factions` (2..4; при 0 — без фракций); столицы выбираются детерминированно среди суши с высоким `fertility` и разносом не ближе `size // 4` (добор через `rng`); культура берётся из палитры (`Люди`, `Эльфы`, `Орки`, `Гномы`, `Нежить`) без повторов в одном мире; имена — из встроенного пула по культуре с суффиксом при коллизии; идеология назначается взвешенно; цвета — из встроенной палитры без повторов.
> - Стартовые значения: `treasury = 100.0`, `food_stockpile = 200.0`, `tech_level = 1.0`, `morale = 0.8`, `army_size = population * ideology.army_share` (не меньше 1), `resources` — по культуре и идеологии (эльфы — `{"mana_crystals": 10}`, орки — `{"iron": 500}`, гномы — `{"iron": 300, "gold": 50}`, люди — `{"gold": 100}`), `aggressiveness` — из конфига с поправкой `ideology.aggression_bonus` в `[0, 1]`; `mana_pool = 0`; `magic_affinity` — по культуре (Эльфы 90, Нежить 70, Люди 50, Орки 40, Гномы 20); `magic_schools` — по культуре (Эльфы — `NATURE`, `ICE`; Гномы — `FIRE`; Орки — `FIRE`; Люди — `NATURE`; Нежить — `NECROMANCY`).
> - Обнови `create_world`: `initial_factions` по умолчанию 2, территории раздаются BFS-заливкой от столиц с равной скоростью, нейтральные тайлы остаются `owner_id=None`.
> - Тесты: число фракций соответствует конфигу, имена и цвета уникальны, культуры не повторяются, казна и запасы еды неотрицательны, `army_size` в допустимых границах, у каждой фракции непустая территория и столица принадлежит ей, все владельцы валидны, одинаковый seed → одинаковые культуры, имена, ресурсы и границы, при 0 фракций все `owner_id is None`.
> **Готово, когда:** тесты зелёные, детерминизм подтверждён `snapshot_hash`, mypy strict.

---

### T19 — Метрики фракций (`engine/metrics.py`)

*Этап 1 Фракции · P1 · зависит: T17*

**Промпт:**

> Реализуй `src/worldsim/engine/metrics.py` — агрегированные показатели, на которые опираются правила.
> - `FactionStats` (frozen): `faction_id`, `culture`, `tiles`, `population`, `food_production`, `food_consumption`, `treasury`, `food_stockpile`, `tech_level`, `army_size`, `military_power`, `morale`, `mana_pool`, `mana_income`, `magic_affinity`, `mana_density_avg`, `ley_lines`, `happiness_avg`, `unrest_avg`, `cities`, `is_starving`, `is_low_morale`, `border_contact: tuple[int, ...]`, `enemies: tuple[int, ...]`.
> - `compute_faction_stats(state: WorldState) -> dict[int, FactionStats]`: `food_production` = сумма `RegionData.food_output()` по тайлам фракции (учитывает плодородие 0–100, реку, инфраструктуру и население); `food_consumption` = `population * FOOD_PER_CAPITA`; `happiness_avg` и `unrest_avg` — средние по населённым тайлам; `cities` — число тайлов с `is_city`; `is_starving` = `food_stockpile <= 0` или `food_stockpile + food_production < food_consumption`; `is_low_morale` = `morale < MORALE_PEACE_THRESHOLD` (`0.3`); `military_power` = `Faction.military_power`; `mana_income` = сумма `mana_regeneration` контролируемых тайлов; `mana_density_avg` — средняя плотность маны по тайлам; `ley_lines` — число захваченных узлов; `enemies` — фракции с активной войной (из `WorldState.wars`, T41); `border_contact` — соседи по 4-связности с другим владельцем. `army_size` больше не выводится из населения — это состояние фракции.
> - Результат кэшируется в `StepContext.stats` на один шаг.
> - Тесты: формулы на ручной карте из четырёх тайлов, фракция без территории, голод `is_starving`, корректный расчёт границ, отсутствие деления на ноль.
> **Готово, когда:** тесты зелёные, метрики не мутируют снимок, mypy strict.

---

### T20 — Правило экспансии (`ExpansionRule`)

*Этап 1 Фракции · P1 · зависит: T19*

**Промпт:**

> Реализуй `src/worldsim/engine/rules/expansion.py`.
> - `ExpansionRule(priority=10)`: для каждой фракции (детерминированный порядок по `id`) решает, расширяться ли: при `is_starving` — всегда, иначе с вероятностью `aggressiveness * config.aggression * culture_conflict_factor(атакующий, защитник)`, но не чаще одной атаки за год; цели под перемирием (T41) пропускаются.
> - Цель — соседний тайл другого владельца или нейтральный; вес цели: `fertility * (1 - fortification / 150) * (1 + unrest / 100) / (army_presence + 1)`; низкие тайлы предпочтительнее горных (`elevation` и `movement_cost` биома), нейтральный тайл занимается сразу, чужой — передаётся `WarResolutionRule` (T21) через очередь боёв в `StepContext`.
> - Голод повышает шанс атаки, но не меняет `aggressiveness` — это делает `EconomyRule` (T40).
> - Пишет `EXPANSION`, а при атаке — `WAR`, через фабрики `Event`.
> - Тесты: фракция с `food_stockpile = 0` атакует; сытая и неагрессивная — нет; цели выбираются по слабости защитника; лимит одна атака за год; события попадают в летопись; исходный снимок не изменён.
> **Готово, когда:** тесты зелёные, детерминизм при фиксированном seed, mypy strict.

---

### T21 — Правило войны (`WarResolutionRule`)

*Этап 1 Фракции · P1 · зависит: T19*

**Промпт:**

> Реализуй `src/worldsim/engine/rules/war.py` — разрешение боёв, накопленных `ExpansionRule`.
> - `WarResolutionRule(priority=20)`: для каждой заявки `attack = military_power атакующего * (1 + 0.2 * magic_power() атакующего) * rng.uniform(0.8, 1.2) * culture_conflict_factor(атакующий, защитник)`; `defense = (army_presence защитника + 0.25 * army_size фракции-защитника) * (1 + 0.2 * magic_power() защитника) * biome.defense_bonus * RegionData.defense_multiplier() * rng.uniform(0.8, 1.2)`; при `attack > defense` тайл переходит атакующему.
> - Оккупация: победитель оставляет в тайле `army_presence` до 5 % своей армии; `fortification` падает на 25–50 %, `unrest` растёт на 20, `happiness` падает на 10, население теряет 5–10 %; событие `OCCUPATION`.
> - Потери: обе стороны теряют долю `army_size` (5–30 % в зависимости от разницы сил); проигравший теряет `morale` на `0.1`, победитель получает `+0.05` (в границах `[0, 1]`); победитель забирает из казны проигравшего трофеи (10–50 золота, не больше остатка).
> - При переходе столицы — `CAPITAL_FALL` и перенос столицы на защищённый тайл победителя.
> - В `WorldState` появляется `wars: tuple[War, ...] = ()`: битва между двумя фракциями заводит или обновляет запись войны (`core/diplomacy.py`: `id`, `attacker_id`, `defender_id`, `started_year`, `battles`, `attacker_losses`, `defender_losses`, `active`, `truce_until_year`), которую использует дипломатия T41.
> - Количество атак за год ограничено (например, 3 на сторону), все случайные числа — из `ctx.rng`.
> - Пишет `WAR`, `BATTLE_WON` / `BATTLE_LOST`; итоги обновляют `morale`, `army_size` и `treasury` через `faction_updates`.
> - Тесты: сильнейший побеждает чаще (100 прогонов с фиксированными seed, больше 60 % побед), потери уменьшают `army_size`, `morale` меняется только у участников, казна не уходит в минус, `owner_id` меняется ровно у одного тайла, падение столицы обработано, повторный прогон идентичен.
> **Готово, когда:** тесты зелёные, результат не зависит от порядка словарей, mypy strict.

---

### T22 — UI: политическая карта

*Этап 1 Фракции · P1 · зависит: T15, T18*

**Промпт:**

> Добавь слой политической карты в UI.
> - `figures.py`: `political_figure(state)` — цвет = `Faction.color`, нейтральные серые, hover: фракция, культура, население, армия, боевая мощь; `tile_layer_figure(state, layer)` — слои `biomes`, `political`, `resources`, `happiness`, `unrest`, `army`, `mana` (цвет по выбранному показателю, hover со всеми параметрами тайла).
> - `app.py`: переключатель слоя карты, панель тайла (координаты, биом, население и ёмкость, плодородие, высота, река, ресурс и остаток, инфраструктура, счастье, урбанизация, армия, фортификация, недовольство, мана: плотность, регенерация и лей-линия), таблица фракций (цвет, имя, культура, идеология, территории, население, казна, запасы еды, технологии, армия, боевая мощь, мораль), панель ресурсов фракции.
> - В UI только отрисовка готовых `RegionData` и `FactionStats`, никаких правил.
> - Тесты: `political_figure` строит точку на каждый тайл, цвета совпадают с `Faction.color`, нейтральные серые, при 0 фракций карта не падает, `tile_layer_figure` для каждого слоя строит точки и не требует Streamlit.
> **Готово, когда:** тесты зелёные, переключение слоёв визуально работает на трёх фракциях.

---

### T23 — Интеграционные тесты сценария фракций

*Этап 1 Фракции · P1 · зависит: T20, T21, T22, T40, T41*

**Промпт:**

> Напиши сценарные тесты этапа 1 в `tests/integration/test_factions_scenario.py`.
> - `create_world(WorldConfig(seed=42, size=32, initial_factions=3))` → `run(100)` → инварианты: территории валидны, все `owner_id` существуют, население неотрицательно, `treasury >= 0`, `food_stockpile >= 0`, `0 <= morale <= 1`, `army_size >= 0`, значения `resources` неотрицательны, летопись упорядочена по годам; полное исчезновение фракции допустимо только вместе с событием.
> - Сценарий голода: выставить `food_stockpile = 0` → за 10 лет население падает, `aggressiveness` растёт, в летописи есть `STARVATION`.
> - Сценарий мира: довести фракцию до `morale < 0.3` поражениями → появляются `PEACE_OFFER` и `PEACE_TREATY`, атаки на время перемирия прекращаются.
> - Инварианты тайлов: `0 <= fertility/happiness/unrest/urbanization/fortification/infrastructure <= 100`, `elevation` в `[0, 9000]`, `army_presence >= 0`, `army_presence` только у тайлов с владельцем, `is_city` соответствует порогам, `mana_density` в `[0, 100]`, `mana_regeneration >= 0`, `mana_pool >= 0`.
> - Сценарий магии: на карте есть лей-линии; фракция с академией растит `magic_affinity`; при достаточной мане война даёт бонус, при нуле `mana_pool` бонус равен нулю.
> - Сценарии тайлов: город появляется при населении больше 1000 и урбанизации не ниже 50 (`CITY_RISE`); при `unrest > 80` тайл отделяется или переходит к соседу (`SECESSION` / `DEFECTION`); добыча уменьшает `resource_depletion` и при нуле даёт `RESOURCE_DEPLETED`; оккупация повышает `unrest` и снижает `fortification`.
> - Сохраняй снимок каждого 10-го года и проверяй, что его `snapshot_hash` не изменился после следующих шагов.
> - Повторный прогон с тем же seed → идентичный финальный hash и идентичная летопись; с другим seed → отличается.
> **Готово, когда:** тесты зелёные, прогон меньше 10 секунд, сценарии помечены маркером `integration`.

---

### T24 — Репозиторий и модель коммита (`vcs/`)

*Этап 2 VCS · P1 · зависит: T10*

**Промпт:**

> Реализуй модель коммита и хранилище в `src/worldsim/vcs/`.
> - `commit.py`: `Commit(BaseModel, frozen=True)`: `id: str` (sha256 от родителя, года, сообщения и содержимого снимка), `parent_id: str | None`, `branch: str`, `year: int`, `message: str`, `created_at: datetime` (UTC, передаётся снаружи — без `datetime.now()` внутри моделей), `snapshot_hash: str`.
> - `repo.py`: `WorldRepo(root: Path)`; раскладка `.worldsim/`: `objects/<commit_id>.json` (метаданные + снимок + летопись), `refs/branches/<name>` (id), `HEAD`. `init()` создаёт структуру; `_write_atomic(path, data)` пишет через временный файл и `os.replace`; повреждённые файлы → `RepositoryError`.
> - Тесты `tests/vcs/test_repo.py` на `tmp_path`: `init` идемпотентен, атомарная запись, чтение объекта, отсутствующий объект → ошибка, раскладка каталогов корректна.
> **Готово, когда:** тесты зелёные, сетевых вызовов нет, mypy strict.

---

### T25 — Операции `commit` / `checkout` / `log`

*Этап 2 VCS · P1 · зависит: T24*

**Промпт:**

> Реализуй операции репозитория.
> - `commit(state, message, branch="main", created_at=None) -> Commit`: сериализует снимок и летопись, вычисляет id, обновляет ref ветки и `HEAD`; одинаковые снимок, родитель и сообщение дают одинаковый id.
> - `checkout(ref: str) -> tuple[WorldState, Chronicle]`: `ref` — id коммита, имя ветки или `HEAD`; загружает и валидирует снимок, восстанавливает летопись из того же объекта.
> - `log(branch=None) -> list[Commit]` — от HEAD к корню; `current_branch()`, `head()`.
> - Тесты: `commit` → `checkout` восстанавливает идентичные `snapshot_hash` и `chronicle.to_json()`; порядок `log`; checkout несуществующего ref → `RepositoryError`; два коммита подряд связаны `parent_id`.
> **Готово, когда:** тесты зелёные, после checkout снимок полностью детерминирован.

---

### T26 — Ветвление и альтернативные реальности

*Этап 2 VCS · P1 · зависит: T25*

**Промпт:**

> Реализуй ветвление (сценарий «альтернативная реальность»).
> - `create_branch(name: str, from_ref: str = "HEAD")` с валидацией имени `[A-Za-z0-9_-]+` и запретом существующих, `checkout_branch(name)`, `list_branches() -> dict[str, str]`; `merge` не реализуется — явно задокументируй это в docstring.
> - Сценарий-демо: `checkout("year_100")` → `state.evolve(config=state.config.evolve(aggression=0.9))` → `engine.run(50)` → `commit(new_state, "alt: высокая агрессия", branch="alt")`.
> - Тесты: ветка от середины истории, коммиты в ветке не меняют основную, checkout ветки возвращает её HEAD, две ветки с разными параметрами и одинаковым seed дают разные итоги, имена валидируются.
> **Готово, когда:** тесты зелёные, `log` показывает развилку.

---

### T27 — Сравнение снимков (`diff`)

*Этап 2 VCS · P1 · зависит: T26*

**Промпт:**

> Реализуй сравнение снимков `src/worldsim/vcs/diff.py`.
> - `Diff` (frozen): `years`, `tiles_changed`, `population_delta`, `owners_changed: tuple[TileOwnershipChange, ...]`, `factions_added`, `factions_removed`, `events_added`, метод `to_markdown()`.
> - `WorldRepo.diff(from_ref, to_ref) -> Diff`: сравнение по id тайла (владелец, население), по фракциям и по летописи; снимки разного размера не должны ронять метод — внятная ошибка или частичный diff.
> - Тесты: без изменений → пустой diff; смена владельца и рост населения видны; markdown-таблица корректна; разный размер карт обработан.
> **Готово, когда:** тесты зелёные, mypy strict.

---

### T28 — UI: таймлайн и «альтернативная реальность»

*Этап 2 VCS · P1 · зависит: T15, T26*

**Промпт:**

> Добавь «машину времени» в UI.
> - `figures.py`: `timeline_figure(commits) -> go.Figure` — граф коммитов (x = год, y = ветка), линии родитель → ребёнок, hover: сообщение, год, ветка.
> - `app.py`: панель «История» (список коммитов, кнопки «Checkout», «Новая ветка»), кнопка «Создать альтернативную реальность» (выбор коммита → изменение параметра слайдером → новая ветка → прогон N лет), показ diff к родителю.
> - Репозиторий по умолчанию — `.worldsim/` в корне проекта (закрыт `.gitignore`), путь переопределяется в сайдбаре.
> - Тесты: `timeline_figure` строит узлы и рёбра, checkout через UI-обёртку возвращает снимок, diff отображается.
> **Готово, когда:** сценарий из T26 воспроизводится через интерфейс.

---

### T29 — Тесты VCS и ветвления

*Этап 2 VCS · P1 · зависит: T27, T28*

**Промпт:**

> Дополни тесты ветвления `tests/vcs/test_branching.py`.
> - Полный сценарий: три ветки, две развилки, checkout старых коммитов, коммит после checkout, восстановление после «повреждённого» объекта, неизменность основной ветки.
> - Свойство: `checkout(commit_id)` восстанавливает `snapshot_hash` и `chronicle.to_json()` без расхождений.
> **Готово, когда:** тесты зелёные, покрытие `vcs/` не ниже 85 %, сценарии помечены маркером `integration`.

---

### T30 — Клиент LLM (`ai/client.py`)

*Этап 3 ИИ · P2 · зависит: T03*

**Промпт:**

> Реализуй клиент LLM в `src/worldsim/ai/client.py`; в тестах сетевые вызовы не выполняются.
> - `LLMClient(Protocol)`: `complete(messages, *, json_mode: bool = False, temperature: float = 0.7) -> str`; реализации `OpenAIClient`, `GroqClient` (OpenAI-совместимый `/chat/completions` через `httpx`), `OllamaClient` (`POST /api/chat`).
> - `create_client(provider: str | None = None) -> LLMClient` — провайдер из `WORLDSIM_AI_PROVIDER` или автоопределение по ключам (`OPENAI_API_KEY`, `GROQ_API_KEY`, `OLLAMA_HOST`); при отсутствии конфигурации — `AIUnavailableError`.
> - Таймаут 30 с, два повтора с экспоненциальной задержкой на 429 и 5xx; ключи читаются из env и **никогда** не попадают в логи, исключения и `repr`.
> - Тесты на фейковом транспорте: успех, повтор, отсутствие ключа → `AIUnavailableError`, ключ не утекает в текст исключения.
> **Готово, когда:** тесты зелёные без сети, `.env.example` актуален, mypy strict.

---

### T31 — ИИ-хронист

*Этап 3 ИИ · P2 · зависит: T11, T30*

**Промпт:**

> Реализуй ИИ-хрониста в `src/worldsim/ai/chronicler.py`.
> - `ChronicleWriter(client: LLMClient)`: `write_chapter(events: Sequence[Event], year_from: int, year_to: int) -> str` — собирает из событий компактный JSON (год, тип, фракции, severity) и просит главу на 400–800 слов на русском; системный промпт запрещает выдумывать факты, которых нет в событиях.
> - Проверка ответа: непустой текст, упомянуты все годы периода, нет заглушек; при недоступности ИИ — `fallback_chapter(events)` из `Chronicle.to_markdown()`.
> - `save_chapter(path: Path, text: str)` — атомарная запись в `chronicle/chapter_<from>_<to>.md` с YAML-front-matter (год начала и конца, seed, модель).
> - Тесты с mock-клиентом: файл создан, front-matter корректен, fallback работает, ключи не попадают в файл, пустой список событий обрабатывается.
> **Готово, когда:** тесты зелёные, реальный вызов ИИ для CI не требуется.

---

### T32 — ИИ-генератор конфигурации мира

*Этап 3 ИИ · P2 · зависит: T10, T30*

**Промпт:**

> Реализуй генератор конфигурации по текстовому описанию в `src/worldsim/ai/world_builder.py`.
> - `build_config(user_prompt: str, client: LLMClient) -> WorldConfig`: промпт требует строгий JSON с полями `seed`, `size`, `initial_factions`, `aggression`, `growth_rate`, `plague_chance`, `magic_level` и описанием фракций (имя, идеология, цвет); ответ парсится `json.loads`; невалидный ответ — одна повторная попытка с текстом ошибки, затем `AIUnavailableError`.
> - `apply_config(...)`: создаёт мир через `create_world`, следит, чтобы имена и цвета фракций из ИИ прошли валидацию, при конфликте — заменяет сгенерированными.
> - Исходный промпт и итоговый JSON сохраняются в `worlds/<hash>.json` для воспроизводимости.
> - Тесты: валидный JSON, обрезанный JSON → повтор → ошибка, значения вне диапазона отвергаются, мир сохраняется.
> **Готово, когда:** тесты зелёные без сети, mypy strict.

---

### T33 — UI: интеграция ИИ

*Этап 3 ИИ · P2 · зависит: T15, T31, T32*

**Промпт:**

> Встрой ИИ в интерфейс.
> - `app.py`: вкладки «Мир» / «История» / «ИИ»; поле описания мира и кнопка «Создать мир по описанию» (предпросмотр конфига, fallback на ручные параметры); кнопка «Написать главу летописи» за период с индикатором прогресса и скачиванием `.md`; `AIUnavailableError` показывается понятным сообщением.
> - Клиент создаётся лениво (только при нажатии кнопки); без ключей интерфейс работает в обычном режиме.
> - Тесты: сборка конфига из формы, обработка ошибок клиента, отсутствие ключей не ломает страницу.
> **Готово, когда:** без ключей UI деградирует корректно, с ключом генерирует главу.

---

### T34 — Культура и религия

*Этап 4 Культура и экономика · P3 · зависит: T17*

**Промпт:**

> Добавь культуру и религию в модель и правила.
> - `core/culture.py`: `Culture` (`id`, `name`, `traits: tuple[str, ...]`), `Religion` (`id`, `name`, `culture_id`, `zeal`); в `RegionData` — `culture_id: int | None`, `religion_id: int | None`; в `WorldState` — `cultures`, `religions` с валидацией ссылок.
> - `Faction.culture` из T16 — строковая метка: валидатор `WorldState` требует, чтобы культура каждой фракции совпадала с `Culture.name` (регистр не важен); для миров без `cultures` проверка пропускается (обратная совместимость).
> - `RegionData.culture` (T08) — культура населения тайла: при захвате тайла фракцией другой культуры `assimilation` растёт на 0.05–0.1 за год, если `happiness > 50`, и падает на 0.05 при войне и бунтах; при `assimilation >= 1.0` культура тайла меняется на культуру владельца, `assimilation` сбрасывается в 0.
> - `engine/rules/culture.py`: `CultureClashRule` — при соседстве разных культур растёт напряжение; вероятность конфликта считается через `culture_conflict_factor` из T16 и `traits` культур; при высоком напряжении событие `CULTURE_CLASH` (падение населения и рождаемости); `ConversionRule` — религия с высоким `zeal` постепенно вытесняет соседнюю.
> - UI: слой «Культуры».
> - Тесты: валидаторы ссылок, конфликт только на границе культур, одинаковые культуры не конфликтуют, детерминизм.
> **Готово, когда:** тесты зелёные, миры без культур работают (обратная совместимость).

---

### T35 — Система плагинов правил

*Этап 4 Культура и экономика · P3 · зависит: T13*

**Промпт:**

> Реализуй систему плагинов правил.
> - `engine/plugins.py`: `load_rules(sources: Sequence[str | Path]) -> list[Rule]` — загрузка по entry points группы `worldsim.rules` и из директорий `plugins/` (модули `*_rule.py`); проверка соответствия `Rule` Protocol; конфликт имён → ошибка; падающее правило не роняет движок: событие `CUSTOM` и правило отключается.
> - Порядок применения — по `Rule.priority`; флаг `enabled`.
> - Пример-плагин `plugins/mana_rule.py`: `ManaRegenerationRule` — при `magic_level > 0` население растёт быстрее, при высоком уровне возможны события `CUSTOM`.
> - UI: список подключённых правил; `scripts/run_sim.py --plugin plugins/mana_rule.py`.
> - Тесты: загрузка entry point (mock), падающее правило изолировано, порядок по `priority`, пример-плагин влияет на рост населения.
> **Готово, когда:** тесты зелёные, без плагинов движок работает как раньше.

---

### T36 — Ресурсы и торговые пути

*Этап 4 Культура и экономика · P3 · зависит: T19, T34*

**Промпт:**

> Добавь ресурсы и торговые пути.
> - `core/resources.py`: `ResourceType` уже объявлен в T08; здесь — `MANA` как ресурс — это добываемая кристаллическая мана, она отличается от фоновой `mana_density` тайла (T08), которая питает академии и заклинания. `TradeRoute` (`from_tile`, `to_tile`, `resource`, `capacity`) и `ExtractionRule` (`engine/rules/extraction.py`): при наличии владельца и `resource_type != NONE` фракция получает `resource_amount * (1 + infrastructure / 100) * (1 + 0.25 * has_river)` единиц ресурса; `FOOD` пополняет `food_stockpile`, `GOLD` — `treasury`, `IRON`/`WOOD`/`MANA` — `resources`; `resource_depletion` уменьшается на добычу, при нуле — событие `RESOURCE_DEPLETED`; город (`is_city`) даёт +20 % к добыче.
> - `engine/rules/trade.py`: `TradeRule` — между соседними тайлами разных фракций в мире (без войны и перемирия) строятся маршруты; бонус дают река и инфраструктура; каждая фракция получает доход в `treasury` и пополняет `resources`; при войне маршруты рвутся; событие `TRADE`.
> - UI: слой ресурсов и панель торговли.
> - Тесты: маршрут только между соседями, война рвёт маршрут, доход неотрицателен, детерминизм, обратная совместимость JSON.
> **Готово, когда:** тесты зелёные, старые снимки читаются.

---

### T37 — Архитектурная документация и ADR

*Этап 4 Культура и экономика · P2 · зависит: T29, T33*

**Промпт:**

> Закрой документацию проекта.
> - `docs/ARCHITECTURE.md`: схема модулей (mermaid), поток данных `generator → engine → chronicle → vcs → ui`, инварианты иммутабельности и детерминизма, формат репозитория `.worldsim/`, список правил и их приоритеты.
> - `docs/adr/`: 4–6 ADR по шаблону «Контекст / Решение / Последствия»: `0001-src-layout`, `0002-frozen-pydantic`, `0003-bst-chronicle`, `0004-json-vcs`, `0005-rules-protocol`, `0006-seeded-rng`.
> - `README.md`: полный quickstart, все команды, ссылки на ADR; `docs/OBSIDIAN.md` — как импортировать ADR в vault проекта.
> - `scripts/check_docs.py` — проверка относительных ссылок и якорей в Markdown, запускается в CI.
> **Готово, когда:** `check_docs.py` без ошибок, публичные модули имеют docstrings, README воспроизводится на чистом venv.

---

### T38 — Производительность шага симуляции

*Этап 4 Культура и экономика · P3 · зависит: T23, T29*

**Промпт:**

> Оптимизируй шаг симуляции для больших карт.
> - Замерь `step()` на 256×256 за 200 лет, найди узкие места (копирование pydantic-моделей, пересчёт метрик).
> - Введи кэш метрик на шаг, батч-применение изменений (один `evolve` на правило вместо одного на тайл), при необходимости — numpy-представление населения с синхронизацией в pydantic на границе шага.
> - Цель: 256×256 не дольше 50 мс на шаг, память не больше 300 МБ; закрепи бенчмарком `tests/benchmarks/test_step_benchmark.py` (маркер `slow`, в CI по умолчанию не запускается).
> **Готово, когда:** цель достигнута или задокументировано, почему нет; тесты детерминизма не изменились.

---

### T39 — Перевод проекта из библиотеки в приложение

*Этап 0.1 · P0 · зависит: T02*

**Промпт:**

> Продукт — приложение, а не библиотека: пользователь запускает WorldSim и работает с ним через веб-интерфейс; импорт пакета как публичного API не предусмотрен.
> - `pyproject.toml`: добавь `[project.scripts] worldsim = "worldsim.launcher:main"`; убери классификатор `Typing :: Typed` и `[tool.setuptools.package-data]`; удали `src/worldsim/py.typed`; в описании пакета укажи приложение.
> - `src/worldsim/launcher.py`: `app_script() -> Path`, `build_streamlit_argv(args: list[str]) -> list[str]`, `main(argv: list[str] | None = None) -> int` — запускает `streamlit run worldsim/ui/app.py`, импортирует Streamlit лениво и корректно обрабатывает `SystemExit`.
> - `src/worldsim/__main__.py`: `python -m worldsim` вызывает `launcher.main()`.
> - `src/worldsim/ui/app.py`: стартовая страница приложения (заголовок, версия, статус, подсказка о следующих задачах); карта и управление появятся в T15.
> - `README.md`: запуск `pip install -e .` → `worldsim`, эквивалент `python -m worldsim`, передача аргументов Streamlit, режим разработки.
> - `docs/TASK.md`: тип проекта — прикладное веб-приложение, формулировки без «библиотеки», в дереве структуры — `launcher.py`, `__main__.py`, `ui/app.py`.
> - `docs/PROMPTS.md`: Definition of Done дополняется требованием «приложение запускается», промпты T03 и T15 учитывают entry point.
> **Готово, когда:** `pip install -e .` регистрирует команду `worldsim`, `python -m worldsim` запускает Streamlit и страница отвечает HTTP 200, `py.typed` и библиотечные формулировки удалены из проекта.

---

### T40 — Экономика фракции: снабжение, казна, армия, технологии

*Этап 1 Фракции · P1 · зависит: T19*

**Промпт:**

> Реализуй `src/worldsim/engine/rules/economy.py` — экономику фракции, на которой держатся голод, армия и технологии.
> - `EconomyRule(priority=5)` — выполняется до экспансии и войны, обходит фракции в порядке `id`.
> - **Еда:** `food_stockpile += food_production - food_consumption` (формулы T19 на основе `RegionData.food_output()`; счастье и недовольство реагируют в T42). Если запас стал отрицательным — обнуляется, население фракции теряет 5–15 % (доля через `ctx.rng`), `morale -= 0.05`, `aggressiveness += 0.05` (в границах `[0, 1]`), событие `STARVATION` с `severity` = доля потерь.
> - **Содержание армии:** `army_size * UPKEEP_PER_SOLDIER` списывается из `treasury`; при нехватке `army_size` уменьшается (дезертирство), `morale -= 0.02`, событие `DESERTION`.
> - **Набор:** если `treasury` выше порога и `army_size < population * ideology.army_share`, фракция набирает рекрутов за золото, но не больше 10 % населения за год; событие `RECRUITMENT`.
> - **Технологии:** при профиците казны `tech_level += 0.02 * (1 + бонус идеологии)` (потолок `10`) за золото; событие `TECH_ADVANCE`.
> - **Мана:** `mana_pool += mana_income` (T19: сумма `mana_regeneration` контролируемых тайлов), `mana_pool` не уходит в минус; расход маны — в T44 и T45.
> - **Строительство:** пока не моделируется — расходы зарезервированы под будущую задачу (отметь в docstring).
> - Все изменения — через `faction_updates` и `evolve`; порядок обхода и все случайные числа детерминированы.
> - Тесты: голод уменьшает население и повышает агрессивность; пустая казна даёт дезертирство; профицит растит `tech_level` с потолком; армия не превышает `army_share * population`; `treasury` и `food_stockpile` не уходят в минус; одинаковый seed → одинаковые значения; исходный снимок не изменён.
> **Готово, когда:** тесты зелёные, события `STARVATION` / `DESERTION` / `RECRUITMENT` / `TECH_ADVANCE` попадают в летопись, mypy strict.

---

### T41 — Дипломатия: запрос мира и перемирие

*Этап 1 Фракции · P1 · зависит: T21*

**Промпт:**

> Реализуй дипломатию и запрос мира в `src/worldsim/core/diplomacy.py` и `src/worldsim/engine/rules/diplomacy.py`.
> - `War` из T21 (`core/diplomacy.py`) получает поле `truce_until_year: int | None = None`; если модель ещё не создана — создай её здесь.
> - `DiplomacyRule(priority=30)`: фракция с `morale < MORALE_PEACE_THRESHOLD` (`0.3`), ведущая активную войну, с вероятностью `min(1, (threshold - morale) * 2)` запрашивает мир — событие `PEACE_OFFER`.
> - Принятие мира: противник соглашается, если его `morale < 0.5` или его потери в войне выше (детерминированное правило; `ctx.rng` — только для пограничных случаев) → `War.active = False`, `truce_until_year = year + TRUCE_YEARS` (`10`), событие `PEACE_TREATY`; `morale` обеих фракций `+0.1`, `aggressiveness` `-0.1` в границах `[0, 1]`.
> - `ExpansionRule` (T20) и `TradeRule` (T36) обязаны учитывать перемирие: цели и маршруты под перемирием недоступны.
> - UI: статус «в войне» / «перемирие до года N» в панели фракции.
> - Тесты: низкая мораль рождает `PEACE_OFFER`; принятие завершает войну и прекращает атаки на время перемирия; высокая мораль сохраняет войну; снимок иммутабелен; одинаковый seed → одинаковое поведение.
> **Готово, когда:** тесты зелёные, сценарий мира из T23 проходит, mypy strict.

---

### T42 — Социальная динамика тайлов: счастье, недовольство, урбанизация

*Этап 1 Фракции · P1 · зависит: T17, T34, T40*

**Промпт:**

> Реализуй `src/worldsim/engine/rules/social.py` — социальную динамику тайлов.
> - `HappinessRule(priority=12)`: счастье растёт при запасах еды, культуре владельца, низком `unrest` и присутствии армии; падает при голоде, войне, чужой культуре и высоком `unrest`; шаг 1–3 пункта за год, границы `[0, 100]`.
> - `UnrestRule(priority=13)`: недовольство растёт от счастья ниже 40, голода и чужой культуры, снижается армией и инфраструктурой; границы `[0, 100]`.
> - `RiotRule`: при `happiness < 20` и `unrest > 60` — бунт: население −5–15 %, событие `RIOT`, `unrest += 10`.
> - `SecessionRule`: при `unrest > 80` тайл отделяется (`owner_id = None`, `army_presence = 0`, событие `SECESSION`) или переходит к соседней фракции той же культуры (событие `DEFECTION`), выбор — детерминированно по соседям.
> - `UrbanizationRule`: `urbanization` растёт при населении больше 500 и `infrastructure > 20`, падает при голоде и бунтах; при `population > 1000` и `urbanization >= 50` тайл становится городом (`is_city`), событие `CITY_RISE`; город даёт +20 % к добыче и +10 к `population_capacity`.
> - Изменения только через `tile_updates`; обход тайлов по `id`; `ctx.rng` — только для пороговых случаев.
> - Тесты: бунт при низком счастье; отделение при `unrest > 80`; город на пороге; счастье восстанавливается в мирные годы; одинаковый seed → одинаковое поведение.
> **Готово, когда:** тесты зелёные, события `RIOT` / `SECESSION` / `DEFECTION` / `CITY_RISE` попадают в летопись, mypy strict.

---

### T43 — Армии на карте: присутствие, перемещение, оккупация

*Этап 1 Фракции · P1 · зависит: T17, T20, T21*

**Промпт:**

> Реализуй армии на карте в `src/worldsim/engine/rules/army.py`.
> - `ArmyMovementRule(priority=7)`: фракция распределяет `army_size` по своим тайлам; приоритет — тайлы на границе с врагом и тайлы с высоким `unrest`; стоимость перемещения учитывает `biome.movement_cost`, `elevation` и `has_river`/`infrastructure`; суммарный `army_presence` не превышает `army_size`.
> - `OccupationRule(priority=21)`: тайл с чужим `army_presence` оккупируется только после победы в бою (T21); оккупант оставляет гарнизон, `unrest += 20`, `happiness -= 10`; при потере гарнизона тайл возвращается владельцу или становится нейтральным — событие `OCCUPATION`.
> - `FrontlineRule`: тайлы на границе с враждебной фракцией получают +20 % к распределению армии; присутствие армии даёт +10 к защите тайла (учитывается T21).
> - UI: слой «Армии» и число солдат в hover.
> - Тесты: сумма `army_presence` ≤ `army_size`; армия стягивается к фронту; река ускоряет перемещение; оккупация меняет `owner_id` только после боя; детерминизм.
> **Готово, когда:** тесты зелёные, сценарий оккупации из T23 проходит, mypy strict.

---

### T44 — Магическая экономика: доход маны, академии, школы

*Этап 5 Магия · P2 · зависит: T16, T19, T40*

**Промпт:**

> Реализуй магическую экономику в `src/worldsim/core/magic.py` и `src/worldsim/engine/rules/magic.py`.
> - `MagicAcademy(BaseModel, frozen=True)`: `id`, `tile_id`, `faction_id`, `school: MagicSchool`, `level: int >= 1`, `founded_year: int`; в `WorldState` — `academies: tuple[MagicAcademy, ...] = ()` с валидацией: тайл принадлежит фракции, `mana_density >= ACADEMY_MIN_DENSITY` (`50`), не больше одной академии на тайл.
> - `ManaRule(priority=6)`: `mana_pool += mana_income` (доход T19: сумма `mana_regeneration` контролируемых тайлов; лей-линии учитываются своим приростом); `mana_pool` не уходит в минус.
> - `AcademyRule(priority=14)`: фракция строит академию, если `treasury >= 100` и `mana_pool >= 50`, выбирая тайл с максимальной `mana_density` (детерминированно, без Streamlit); списывает золото и ману, событие `ACADEMY_FOUNDED`.
> - `MagicResearchRule(priority=15)`: при `mana_pool >= 20` и наличии академий `magic_affinity += 1` (потолок 100), уровень школ растёт; без академий склонность не растёт; событие `MAGIC_BREAKTHROUGH` раз в несколько лет.
> - `magic_power()` фракции (T16) учитывает `magic_affinity`, `tech_level` и число школ.
> - Тесты: мана копится и не уходит в минус; академия строится только на тайле с плотностью не ниже 50 и при достаточных ресурсах; без маны исследования не идут; лей-линия даёт больше дохода; детерминизм.
> **Готово, когда:** тесты зелёные, события `ACADEMY_FOUNDED` / `MAGIC_BREAKTHROUGH` попадают в летопись, mypy strict.

---

### T45 — Магия в бою: школы, контршколы, расход маны

*Этап 5 Магия · P2 · зависит: T21, T44*

**Промпт:**

> Реализуй боевую магию в `src/worldsim/engine/rules/battle_magic.py`.
> - `MagicCombatRule(priority=18)` (до `WarResolutionRule`): перед боем фракция может потратить до 10 % `mana_pool` на усиление; `magic_bonus = 0.2 * (mana_spent / max(1, mana_pool_before)) * magic_power()`.
> - Контршколы: цикл `FIRE > ICE > NATURE > NECROMANCY > FIRE`; если у атакующего есть школа, побеждающая школу защитника, атака получает +15 %, иначе −10 %.
> - `magic_power()` (T16) = `(magic_affinity / 100) * (1 + 0.1 * tech_level) * (1 + 0.25 * len(magic_schools))`; T21 использует его как множитель, T45 добавляет школы и расход маны.
> - Расход маны пишется в событие `WAR` (`payload["mana_spent"]`); при нулевом `mana_pool` бонус равен нулю.
> - UI: магическая мощь и потраченная мана в панели фракции и в отчёте о битве.
> - Тесты: контршкола даёт преимущество; без маны бонуса нет; расход не превышает `mana_pool`; бой детерминирован при фиксированном seed.
> **Готово, когда:** тесты зелёные, сценарий магической войны из T23 проходит, mypy strict.

## Журнал изменений промптов

Любое изменение формулировки, порядка или состава промптов фиксируется здесь: дата, задача, что именно изменилось и почему. Журнал не переписывается задним числом — новые записи добавляются снизу.

| Дата | Задача | Изменение | Причина |
|------|--------|-----------|---------|
| 2026-11-11 | T00 | Статусы задач и журнал выполнения вынесены в `backlog.md`; из карточек задач убрано поле «статус» | Todo-лист должен вестись в `backlog.md`, чтобы не рассинхронизировать два файла |
| 2026-11-11 | T00 | Добавлено правило: любое изменение промпта фиксируется в этом журнале | Требование отслеживать изменения формулировок промптов |
| 2026-11-11 | T02 | Промпт выполнен без изменения текста | Изменений не потребовалось |
| 2026-11-12 | T39 | Новая задача: перевод продукта из библиотеки в приложение — точка входа `worldsim`, `__main__.py`, `launcher.py`, правки README и ТЗ | Требование заказчика: продукт должен быть приложением, а не библиотекой |
| 2026-11-12 | T03 | В промпт добавлено требование `[[tool.mypy.overrides]]` с `ignore_missing_imports` для `streamlit.*` и `plotly.*` | У этих пакетов нет type hints — mypy strict упадёт на новой точке входа и UI |
| 2026-11-12 | T15 | Уточнено, что интерфейс запускается через `worldsim` / `python -m worldsim`, а `streamlit run` остаётся отладочным | Учесть entry point, появившийся в T39 |
| 2026-11-12 | T02 | Промпт сохранён как исторический, добавлено примечание об отмене пункта про `py.typed` задачей T39 | Показать, что решение о библиотечном каркасе пересмотрено |
| 2026-11-12 | T09 | В `EventType` добавлены `STARVATION`, `RECRUITMENT`, `DESERTION`, `TECH_ADVANCE`, `PEACE_OFFER`, `PEACE_TREATY` | Новые события экономики фракции и дипломатии |
| 2026-11-12 | T16 | Модель фракции расширена: `culture`, `treasury`, `food_stockpile`, `tech_level`, `resources`, `army_size`, `morale`, вычисляемый `military_power`, `culture_conflict_factor` | Требование заказчика: параметры фракции для конфликтов, экономики и войны |
| 2026-11-12 | T18 | Генератор инициализирует культуру, казну, запасы еды, технологии, армию, мораль и ресурсы | Новые поля фракции нельзя оставлять пустыми |
| 2026-11-12 | T19 | Метрики дополнены экономикой фракции; `army_size` больше не выводится из населения | Численность армии стала состоянием, а не производной |
| 2026-11-12 | T20 | Экспансия учитывает `food_stockpile` и `military_power`, вес цели считается по боевой мощи | Голод — причина агрессии, сила защитника — критерий выбора |
| 2026-11-12 | T21 | Война сравнивает `military_power`, меняет потери, `morale` и казну, заводит записи войн | Требование: именно боевая мощь сравнивается в войне |
| 2026-11-12 | T22 | UI показывает культуру, казну, еду, технологии, армию, мощь и мораль | Новые параметры должны быть видны пользователю |
| 2026-11-12 | T23 | Проверяются новые инварианты и сценарии голода и мира; зависимости расширены на T40 и T41 | Интеграционные тесты должны покрывать новое поведение |
| 2026-11-12 | T34 | Конфликт культур считается через `culture_conflict_factor` и `Faction.culture` | Не дублировать логику конфликтов |
| 2026-11-12 | T36 | Торговля пополняет `resources` и `treasury` фракции | Ресурсы фракции должны откуда-то браться |
| 2026-11-12 | T40 | Новая задача: экономика фракции — снабжение, казна, армия, технологии | Требования «еда → голод», «казна → армия», «технологии» не покрывались задачами |
| 2026-11-12 | T41 | Новая задача: дипломатия — запрос мира и перемирие | Требование «мораль падает → запрос мира» требует модели войн |
| 2026-11-12 | T08 | Модель тайла расширена до 20 параметров; добавлены `ResourceType`, `ClimateZone`, вычисляемые `is_city`, `defense_multiplier()`, `food_output()` | Требование заказчика: параметры тайла и их влияние |
| 2026-11-12 | T09 | Добавлены события `RIOT`, `SECESSION`, `DEFECTION`, `CITY_RISE`, `RESOURCE_DEPLETED`, `OCCUPATION` | Новые социальные, ресурсные и военные события |
| 2026-11-12 | T12 | Генератор задаёт плодородие 0–100, высоту, реки, ресурсы с истощением, ёмкость и социальные показатели | Поля тайла нельзя оставлять пустыми |
| 2026-11-12 | T17 | `owner_id` перенесён в T08; добавлена валидация воды и присутствия армии | Поле объявлено раньше, чем появилась связь с фракциями |
| 2026-11-12 | T19 | Метрики считаются через `RegionData.food_output()` и агрегируют счастье, недовольство и города | Формула еды зависит от реки и инфраструктуры |
| 2026-11-12 | T20 | Выбор цели учитывает фортификацию, недовольство, высоту и гарнизон | Параметры тайла должны влиять на решения о войне |
| 2026-11-12 | T21 | Защита строится из гарнизона, фортификации и биома; добавлена оккупация | Требование заказчика: армия, фортификация и население тайла |
| 2026-11-12 | T22 | UI получил слои ресурсов, счастья, недовольства и армий, панель тайла | Пользователь должен видеть новые параметры |
| 2026-11-12 | T23 | Инварианты новых полей и сценарии города, отделения, истощения, оккупации | Покрыть новое поведение тестами |
| 2026-11-12 | T34 | Культура населения тайла и ассимиляция при оккупации | Требование: культура меняется медленно |
| 2026-11-12 | T36 | Добыча ресурсов из тайлов с истощением, бонусами инфраструктуры и рек | Один тайл — один главный ресурс |
| 2026-11-12 | T40 | Экономика опирается на `food_output()` тайлов | Единая формула производства еды |
| 2026-11-12 | T42 | Новая задача: социальная динамика тайлов (счастье, недовольство, урбанизация) | Требования «бунты», «отделение», «города» не покрывались задачами |
| 2026-11-12 | T43 | Новая задача: армии на карте, фронты и оккупация | Требование «army_presence для фронтов и оккупации» |
| 2026-11-12 | T08 | Добавлены `mana_density`, `mana_regeneration`, `ley_line` и проверки диапазонов | Требование заказчика: магические параметры тайла |
| 2026-11-12 | T09 | Добавлены события `ACADEMY_FOUNDED`, `MAGIC_BREAKTHROUGH`, `LEY_LINE_CLAIMED` | События магической экономики и войн за лей-линии |
| 2026-11-12 | T12 | Генератор задаёт плотность и регенерацию маны, расставляет узлы лей-линий | Лей-линии должны быть редкими и ценными |
| 2026-11-12 | T16 | Добавлены `MagicSchool`, `mana_pool`, `magic_affinity`, `magic_schools`, метод `magic_power()` | Требование заказчика: магические параметры фракции |
| 2026-11-12 | T18 | Стартовые `magic_affinity` и школы задаются культурой | Эльфы, гномы, орки и нежить различаются магией |
| 2026-11-12 | T19 | Метрики считают `mana_income`, `mana_density_avg` и захваченные лей-линии | Доход маны складывается из тайлов |
| 2026-11-12 | T21 | Боевая мощь умножается на магическую (`magic_power()`) | Маги должны усиливать армию |
| 2026-11-12 | T22 | Слой «Мана» и магические показатели в панели тайла | Новые параметры должны быть видны |
| 2026-11-12 | T23 | Проверяются инварианты маны и сценарий магической войны | Покрытие новой механики тестами |
| 2026-11-12 | T36 | Уточнено различие ресурса `MANA` и фоновой `mana_density` | Два разных понятия маны |
| 2026-11-12 | T40 | Добавлено накопление `mana_pool` из `mana_income` | Мана должна копиться |
| 2026-11-12 | T44 | Новая задача: магическая экономика, академии и школы | Требования «академии» и «рост магии» не покрывались задачами |
| 2026-11-12 | T45 | Новая задача: боевая магия, контршколы и расход маны | Требование «сила магов в бою» |
| 2026-11-12 | T03 | В конфигурацию ruff добавлено `ignore = ["RUF001", "RUF002", "RUF003"]` | Кириллица в docstrings ложно распознаётся как неоднозначные символы |
| 2026-11-23 | T10, T18 | `WorldConfig.initial_factions` по умолчанию 2 (по требованию T18), тест T10 обновлён | Мир по умолчанию должен создаваться с фракциями |

## Новые задачи, добавленные при декомпозиции

Задачи, которых не было в ТЗ явно, но без них ТЗ не выполнить:

| ID | Почему добавлена |
|----|------------------|
| T02, T03 | В репозитории нет `pyproject.toml`, src-layout и тестового каркаса — ТЗ описывает их как существующие |
| T04 | Требование «покрыто тестами и запускается» без CI проверяется вручную; CI нужен для регрессий |
| T07 | Принцип детерминизма из ТЗ требует единой точки случайности вместо `random` в каждом модуле |
| T13, T14 | ТЗ называет движок «в разработке», но правил роста и случайных событий в коде нет — их нужно переписать с нуля |
| T27 | Пункт ТЗ 2.4 подразумевает сравнение веток, но `diff` как операция не выделен |
| T37 | Требование фиксировать архитектурные решения в Obsidian нужно материализовать в ADR внутри репозитория |
| T38 | Детерминизм и иммутабельность на 256×256 требуют отдельного замера, иначе симуляция станет нерабочей |
| T39 | Тип продукта изменён на приложение: нужна точка входа `worldsim`, страница запуска и документация вместо библиотечных формулировок |
| T40 | Требования «запасы еды → голод», «казна → армия и строительство», «технологии» не покрывались ни одной задачей |
| T41 | Требование «мораль падает → фракция запрашивает мир» требует модели войн и перемирий |
| T42 | Требования «счастье → бунты», «недовольство → отделение», «урбанизация → город» не покрывались задачами |
| T43 | Требование «army_presence для фронтов и оккупации» требует перемещения армий и правил оккупации |
| T44 | Требования «академии на богатых маной тайлах» и «магические школы» не покрывались задачами |
| T45 | Требование «сила магов в бою» и контршколы требуют отдельного боевого правила |
