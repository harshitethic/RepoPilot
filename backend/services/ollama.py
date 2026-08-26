import os, requests
URL=os.getenv("OLLAMA_URL","http://127.0.0.1:11434")
MODEL=os.getenv("OLLAMA_MODEL","llama3.2:1b")
def tags():
    r=requests.get(f"{URL}/api/tags",timeout=5); r.raise_for_status(); return [m["name"] for m in r.json().get("models",[])]
def available():
    try:return {"online":True,"models":tags(),"selected":MODEL}
    except Exception as e:return {"online":False,"models":[],"selected":MODEL,"error":str(e)}
def chat(prompt,timeout=180):
    payload={"model":MODEL,"messages":[{"role":"system","content":"You are RepoPilot, a senior software engineer. Only make claims supported by the supplied repository context. Mention file paths when evidence exists. If context is insufficient, say so."},{"role":"user","content":prompt}],"stream":False,"options":{"temperature":0.2,"num_predict":700}}
    r=requests.post(f"{URL}/api/chat",json=payload,timeout=timeout); r.raise_for_status(); return r.json()["message"]["content"]
