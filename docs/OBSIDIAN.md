# Импорт ADR в Obsidian

ADR в `docs/adr/` — обычные Markdown-файлы с относительными ссылками. Их
можно открыть в Obsidian двумя способами.

## Вариант 1: открыть каталог `docs` как vault

1. В Obsidian выберите **Open folder as vault**.
2. Укажите каталог `docs/`.
3. В настройках **Files & Links**:
   - **New link format** → `Relative path to file`;
   - **Use [[Wikilinks]]** → выключено, чтобы сохранить markdown-ссылки;
   - **Automatically update internal links** → включено.
4. Откройте [ARCHITECTURE.md](ARCHITECTURE.md) — граф связей и ссылки на
   ADR в `adr/` подхватятся автоматически.

## Вариант 2: добавить ADR в существующий vault

1. Скопируйте каталог `docs/adr/` в vault, например в `WorldSim/adr/`.
2. Скопируйте [ARCHITECTURE.md](ARCHITECTURE.md) рядом с `adr/`, чтобы
   относительные ссылки `adr/0001-src-layout.md` продолжали работать.
3. Либо сделайте симлинк:
   ```bash
   # Linux / macOS
   ln -s "$(pwd)/docs/adr" "$HOME/vault/WorldSim/adr"
   ```
   На Windows используйте `mklink /D`.

## Полезное

- Mermaid-схема из `ARCHITECTURE.md` рендерится встроенным плагином
  Obsidian.
- Для наглядности добавьте теги вручную через свойства заметки:
  `adr`, `architecture`, `worldsim`.
- Если ADR обновляются через git, достаточно обновить каталог `docs/adr/`
  в vault — ссылки останутся прежними.
- Быстрая проверка ссылок и якорей: `python scripts/check_docs.py`.
