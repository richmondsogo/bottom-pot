"""
Central Operational Database & Destructive-Cleanup Safety Guards.

Enforces the invariant that no automated test, E2E run, temporary server,
or cleanup routine may open, migrate, checkpoint, modify, or delete the
operational SQLite database (`data/cache.sqlite`), its sidecars, or its backups.

Fails closed on ambiguous, traversal, symlink/junction, hard-link, or URI inputs.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import stat as stat_mod
import sys
import tempfile
import threading
from typing import Iterator, Literal


REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_PROTECTED_DB_BASENAMES: frozenset[str] = frozenset({
    "cache.sqlite",
    "cache.sqlite-wal",
    "cache.sqlite-shm",
    "cache.sqlite-journal",
})
DOCUMENTED_OPERATIONAL_ENTRYPOINTS: frozenset[str] = frozenset({
    "src.api.main:lifespan",
    "src.monitoring.board_monitor:main",
    "src.monitoring.cache_repair.ashby:main",
    "src.monitoring.cache_repair.greenhouse:main",
    "src.monitoring.cache_repair.lever:main",
    "src.monitoring.cache_repair.workable:main",
})
_TRUTHY_FLAGS: frozenset[str] = frozenset({"1", "true", "yes", "on"})

_AUTH_LOCK = threading.RLock()
_OPERATIONAL_RUNTIME_AUTHORIZED_BY: str | None = None


class UnsafeDatabasePathError(ValueError):
    """Raised when a test, startup, or cleanup routine targets a protected or invalid DB path."""


def is_test_or_disposable_context() -> bool:
    """
    Return True when execution is inside an automated test, E2E, or CI context.

    Setting TESTING=true, CI=true, PYTEST_CURRENT_TEST, PLAYWRIGHT_*, or BOTTOM_POT_TEST_MODE
    always overrides operational opt-ins and rejects operational database targets.
    """
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        return True
    for var in ("PLAYWRIGHT_TEST", "PLAYWRIGHT_SQLITE_DB_PATH", "BOTTOM_POT_TEST_MODE"):
        if os.environ.get(var, "").strip():
            return True
    for flag_var in ("TESTING", "CI"):
        val = os.environ.get(flag_var, "").strip().lower()
        if val and val not in ("0", "false", "no", "off"):
            return True
    return False


def is_operational_env_enabled() -> bool:
    """Return True only when explicit non-.env opt-in BOTTOM_POT_ALLOW_OPERATIONAL_DB is truthy."""
    return os.environ.get("BOTTOM_POT_ALLOW_OPERATIONAL_DB", "").strip().lower() in _TRUTHY_FLAGS


def authorize_operational_runtime(entrypoint: str) -> None:
    """
    Grant in-process operational DB access from a documented production entrypoint.

    Always fails closed when automated test/E2E/CI flags are active, and validates
    ``entrypoint`` against ``DOCUMENTED_OPERATIONAL_ENTRYPOINTS`` to prevent
    accidental opt-in from arbitrary scripts. Note: this string allow-list is an
    in-process discipline guardrail against accidental misuse, not a cryptographic
    or adversarial OS security boundary.
    """
    global _OPERATIONAL_RUNTIME_AUTHORIZED_BY
    if is_test_or_disposable_context():
        raise UnsafeDatabasePathError(
            f"Cannot authorize operational database runtime ({entrypoint}) inside a test, E2E, or CI context."
        )
    clean_entrypoint = entrypoint.strip() if isinstance(entrypoint, str) else ""
    if not clean_entrypoint or clean_entrypoint not in DOCUMENTED_OPERATIONAL_ENTRYPOINTS:
        raise UnsafeDatabasePathError(
            f"Unauthorized operational runtime entrypoint {entrypoint!r}; "
            f"expected one of {sorted(DOCUMENTED_OPERATIONAL_ENTRYPOINTS)}."
        )
    with _AUTH_LOCK:
        _OPERATIONAL_RUNTIME_AUTHORIZED_BY = clean_entrypoint


def revoke_operational_runtime() -> None:
    """Revoke in-process operational database runtime authorization."""
    global _OPERATIONAL_RUNTIME_AUTHORIZED_BY
    with _AUTH_LOCK:
        _OPERATIONAL_RUNTIME_AUTHORIZED_BY = None


def is_operational_runtime_authorized() -> bool:
    """Return True iff operational runtime was explicitly granted and no test/CI flag is active."""
    if is_test_or_disposable_context():
        return False
    with _AUTH_LOCK:
        return _OPERATIONAL_RUNTIME_AUTHORIZED_BY is not None


@contextmanager
def operational_runtime_context(entrypoint: str) -> Iterator[None]:
    """Context manager granting and automatically revoking operational runtime authorization."""
    global _OPERATIONAL_RUNTIME_AUTHORIZED_BY
    with _AUTH_LOCK:
        previous = _OPERATIONAL_RUNTIME_AUTHORIZED_BY
    authorize_operational_runtime(entrypoint)
    try:
        yield
    finally:
        with _AUTH_LOCK:
            _OPERATIONAL_RUNTIME_AUTHORIZED_BY = previous


@contextmanager
def cli_operational_runtime(entrypoint: str, *, allow_operational_db: bool = False) -> Iterator[None]:
    """
    Scope operational DB runtime authorization for documented CLI entry points.

    If neither ``allow_operational_db`` nor ``BOTTOM_POT_ALLOW_OPERATIONAL_DB=1`` is active,
    no operational authorization is granted (non-operational temp paths still succeed).
    In any test/E2E/CI context, operational opt-ins fail closed.
    """
    if not allow_operational_db and not is_operational_env_enabled():
        yield
        return
    if is_test_or_disposable_context():
        raise UnsafeDatabasePathError(
            f"Cannot authorize operational CLI runtime ({entrypoint}) inside a test, E2E, or CI context."
        )
    had_env = "BOTTOM_POT_ALLOW_OPERATIONAL_DB" in os.environ
    prev_env = os.environ.get("BOTTOM_POT_ALLOW_OPERATIONAL_DB")
    if allow_operational_db and not is_operational_env_enabled():
        os.environ["BOTTOM_POT_ALLOW_OPERATIONAL_DB"] = "1"
    try:
        with operational_runtime_context(entrypoint):
            yield
    finally:
        if had_env and prev_env is not None:
            os.environ["BOTTOM_POT_ALLOW_OPERATIONAL_DB"] = prev_env
        elif not had_env:
            os.environ.pop("BOTTOM_POT_ALLOW_OPERATIONAL_DB", None)


def _is_reparse_or_link(candidate: Path) -> bool:
    if os.path.islink(candidate):
        return True
    is_junc = getattr(os.path, "isjunction", None)
    if callable(is_junc) and is_junc(candidate):
        return True
    try:
        st = os.lstat(candidate)
    except FileNotFoundError:
        return False
    except OSError:
        raise
    attrs = getattr(st, "st_file_attributes", 0)
    reparse_flag = getattr(stat_mod, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & reparse_flag)


def _read_link_target(candidate: Path) -> Path:
    raw = os.readlink(candidate)
    if sys.platform == "win32" and raw.startswith("\\\\?\\") and len(raw) > 6 and raw[5] == ":":
        raw = raw[4:]
    target = Path(raw)
    if target.is_absolute():
        return target
    return candidate.parent / target


def _resolve_preserving_tail(abs_path: Path) -> Path:
    tail: list[str] = []
    cur = abs_path
    while True:
        try:
            os.lstat(cur)
            break
        except FileNotFoundError:
            parent = cur.parent
            if parent == cur:
                return abs_path
            tail.insert(0, cur.name)
            cur = parent
    real_base = Path(os.path.realpath(cur))
    for seg in tail:
        real_base = real_base / seg
    return real_base


def resolve_canonical_path_following_links(
    raw_path: str | os.PathLike[str],
    *,
    base_dir: Path | None = None,
    max_hops: int = 40,
) -> Path:
    """Resolve symlinks/junctions (including dangling intermediate links) and '..' segments."""
    base = base_dir or Path.cwd()
    raw_str = os.fspath(raw_path)
    p = Path(raw_str)
    abs_initial = Path(os.path.abspath(p if p.is_absolute() else (base / p)))

    drive, tail = os.path.splitdrive(str(abs_initial))
    root_part = drive + (os.sep if tail.startswith(os.sep) or tail.startswith("/") else "")
    resolved = Path(root_part or os.sep)
    queue = [seg for seg in tail.replace("/", os.sep).split(os.sep) if seg]
    hops = 0

    while queue:
        seg = queue.pop(0)
        if seg == ".":
            continue
        if seg == "..":
            if resolved.parent != resolved:
                resolved = resolved.parent
            continue

        candidate = resolved / seg
        try:
            os.lstat(candidate)
        except FileNotFoundError:
            resolved = candidate
            continue

        if _is_reparse_or_link(candidate):
            hops += 1
            if hops > max_hops:
                raise UnsafeDatabasePathError(
                    f"Refusing path '{raw_str}': exceeded {max_hops} symlink/junction resolution hops."
                )
            next_target = Path(os.path.abspath(_read_link_target(candidate)))
            n_drive, n_tail = os.path.splitdrive(str(next_target))
            n_root = n_drive + (os.sep if n_tail.startswith(os.sep) or n_tail.startswith("/") else "")
            resolved = Path(n_root or os.sep)
            next_segs = [s for s in n_tail.replace("/", os.sep).split(os.sep) if s]
            queue = next_segs + queue
            continue

        resolved = candidate

    return _resolve_preserving_tail(resolved)


def _comparable(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _comparable_ci(path: Path) -> str:
    return os.path.normpath(str(path)).lower()


def _is_within_or_equal(candidate: Path, directory: Path) -> bool:
    try:
        return os.path.commonpath([_comparable(candidate), _comparable(directory)]) == _comparable(directory)
    except ValueError:
        return False


def _is_within_or_equal_ci(candidate: Path, directory: Path) -> bool:
    """Case-insensitive containment check used for operational lookalike defense on POSIX."""
    try:
        return os.path.commonpath([_comparable_ci(candidate), _comparable_ci(directory)]) == _comparable_ci(directory)
    except ValueError:
        return False


def _normalize_raw_variants(raw_str: str) -> list[str]:
    variants = [raw_str]
    if os.sep != "\\" and "\\" in raw_str:
        slash_variant = raw_str.replace("\\", "/")
        if slash_variant not in variants:
            variants.append(slash_variant)
    return variants


def _get_protected_roots(repo_root: Path | None) -> list[Path]:
    """Return protected repository roots; REPO_ROOT is ALWAYS included and cannot be disabled."""
    candidates: list[Path] = [REPO_ROOT]
    if repo_root is not None:
        candidates.append(repo_root)
    extra_raw = os.environ.get("BOTTOM_POT_TEST_EXTRA_PROTECTED_ROOT", "").strip()
    if extra_raw:
        candidates.append(Path(extra_raw))

    unique_roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = resolve_canonical_path_following_links(candidate, base_dir=REPO_ROOT)
        comp = _comparable(resolved)
        if comp not in seen:
            seen.add(comp)
            unique_roots.append(resolved)
    return unique_roots


def _collect_protected_info(repo_root: Path) -> tuple[Path, Path, set[str], set[str], list[tuple[int, int]], list[tuple[int, int]]]:
    data_dir = resolve_canonical_path_following_links(repo_root / "data", base_dir=repo_root)
    op_db = data_dir / "cache.sqlite"
    exact_paths: list[Path] = [
        data_dir / name for name in _PROTECTED_DB_BASENAMES
    ]
    exact_paths.append(resolve_canonical_path_following_links(repo_root / "subscriptions.csv", base_dir=repo_root))

    try:
        if data_dir.exists():
            for entry in data_dir.iterdir():
                exact_paths.append(resolve_canonical_path_following_links(entry, base_dir=repo_root))
    except OSError as exc:
        raise UnsafeDatabasePathError(f"Unable to inspect operational data directory '{data_dir}': {exc}") from exc

    comparable_set = {_comparable(p) for p in exact_paths}
    comparable_ci_set = {_comparable_ci(p) for p in exact_paths}
    all_identities: list[tuple[int, int]] = []
    backup_identities: list[tuple[int, int]] = []
    seen_identities: set[str] = set()
    for p in exact_paths:
        comp = _comparable(p)
        if comp in seen_identities:
            continue
        seen_identities.add(comp)
        try:
            st = os.stat(p)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UnsafeDatabasePathError(f"Unable to stat protected asset '{p}': {exc}") from exc
        if st.st_dev <= 0 or st.st_ino <= 0:
            raise UnsafeDatabasePathError(
                f"Protected asset '{p}' lacks reliable filesystem identity (dev/ino); failing closed."
            )
        pair = (st.st_dev, st.st_ino)
        all_identities.append(pair)
        low_name = p.name.lower()
        if low_name.startswith("cache.sqlite.bak-") or low_name.startswith(".cache.sqlite.restore-staging-"):
            backup_identities.append(pair)

    return data_dir, op_db, comparable_set, comparable_ci_set, all_identities, backup_identities


def _matches_protected_identity(candidate: Path, protected_identities: list[tuple[int, int]]) -> bool:
    if not protected_identities:
        return False
    try:
        st = os.stat(candidate)
    except FileNotFoundError:
        return False
    except OSError:
        return True  # fail closed
    if st.st_dev <= 0 or st.st_ino <= 0:
        return True  # cannot distinguish safely
    return (st.st_dev, st.st_ino) in protected_identities


def _is_protected_filename(name: str) -> bool:
    low = name.lower()
    return (
        low in _PROTECTED_DB_BASENAMES
        or low.startswith("cache.sqlite.bak-")
        or low.startswith(".cache.sqlite.restore-staging-")
    )


def validate_sqlite_db_path(
    raw_path: str | os.PathLike[str] | None,
    *,
    context: Literal["auto", "test", "production"] = "auto",
    operation: Literal["connect", "migrate", "checkpoint", "cleanup", "startup"] = "connect",
    repo_root: Path | None = None,
    enforce_env_test_guard: bool = True,
) -> str:
    """
    Validate a target SQLite database path and return its canonical path (or ':memory:').

    Fails closed when:
    - Any test/E2E/CI process targets operational data or backups.
    - Any unknown/unverified process (including scripts inheriting .env) targets operational
      data without explicit non-test operational opt-in + documented runtime entrypoint grant.
    - Any cleanup operation targets operational data, sidecars, or backups.
    - Any path resolves via symlink, directory junction, hard link, '..' traversal,
      cross-platform slash/case lookalike, or URI syntax into protected storage.
    """
    if raw_path is None or not isinstance(raw_path, (str, os.PathLike)):
        raise UnsafeDatabasePathError(
            f"SQLite path validation failed ({operation}): expected non-empty path, got {raw_path!r}."
        )

    raw_str = os.fspath(raw_path).strip()
    if not raw_str or "\0" in raw_str:
        raise UnsafeDatabasePathError(
            f"SQLite path validation failed ({operation}): empty or null-byte database path is forbidden."
        )

    low = raw_str.lower()
    if low == ":memory:":
        if operation == "cleanup":
            raise UnsafeDatabasePathError("Cannot perform filesystem cleanup on ':memory:' database.")
        return ":memory:"

    if low.startswith("file:") or raw_str.endswith(("/", "\\")):
        raise UnsafeDatabasePathError(
            f"SQLite path validation failed ({operation}): rejected URI or directory-like path {raw_str!r}."
        )

    protected_roots = _get_protected_roots(repo_root)
    real_repo_comp = _comparable(resolve_canonical_path_following_links(REPO_ROOT, base_dir=REPO_ROOT))
    protected_infos = [
        (root_item, _collect_protected_info(root_item))
        for root_item in protected_roots
    ]

    variants = _normalize_raw_variants(raw_str)
    resolved_primary: Path | None = None

    for variant in variants:
        bases = [Path.cwd(), *protected_roots] if not Path(variant).is_absolute() else [protected_roots[0]]
        for base in bases:
            resolved = resolve_canonical_path_following_links(variant, base_dir=base)
            if resolved_primary is None and variant == raw_str:
                resolved_primary = resolved

            try:
                if resolved.exists() and resolved.is_dir():
                    raise UnsafeDatabasePathError(
                        f"SQLite path validation failed ({operation}): target '{resolved}' is a directory."
                    )
            except UnsafeDatabasePathError:
                raise
            except OSError as exc:
                raise UnsafeDatabasePathError(
                    f"SQLite path validation failed ({operation}): cannot inspect '{resolved}': {exc}"
                ) from exc

            cand_comp = _comparable(resolved)
            cand_ci = _comparable_ci(resolved)

            for root_item, (data_dir, op_db, protected_exact, protected_exact_ci, protected_identities, backup_identities) in protected_infos:
                op_db_comp = _comparable(op_db)
                is_real_repo = (_comparable(root_item) == real_repo_comp)
                guard_active = enforce_env_test_guard or is_real_repo
                effective_test = (context == "test") or (is_test_or_disposable_context() if guard_active else False)

                is_in_data_dir = _is_within_or_equal(resolved, data_dir) or _is_within_or_equal_ci(resolved, data_dir)
                is_exact_protected = (cand_comp in protected_exact) or (cand_ci in protected_exact_ci)
                is_protected_name = _is_protected_filename(resolved.name)
                shares_protected_inode = _matches_protected_identity(resolved, protected_identities)
                shares_backup_inode = _matches_protected_identity(resolved, backup_identities)
                is_backup_or_staging = (
                    resolved.name.lower().startswith("cache.sqlite.bak-")
                    or resolved.name.lower().startswith(".cache.sqlite.restore-staging-")
                )

                if is_backup_or_staging or shares_backup_inode:
                    raise UnsafeDatabasePathError(
                        f"Invariant violation ({operation}): target '{resolved}' is or links to a protected backup/forensic artifact."
                    )

                if operation == "cleanup" and (
                    is_in_data_dir or is_exact_protected or is_protected_name or shares_protected_inode
                ):
                    raise UnsafeDatabasePathError(
                        f"Invariant violation (cleanup): refusing destructive cleanup of protected asset '{resolved}'."
                    )

                # Reject hard-link aliases pointing to operational assets regardless of context.
                if shares_protected_inode and cand_comp != op_db_comp:
                    raise UnsafeDatabasePathError(
                        f"Invariant violation ({operation}): target '{resolved}' shares filesystem identity (hard link) with a protected operational asset."
                    )

                if is_in_data_dir or is_exact_protected or shares_protected_inode:
                    if effective_test:
                        raise UnsafeDatabasePathError(
                            f"Invariant violation ({operation}): automated test/disposable execution cannot target operational path '{resolved}'. "
                            "Set SQLITE_DB_PATH to an isolated temporary directory."
                        )

                    if cand_comp != op_db_comp:
                        raise UnsafeDatabasePathError(
                            f"Invariant violation ({operation}): protected operational path '{resolved}' is not the canonical operational DB '{op_db}'."
                        )

                    if guard_active:
                        if not (is_operational_env_enabled() and is_operational_runtime_authorized()):
                            raise UnsafeDatabasePathError(
                                f"Operational DB access denied ({operation}): target '{resolved}' requires non-test execution, "
                                "BOTTOM_POT_ALLOW_OPERATIONAL_DB=1, and explicit documented runtime authorization."
                            )
                    else:
                        if context != "production" or not is_operational_env_enabled():
                            raise UnsafeDatabasePathError(
                                f"Operational DB access denied ({operation}): synthetic production check for '{resolved}' "
                                "requires context='production' and BOTTOM_POT_ALLOW_OPERATIONAL_DB=1."
                            )

    assert resolved_primary is not None
    return str(resolved_primary)


def assert_safe_sqlite_db_path(
    raw_path: str | os.PathLike[str] | None,
    *,
    context: Literal["auto", "test", "production"] = "auto",
    operation: Literal["connect", "migrate", "checkpoint", "cleanup", "startup"] = "connect",
    repo_root: Path | None = None,
) -> str:
    """Public guard enforcing fail-closed SQLite path safety."""
    return validate_sqlite_db_path(
        raw_path,
        context=context,
        operation=operation,
        repo_root=repo_root,
        enforce_env_test_guard=True,
    )


def assert_safe_subscriptions_path(
    raw_path: str | os.PathLike[str] | None,
    *,
    context: Literal["auto", "test", "production"] = "auto",
    repo_root: Path | None = None,
) -> str:
    """Reject unauthorized operational subscriptions.csv or data/ paths."""
    if raw_path is None or not isinstance(raw_path, (str, os.PathLike)):
        raise UnsafeDatabasePathError(f"Invalid subscriptions path: {raw_path!r}")
    raw_str = os.fspath(raw_path).strip()
    if not raw_str or "\0" in raw_str or raw_str.endswith(("/", "\\")):
        raise UnsafeDatabasePathError(f"Invalid subscriptions path: {raw_str!r}")

    protected_roots = _get_protected_roots(repo_root)
    protected_infos = [
        (
            root_item,
            _collect_protected_info(root_item),
            resolve_canonical_path_following_links(root_item / "subscriptions.csv", base_dir=root_item),
        )
        for root_item in protected_roots
    ]
    effective_test = (context == "test") or is_test_or_disposable_context()
    operational_authorized = (not effective_test) and is_operational_env_enabled() and is_operational_runtime_authorized()

    resolved_primary: Path | None = None
    for variant in _normalize_raw_variants(raw_str):
        bases = [Path.cwd(), *protected_roots] if not Path(variant).is_absolute() else [protected_roots[0]]
        for base in bases:
            resolved = resolve_canonical_path_following_links(variant, base_dir=base)
            if resolved_primary is None and variant == raw_str:
                resolved_primary = resolved
            for _, (data_dir, _, _, _, protected_identities, _), op_subs in protected_infos:
                in_data = _is_within_or_equal(resolved, data_dir) or _is_within_or_equal_ci(resolved, data_dir)
                is_op_subs = (_comparable(resolved) == _comparable(op_subs)) or (_comparable_ci(resolved) == _comparable_ci(op_subs))
                shares_id = _matches_protected_identity(resolved, protected_identities)
                if shares_id and not is_op_subs:
                    raise UnsafeDatabasePathError(
                        f"Invariant violation (subscriptions): '{resolved}' shares filesystem identity with a protected operational file."
                    )
                if in_data or is_op_subs or shares_id:
                    if effective_test:
                        raise UnsafeDatabasePathError(
                            f"Invariant violation (subscriptions): automated test execution cannot target '{resolved}'."
                        )
                    if in_data or not is_op_subs or not operational_authorized:
                        raise UnsafeDatabasePathError(
                            f"Invariant violation (subscriptions): unauthorized access to operational '{resolved}'."
                        )
    assert resolved_primary is not None
    return str(resolved_primary)


def safe_cleanup_disposable_path(
    target_path: str | os.PathLike[str],
    *,
    owned_root: str | os.PathLike[str],
    repo_root: Path | None = None,
) -> bool:
    """
    Delete a disposable file or subdirectory ONLY after verifying explicit workspace
    ownership under ``owned_root`` and confirming zero protected operational overlap.
    Unconditionally rejects protected operational assets regardless of context or flags.
    """
    protected_roots = _get_protected_roots(repo_root)
    protected_bundles = [
        (
            resolve_canonical_path_following_links(r, base_dir=r),
            _collect_protected_info(r),
        )
        for r in protected_roots
    ]

    owned_dir = resolve_canonical_path_following_links(owned_root, base_dir=Path.cwd())
    for resolved_repo, (data_dir, _, _, _, _, _) in protected_bundles:
        if (
            _is_within_or_equal(owned_dir, data_dir)
            or _is_within_or_equal_ci(owned_dir, data_dir)
            or _comparable(owned_dir) == _comparable(resolved_repo)
        ):
            raise UnsafeDatabasePathError(
                f"Invariant violation (cleanup): owned_root '{owned_dir}' cannot be inside repository/operational data."
            )
    if _is_reparse_or_link(owned_dir) or not owned_dir.is_dir():
        raise UnsafeDatabasePathError(
            f"Invariant violation (cleanup): owned_root '{owned_dir}' must be an existing physical directory."
        )

    target_raw = Path(os.fspath(target_path))
    target_abs = Path(os.path.abspath(target_raw if target_raw.is_absolute() else Path.cwd() / target_raw))
    target_resolved = resolve_canonical_path_following_links(target_abs, base_dir=Path.cwd())

    if _comparable(target_resolved) == _comparable(owned_dir):
        raise UnsafeDatabasePathError(
            f"Invariant violation (cleanup): use workspace.cleanup() rather than unlinking owned_root '{owned_dir}' directly."
        )
    if not _is_within_or_equal(target_resolved, owned_dir) or not _is_within_or_equal(target_abs, owned_dir):
        raise UnsafeDatabasePathError(
            f"Invariant violation (cleanup): target '{target_abs}' (resolved '{target_resolved}') is outside owned workspace '{owned_dir}'."
        )

    for _, (data_dir, _, protected_exact, protected_exact_ci, protected_identities, _) in protected_bundles:
        if (
            _is_within_or_equal(target_resolved, data_dir)
            or _is_within_or_equal_ci(target_resolved, data_dir)
            or _comparable(target_resolved) in protected_exact
            or _comparable_ci(target_resolved) in protected_exact_ci
            or _is_protected_filename(target_resolved.name)
            or _matches_protected_identity(target_resolved, protected_identities)
        ):
            raise UnsafeDatabasePathError(
                f"Invariant violation (cleanup): refusing cleanup of protected path '{target_resolved}'."
            )

    if not target_abs.exists() and not _is_reparse_or_link(target_abs):
        return False

    if target_abs.is_dir() and not _is_reparse_or_link(target_abs):
        shutil.rmtree(target_abs)
    else:
        target_abs.unlink()
    return True


@dataclass
class OwnedDisposableWorkspace:
    """Explicitly owned temporary workspace for disposable test SQLite DBs."""

    root: Path
    db_path: Path
    subscriptions_file: Path

    @classmethod
    def create(cls, prefix: str = "bottom-pot-test-") -> OwnedDisposableWorkspace:
        raw_dir = tempfile.mkdtemp(prefix=prefix)
        resolved = resolve_canonical_path_following_links(raw_dir)
        for prot_root in _get_protected_roots(None):
            data_dir, _, _, _, _, _ = _collect_protected_info(prot_root)
            if _is_within_or_equal(resolved, data_dir) or _is_within_or_equal_ci(resolved, data_dir):
                raise UnsafeDatabasePathError(
                    f"Invariant violation: disposable workspace '{resolved}' resolved inside operational data directory '{data_dir}'."
                )
        db_file = Path(assert_safe_sqlite_db_path(resolved / "test_cache.sqlite", context="test"))
        sub_file = Path(assert_safe_subscriptions_path(resolved / "test_subscriptions.csv", context="test"))
        return cls(root=resolved, db_path=db_file, subscriptions_file=sub_file)

    def cleanup(self) -> None:
        if not self.root.exists():
            return
        resolved = resolve_canonical_path_following_links(self.root)
        for prot_root in _get_protected_roots(None):
            data_dir, _, _, _, _, _ = _collect_protected_info(prot_root)
            if _is_within_or_equal(resolved, data_dir) or _is_within_or_equal_ci(resolved, data_dir) or _is_reparse_or_link(self.root):
                raise UnsafeDatabasePathError(
                    f"Invariant violation (cleanup): refusing to remove unsafe workspace '{self.root}'."
                )
        shutil.rmtree(self.root, ignore_errors=True)
