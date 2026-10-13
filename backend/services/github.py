from pathlib import Path
from urllib.parse import urlparse
import os, re, shutil, subprocess, uuid, zipfile
from datetime import datetime, timezone

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


def ensure_repository_capacity() -> None:
    count = len(repository_ids())
    limit = configured_repository_limit()
    if count >= limit:
        raise ValueError(
            f"Repository capacity reached ({count}/{limit}). "
            "Delete an old import or preview cleanup before adding another repository."
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
    output = []
    for repo_id in repository_ids():
        try:
            output.append(repository_summary(repo_id))
        except (OSError, FileNotFoundError, ValueError):
            continue
    return sorted(output, key=lambda item: item["updated_at"], reverse=True)


def delete_repository(repo_id: str) -> None:
    path = safe_repo_path(repo_id)
    shutil.rmtree(path)


def cleanup_repositories(max_age_hours: int, *, dry_run: bool = True, now: datetime | None = None) -> dict[str, list[str]]:
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
                delete_repository(repo_id)
                result["deleted"].append(repo_id)
        except (OSError, FileNotFoundError, ValueError):
            continue
    for ids in result.values():
        ids.sort()
    return result


def validate_github_url(url: str) -> str:
    p = urlparse(url.strip())
    if p.scheme not in {"http","https"} or p.hostname not in ALLOWED_HOSTS:
        raise ValueError("Only public github.com repository URLs are supported.")
    parts = p.path.strip("/").split("/")
    if len(parts) != 2:
        raise ValueError("Use https://github.com/owner/repository")
    owner, repo = parts[:2]
    repo = re.sub(r"\.git$", "", repo)
    if owner in {".", ".."} or repo in {".", ".."}:
        raise ValueError("Invalid GitHub repository URL.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid GitHub repository URL.")
    return f"https://github.com/{owner}/{repo}.git"

def clone_repo(url: str):
    safe = validate_github_url(url)
    ensure_repository_capacity()
    repo_id = uuid.uuid4().hex[:12]
    dest = BASE_DIR / repo_id
    try:
        r = subprocess.run(["git","clone","--depth","1","--quiet",safe,str(dest)], capture_output=True, text=True, timeout=90)
    except FileNotFoundError:
        raise RuntimeError("Git is not installed or not available on PATH.")
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest, ignore_errors=True); raise RuntimeError("Git clone timed out.")
    if r.returncode:
        shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError((r.stderr or "Git clone failed.").strip()[-500:])
    return repo_id, dest

def extract_zip(upload_path: Path):
    ensure_repository_capacity()
    if upload_path.stat().st_size > MAX_ZIP_BYTES:
        raise ValueError("ZIP is too large. Maximum upload size is 50 MB.")
    repo_id = uuid.uuid4().hex[:12]
    dest = BASE_DIR / repo_id
    total = 0
    try:
        with zipfile.ZipFile(upload_path) as archive:
            infos = [i for i in archive.infolist() if not i.is_dir()]
            if len(infos) > MAX_ZIP_FILES:
                raise ValueError("ZIP contains too many files. Maximum is 5,000 files.")
            root = dest.resolve()
            for info in infos:
                member = Path(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise ValueError("ZIP contains an unsafe file path.")
                total += info.file_size
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise ValueError("ZIP expands beyond the 200 MB limit.")
            for info in infos:
                target = (dest / Path(info.filename)).resolve()
                if root not in target.parents:
                    raise ValueError("ZIP contains an unsafe file path.")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out, length=1024 * 1024)
    except zipfile.BadZipFile:
        shutil.rmtree(dest, ignore_errors=True)
        raise ValueError("Invalid ZIP archive.")
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    return repo_id, dest

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
        if p.suffix.lower() in TEXT_EXTENSIONS or p.name.lower() in {"dockerfile","makefile",".gitignore"}:
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
