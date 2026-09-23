from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from services.github import clone_repo,safe_repo_path,list_repositories,delete_repository,cleanup_repositories
from services.analyzer import analyze,search_code,build_context
from services.ollama import available,chat
from api_upload import router as upload_router
app=FastAPI(title="RepoPilot API")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_methods=["*"],allow_headers=["*"])
app.include_router(upload_router)
class Analyze(BaseModel): url:str=Field(min_length=10,max_length=500)
class RepoReq(BaseModel): repo_id:str
class Ask(RepoReq): question:str=Field(min_length=3,max_length=1200)
class Search(RepoReq): query:str=Field(min_length=1,max_length=100)
class Cleanup(BaseModel): max_age_hours:int=Field(default=24,ge=1,le=24*30)
@app.get("/api/health")
def health(): return {"ok":True,"ollama":available()}
@app.post("/api/analyze")
def do_analyze(x:Analyze):
    try:
        rid,path=clone_repo(x.url); d=analyze(path); d.update(repo_id=rid,source_url=x.url); return d
    except Exception as e: raise HTTPException(400,str(e))
@app.post("/api/search")
def do_search(x:Search):
    try:return {"results":search_code(safe_repo_path(x.repo_id),x.query)}
    except Exception as e:raise HTTPException(400,str(e))
def ai(repo_id,question,mode):
    path=safe_repo_path(repo_id); context=build_context(path,question,10 if mode=="architecture" else 8,20000)
    prompt=f"""Analyze this repository. The user request is: {question}
Use only the code context below.
{context}
Give a concise developer-facing answer. Cite actual file paths. Do not invent files or behavior."""
    return chat(prompt)
@app.post("/api/ask")
def do_ask(x:Ask):
    try:return {"answer":ai(x.repo_id,x.question,"ask")}
    except Exception as e:raise HTTPException(500,str(e))
@app.post("/api/architecture")
def arch(x:Ask):
    try:return {"answer":ai(x.repo_id,"Explain the architecture, components, entry points and request/data flow.","architecture")}
    except Exception as e:raise HTTPException(500,str(e))

@app.get("/api/repositories")
def repositories():
    rows=list_repositories()
    return {"repositories":rows,"count":len(rows)}

@app.delete("/api/repositories/{repo_id}")
def remove_repository(repo_id:str):
    try:
        delete_repository(repo_id)
        return {"repo_id":repo_id,"deleted":True}
    except (ValueError,FileNotFoundError) as e:
        raise HTTPException(404,str(e))

@app.post("/api/repositories/cleanup")
def cleanup(x:Cleanup):
    deleted=cleanup_repositories(x.max_age_hours)
    return {"deleted":deleted,"count":len(deleted),"max_age_hours":x.max_age_hours}
