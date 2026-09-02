from pathlib import Path
from urllib.parse import urlparse
import re, shutil, subprocess, uuid, zipfile

BASE_DIR = Path(__file__).resolve().parents[1] / "repos"
BASE_DIR.mkdir(exist_ok=True)
ALLOWED_HOSTS = {"github.com", "www.github.com"}
SKIP_DIRS = {".git","node_modules",".venv","venv","__pycache__","dist","build",".next",".nuxt","coverage",".idea",".vscode"}
TEXT_EXTENSIONS = {".py",".js",".jsx",".ts",".tsx",".java",".go",".rs",".cpp",".c",".h",".hpp",".cs",".php",".rb",".swift",".kt",".kts",".sql",".html",".css",".scss",".sass",".less",".json",".yaml",".yml",".toml",".ini",".md",".txt",".xml",".sh",".ps1",".env.example"}
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_ZIP_FILES = 5000

def validate_github_url(url: str) -> str:
    p = urlparse(url.strip())
    if p.scheme not in {"http","https"} or p.hostname not in ALLOWED_HOSTS:
        raise ValueError("Only public github.com repository URLs are supported.")
    parts = p.path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError("Use https://github.com/owner/repository")
    owner, repo = parts[:2]
    repo = re.sub(r"\.git$", "", repo)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid GitHub repository URL.")
    return f"https://github.com/{owner}/{repo}.git"

def clone_repo(url: str):
    safe = validate_github_url(url)
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
    for p in root.rglob("*"):
        if not p.is_file(): continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts): continue
        try: size = p.stat().st_size
        except OSError: continue
        if size > 300_000: continue
        if p.suffix.lower() in TEXT_EXTENSIONS or p.name.lower() in {"dockerfile","makefile"}:
            yield p

def read_text(path: Path): return path.read_text(encoding="utf-8", errors="replace")

def safe_repo_path(repo_id: str):
    if not re.fullmatch(r"[a-f0-9]{12}", repo_id): raise ValueError("Invalid repository id.")
    path = (BASE_DIR / repo_id).resolve()
    if BASE_DIR.resolve() not in path.parents or not path.exists(): raise FileNotFoundError("Repository not found.")
    return path
