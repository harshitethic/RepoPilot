from pathlib import Path
import stat
import unicodedata
from urllib.parse import urlparse
import os, re, shutil, subprocess, uuid, zipfile
from datetime import datetime, timezone
from filelock import FileLock
from services.clone_process import run_guarded_git

BASE_DIR = Path(__file__).resolve().parents[1] / "repos"
BASE_DIR.mkdir(exist_ok=True)
ALLOWED_HOSTS = {"github.com", "www.github.com"}
SKIP_DIRS = {".git","node_modules",".venv","venv","__pycache__","dist","build",".next",".nuxt","coverage",".idea",".vscode"}
TEXT_EXTENSIONS = {".py",".js",".jsx",".ts",".tsx",".java",".go",".rs",".cpp",".c",".h",".hpp",".cs",".php",".rb",".swift",".kt",".kts",".sql",".html",".css",".scss",".sass",".less",".json",".yaml",".yml",".toml",".ini",".md",".txt",".xml",".sh",".ps1",".env.example"}
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_ZIP_FILES = 5000


def configured_repository_limit() -> int:
    raw = os.getenv("REPOPILOT_MAX_REPOSITORIES", "100")
    try:
        limit = int(raw)
    except ValueError as exc:
        raise ValueError("REPOPILOT_MAX_REPOSITORIES must be an integer") from exc
    if not 1 <= limit <= 10000:
        raise ValueError("REPOPILOT_MAX_REPOSITORIES must be between 1 and 10000")
    return limit


def configured_storage_limit() -> int:
    """Logical on-disk import budget, including cloned .git metadata."""
    raw = os.getenv("REPOPILOT_MAX_STORAGE_BYTES", str(2 * 1024**3))
    try:
        limit = int(raw)
    except ValueError as exc:
        raise ValueError("REPOPILOT_MAX_STORAGE_BYTES must be an integer") from exc
    if not 1 <= limit <= 1024**4:
        raise ValueError("REPOPILOT_MAX_STORAGE_BYTES must be between 1 byte and 1 TiB")
    return limit


def import_lock() -> FileLock:
    """Serialize admission and completion across threads and API processes.

    Lock lives beside, not inside, the repository store. This permits tests
    and read-only enumeration to ignore the lock file. It must not be removed
    while services are using this storage directory.
    """
    return FileLock(str(BASE_DIR.parent / f".{BASE_DIR.name}.import.lock"), timeout=120)


def directory_bytes(path: Path) -> int:
    """Fail closed on unreadable files and never traverse symlink targets."""
    root = path.resolve()
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_symlink() or not item.is_file():
                continue
            if not item.resolve().is_relative_to(root):
                raise ValueError("Repository contains a file outside its storage directory.")
            total += item.stat().st_size
    except OSError as exc:
        raise ValueError("Unable to inspect repository storage usage.") from exc
    return total


def stored_repository_bytes() -> int:
    try:
        return sum(directory_bytes(safe_repo_path(repo_id)) for repo_id in repository_ids())
    except OSError as exc:
        raise ValueError("Unable to inspect repository storage usage.") from exc


def repository_ids() -> list[str]:
    """List direct non-symlink repository imports only."""
    root = BASE_DIR.resolve()
    if not root.is_dir():
        return []
    result = []
    for entry in root.iterdir():
        if not re.fullmatch(r"[a-f0-9]{12}", entry.name) or entry.is_symlink():
            continue
        if entry.is_dir() and entry.resolve().parent == root:
            result.append(entry.name)
    return sorted(result)


def ensure_repository_capacity(*, planned_bytes: int = 0) -> None:
    """Call with import_lock held before reserving a new workspace."""
    count = len(repository_ids())
    limit = configured_repository_limit()
    if count >= limit:
        raise ValueError(
            f"Repository capacity reached ({count}/{limit}). "
            "Delete an old import or preview cleanup before adding another repository."
        )
    maximum = configured_storage_limit()
    used = stored_repository_bytes()
    if used + max(planned_bytes, 1) > maximum:
        raise ValueError(
            "Repository storage capacity reached. "
            "Delete an old import or raise REPOPILOT_MAX_STORAGE_BYTES."
        )


def repository_summary(repo_id: str) -> dict:
    path = safe_repo_path(repo_id)
    bytes_used = 0
    files = 0
    for candidate in path.rglob("*"):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        if not candidate.resolve().is_relative_to(path):
            continue
        try:
            bytes_used += candidate.stat().st_size
            files += 1
        except OSError:
            continue
    return {
        "repo_id": repo_id,
        "file_count": files,
        "total_bytes": bytes_used,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
    }


def list_repositories() -> list[dict]:
    with import_lock():
        return _list_repositories_locked()


def _list_repositories_locked() -> list[dict]:
    output = []
    for repo_id in repository_ids():
        try:
            output.append(repository_summary(repo_id))
        except (OSError, FileNotFoundError, ValueError):
            continue
    return sorted(output, key=lambda item: item["updated_at"], reverse=True)


def delete_repository(repo_id: str) -> None:
    with import_lock():
        _delete_repository_locked(repo_id)


def _delete_repository_locked(repo_id: str) -> None:
    path = safe_repo_path(repo_id)
    shutil.rmtree(path)


def rollback_import(repo_id: str, expected_path: Path) -> None:
    """Discard only this request's successfully reserved, uncommitted import.

    Verify both the ID and exact returned workspace before removal. The
    import lock serializes this cleanup with admission and explicit deletion.
    """
    with import_lock():
        path = safe_repo_path(repo_id)
        if (
            expected_path.is_symlink()
            or expected_path.name != repo_id
            or path.resolve() != expected_path.resolve()
        ):
            raise ValueError("Refusing to roll back an unrelated repository.")
        shutil.rmtree(path)


def cleanup_repositories(max_age_hours: int, *, dry_run: bool = True, now: datetime | None = None) -> dict[str, list[str]]:
    with import_lock():
        return _cleanup_repositories_locked(max_age_hours, dry_run=dry_run, now=now)


def _cleanup_repositories_locked(max_age_hours: int, *, dry_run: bool = True, now: datetime | None = None) -> dict[str, list[str]]:
    if not 1 <= max_age_hours <= 720:
        raise ValueError("max_age_hours must be between 1 and 720")
    current = now or datetime.now(timezone.utc)
    cutoff = current.timestamp() - max_age_hours * 3600
    result: dict[str, list[str]] = {"candidates": [], "deleted": []}
    for repo_id in repository_ids():
        try:
            path = safe_repo_path(repo_id)
            if path.stat().st_mtime >= cutoff:
                continue
            result["candidates"].append(repo_id)
            if not dry_run:
                _delete_repository_locked(repo_id)
                result["deleted"].append(repo_id)
        except (OSError, FileNotFoundError, ValueError):
            continue
    for ids in result.values():
        ids.sort()
    return result


def validate_github_url(url: str) -> str:
    """Canonicalize a public GitHub repo without credentials or URL extras.

    Git takes its input from the canonical HTTPS URL only. In particular,
    do not accidentally accept the local Git credential/port/query syntax.
    """
    try:
        parsed = urlparse(url.strip())
        # Accessing .port intentionally validates malformed port syntax too.
        port = parsed.port
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid GitHub repository URL.") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.params
    ):
        raise ValueError("Only credential-free HTTPS github.com repository URLs are supported.")
    if parsed.path.endswith("/") or "//" in parsed.path:
        raise ValueError("Invalid GitHub repository path separators.")
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2:
        raise ValueError("Use https://github.com/owner/repository")
    owner, repo = parts
    repo = repo.removesuffix(".git")
    if (
        not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner)
        or not 1 <= len(repo) <= 100
        or repo in {".", ".."}
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo)
    ):
        raise ValueError("Invalid GitHub repository URL.")
    return f"https://github.com/{owner}/{repo}.git"


def safe_clone_environment() -> dict[str, str]:
    """Never inherit a user's Git config overrides or interactive helpers.

    Git can rewrite HTTPS remotes via insteadOf, or spawn configured
    credential/filter helpers. A cloned repository is an untrusted input.
    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith(("GIT_", "SSH_", "LD_", "DYLD_"))
        and name.upper() not in {"PYTHONPATH", "PYTHONSTARTUP", "HOME"}
    }
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GIT_ASKPASS"] = os.devnull
    return environment


def reserve_repository_directory() -> tuple[str, Path]:
    """Atomically reserve a random ID; never overwrite or delete collisions."""
    for _ in range(20):
        repo_id = uuid.uuid4().hex[:12]
        dest = BASE_DIR / repo_id
        try:
            dest.mkdir(mode=0o700)
            return repo_id, dest
        except FileExistsError:
            continue
    raise RuntimeError("Unable to reserve a unique repository ID.")


def clone_repo(url: str):
    """Serialize admission and clone completion to enforce persistent quotas."""
    with import_lock():
        return _clone_repo_locked(url)


def _clone_repo_locked(url: str):
    safe = validate_github_url(url)
    ensure_repository_capacity()
    repo_id, dest = reserve_repository_directory()
    argv = [
        "git",
        "-c", f"core.hooksPath={os.devnull}",
        "-c", "core.fsmonitor=false",
        "-c", "credential.helper=",
        "-c", "protocol.file.allow=never",
        "-c", "protocol.ext.allow=never",
        "-c", "http.followRedirects=false",
        "clone", "--depth", "1", "--quiet", "--no-local",
        "--", safe, str(dest),
    ]
    success = False
    try:
        completed = run_guarded_git(
            argv, cwd=BASE_DIR, timeout=90, env=safe_clone_environment()
        )
        if completed.returncode:
            raise RuntimeError("GitHub repository clone failed.")
        # Git's fetched size is unknown in advance. Reject/roll back the new
        # workspace if the resulting persistent store exceeds the budget.
        if stored_repository_bytes() > configured_storage_limit():
            raise ValueError("Repository storage capacity reached after clone.")
        success = True
        return repo_id, dest
    except FileNotFoundError as exc:
        raise RuntimeError("Git is not installed or not available on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("GitHub repository clone timed out.") from exc
    finally:
        # The only directory we ever remove is the one this invocation
        # atomically reserved. Preexisting imports survive an ID collision.
        if not success:
            shutil.rmtree(dest, ignore_errors=True)


def _validated_zip_members(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, tuple[str, ...]]]:
    """Preflight a ZIP's paths without creating any files or directories.

    Reject ambiguous paths on both case-sensitive and case-insensitive
    filesystems, and refuse archive-defined symlink/special-file types.
    """
    infos = archive.infolist()
    if len(infos) > MAX_ZIP_FILES:
        raise ValueError("ZIP contains too many entries. Maximum is 5,000.")
    files: set[str] = set()
    directories: set[str] = set()
    seen_entries: set[str] = set()
    result: list[tuple[zipfile.ZipInfo, tuple[str, ...]]] = []
    total = 0
    reserved_windows = {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}
    for info in infos:
        name = info.filename
        if not name or len(name) > 4096 or name.startswith("/") or "\x00" in name or "\\" in name:
            raise ValueError("ZIP contains an unsafe file path.")
        raw = name[:-1] if info.is_dir() else name
        parts = raw.split("/")
        if not parts or len(parts) > 32 or any(
            not part or part in {".", ".."} or len(part) > 255
            or part[-1] in {".", " "}
            or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
            or part.split(".")[0].upper() in reserved_windows
            for part in parts
        ):
            raise ValueError("ZIP contains an unsafe file path.")
        if info.flag_bits & 0x1:
            raise ValueError("Encrypted ZIP members are not supported.")
        if info.create_system == 3:
            entry_type = stat.S_IFMT(info.external_attr >> 16)
            if entry_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ValueError("ZIP contains an unsafe symlink or special file.")
            if entry_type and (entry_type == stat.S_IFDIR) != info.is_dir():
                raise ValueError("ZIP contains an unsafe file/directory type.")
        keys = [
            unicodedata.normalize("NFC", "/".join(parts[:index])).casefold()
            for index in range(1, len(parts) + 1)
        ]
        key = keys[-1]
        if key in seen_entries or any(prefix in files for prefix in keys[:-1]):
            raise ValueError("ZIP contains duplicate or conflicting file paths.")
        if info.is_dir():
            if key in files:
                raise ValueError("ZIP contains conflicting file/directory paths.")
        else:
            if key in files or key in directories:
                raise ValueError("ZIP contains duplicate or conflicting file paths.")
            total += info.file_size
            if total > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("ZIP expands beyond the 200 MB limit.")
            files.add(key)
            result.append((info, tuple(parts)))
        seen_entries.add(key)
        directories.update(keys[:-1])
        if info.is_dir():
            directories.add(key)
    return result


def extract_zip(upload_path: Path):
    """Serialize admission and extraction to enforce persistent quotas."""
    with import_lock():
        return _extract_zip_locked(upload_path)


def _extract_zip_locked(upload_path: Path):
    """Extract a validated ZIP without overwriting existing import workspaces."""
    if upload_path.stat().st_size > MAX_ZIP_BYTES:
        raise ValueError("ZIP is too large. Maximum upload size is 50 MB.")
    dest: Path | None = None
    success = False
    try:
        with zipfile.ZipFile(upload_path) as archive:
            members = _validated_zip_members(archive)
            ensure_repository_capacity(planned_bytes=sum(info.file_size for info, _ in members))
            repo_id, dest = reserve_repository_directory()
            total = 0
            for info, parts in members:
                target = dest.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                # "xb" refuses overwrites even if another member/path was
                # accidentally missed by the preflight collision detection.
                with archive.open(info) as source, target.open("xb") as output:
                    while chunk := source.read(64 * 1024):
                        written += len(chunk)
                        total += len(chunk)
                        if written > info.file_size or total > MAX_UNCOMPRESSED_BYTES:
                            raise ValueError("ZIP expands beyond the 200 MB limit.")
                        output.write(chunk)
        if stored_repository_bytes() > configured_storage_limit():
            raise ValueError("Repository storage capacity reached after ZIP extraction.")
        success = True
        return repo_id, dest
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid ZIP archive.") from exc
    finally:
        # Never remove a path that this invocation did not reserve.
        if not success and dest is not None:
            shutil.rmtree(dest, ignore_errors=True)


def iter_files(root: Path):
    # Never follow a repository-controlled symbolic link outside its tree.
    trusted_root = root.resolve()
    for p in root.rglob("*"):
        if p.is_symlink() or not p.is_file(): continue
        if trusted_root not in p.resolve().parents: continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts): continue
        try: size = p.stat().st_size
        except OSError: continue
        if size > 300_000: continue
        if p.suffix.lower() in TEXT_EXTENSIONS or p.name.lower().endswith(".env.example") or p.name.lower() in {"dockerfile","makefile",".gitignore"}:
            yield p

def read_text(path: Path): return path.read_text(encoding="utf-8", errors="replace")

def safe_repo_path(repo_id: str):
    if not re.fullmatch(r"[a-f0-9]{12}", repo_id):
        raise ValueError("Invalid repository id.")
    root = BASE_DIR.resolve()
    candidate = root / repo_id
    if candidate.is_symlink():
        raise ValueError("Repository symlinks are not supported.")
    if not candidate.is_dir() or candidate.resolve().parent != root:
        raise FileNotFoundError("Repository not found.")
    return candidate
