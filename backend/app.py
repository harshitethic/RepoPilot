from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from services.github import clone_repo,safe_repo_path
from services.analyzer import analyze,search_code,build_context
from services.ollama import available,chat
app=FastAPI(title="RepoPilot API")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_methods=["*"],allow_headers=["*"])
class Analyze(BaseModel): url:str=Field(min_length=10,max_length=500)
class RepoReq(BaseModel): repo_id:str
class Ask(RepoReq): question:str=Field(min_length=3,max_length=1200)
class Search(RepoReq): query:str=Field(min_length=1,max_length=100)
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
