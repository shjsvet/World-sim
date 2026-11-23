"""UI-обёртки над репозиторием версий (без Streamlit)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from worldsim.core.chronicle import Chronicle
from worldsim.core.state import WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules import Rule
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.vcs.commit import Commit
from worldsim.vcs.diff import Diff
from worldsim.vcs.repo import WorldRepo

DEFAULT_REPO_DIR = ".worldsim"


def default_repo_path(root: Path | None = None) -> Path:
    """Путь к репозиторию по умолчанию: ``<корень>/.worldsim``."""
    base = Path.cwd() if root is None else Path(root)
    return base / DEFAULT_REPO_DIR


def open_repo(root: Path | None = None) -> WorldRepo:
    """Открывает (или создаёт при первом обращении) репозиторий."""
    return WorldRepo(default_repo_path(root))


def commit_history(repo: WorldRepo) -> list[Commit]:
    """Возвращает коммиты от HEAD к корню."""
    return repo.log()


def checkout_snapshot(repo: WorldRepo, ref: str) -> tuple[WorldState, Chronicle]:
    """Восстанавливает снимок и летопись по ссылке."""
    return repo.checkout(ref)


def diff_to_parent(repo: WorldRepo, commit: Commit) -> Diff:
    """Считает diff коммита к его родителю (или пустой для корня)."""
    if commit.parent_id is None:
        return Diff(years=(commit.year, commit.year))
    return repo.diff(commit.parent_id, commit.id)


def commit_world(
    repo: WorldRepo,
    state: WorldState,
    chronicle: Chronicle,
    message: str,
    branch: str = "main",
) -> Commit:
    """Коммитит текущее состояние мира."""
    return repo.commit(state, message, branch=branch, chronicle=chronicle)


def run_alternative(
    repo: WorldRepo,
    from_ref: str,
    branch: str,
    *,
    aggression: float | None = None,
    growth_rate: float | None = None,
    years: int = 50,
    rules: Sequence[Rule] | None = None,
    chronicle: Chronicle | None = None,
    message: str | None = None,
) -> tuple[Commit, Diff]:
    """Создаёт альтернативную реальность из снимка.

    Меняет выбранные параметры конфигурации, прогоняет мир на ``years`` лет
    в новой ветке и возвращает коммит с diff к родителю.
    """
    state, _ = repo.checkout(from_ref)
    changes: dict[str, object] = {}
    if aggression is not None:
        changes["aggression"] = aggression
    if growth_rate is not None:
        changes["growth_rate"] = growth_rate
    alt_state = state.evolve(config=state.config.evolve(**changes))

    history = chronicle if chronicle is not None else Chronicle()
    chosen_rules = list(rules) if rules is not None else [PopulationGrowthRule()]
    engine = SimulationEngine(chosen_rules, history, initial_state=alt_state)
    final_state = engine.run(years)

    commit_message = message or f"alt: {branch}"
    commit = repo.commit(
        final_state,
        commit_message,
        branch=branch,
        chronicle=history,
    )
    return commit, diff_to_parent(repo, commit)
