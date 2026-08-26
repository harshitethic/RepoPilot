from collections import Counter
from pathlib import Path
from .github import iter_files, read_text
LANG={".py":"Python",".js":"JavaScript",".jsx":"JavaScript",".ts":"TypeScript",".tsx":"TypeScript",".java":"Java",".go":"Go",".rs":"Rust",".cpp":"C++",".c":"C",".cs":"C#",".php":"PHP",".rb":"Ruby",".swift":"Swift",".kt":"Kotlin",".sql":"SQL",".html":"HTML",".css":"CSS",".scss":"SCSS",".json":"JSON",".yaml":"YAML",".yml":"YAML",".md":"Markdown",".sh":"Shell",".ps1":"PowerShell"}

def analyze(root):
    entries=[]; langs=Counter(); lines=0; bytes_=0
    for p in iter_files(root):
        rel=str(p.relative_to(root)).replace("\\","/")
        text=read_text(p); n=text.count("\n")+(1 if text else 0)
        lines+=n; bytes_+=p.stat().st_size; lang=LANG.get(p.suffix.lower(),"Other"); langs[lang]+=1
        entries.append({"path":rel,"size":p.stat().st_size,"lines":n,"language":lang})
    paths={e["path"].lower() for e in entries}; names={Path(e["path"]).name.lower() for e in entries}
    signals={
      "readme":any(n.startswith("readme") for n in names),
      "tests":any("/test" in p or p.startswith("test") or "/tests/" in p or p.startswith("tests/") for p in paths),
      "gitignore":".gitignore" in names,
      "manifest":any(n in names for n in ["package.json","requirements.txt","pyproject.toml","pom.xml","cargo.toml","go.mod","composer.json","gemfile"]),
      "ci":any(p.startswith(".github/workflows/") for p in paths),
      "docker":any(n in names for n in ["dockerfile","docker-compose.yml","compose.yml"])
    }
    score=40+12*signals["readme"]+10*signals["tests"]+8*signals["gitignore"]+8*signals["manifest"]+7*signals["ci"]+7*signals["docker"]
    warnings=[f"No {k} detected" for k,v in signals.items() if not v and k in {"readme","tests","gitignore","ci"}]
    return {"file_count":len(entries),"total_lines":lines,"total_bytes":bytes_,"languages":[{"name":k,"files":v} for k,v in langs.most_common()],"score":min(score,100),"signals":signals,"warnings":warnings,"files":sorted(entries,key=lambda x:x["path"].lower())}

def search_code(root,q,limit=50):
    q=q.lower().strip(); out=[]
    for p in iter_files(root):
        for i,line in enumerate(read_text(p).splitlines(),1):
            if q in line.lower():
                out.append({"path":str(p.relative_to(root)).replace("\\","/"),"line":i,"text":line.strip()[:300]})
                if len(out)>=limit:return out
    return out

def build_context(root,q,max_files=8,max_chars=18000):
    tokens={x for x in q.lower().replace("/"," ").replace("."," ").split() if len(x)>2}; ranked=[]
    for p in iter_files(root):
        text=read_text(p); rel=str(p.relative_to(root)).replace("\\","/")
        low=(rel+"\n"+text[:30000]).lower()
        score=sum(t in low for t in tokens)+sum(k in rel.lower() for k in ["readme","app.","main.","index.","route","api"])*2
        if score: ranked.append((score,rel,text))
    ranked.sort(reverse=True,key=lambda x:x[0]); out=""; used=0
    for _,rel,text in ranked[:max_files]:
        block=f"\n--- FILE: {rel} ---\n{text[:4000]}\n"
        if used+len(block)>max_chars: break
        out+=block; used+=len(block)
    return out or "No strongly matching files were found. Say that the supplied context is insufficient."
