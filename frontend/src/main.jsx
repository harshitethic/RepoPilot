import React,{useEffect,useRef,useState}from"react";import{createRoot}from"react-dom/client";import{Activity,AlertTriangle,Bot,CheckCircle2,ChevronRight,Code2,FileCode2,Github,HeartPulse,Loader2,Moon,Search,Send,Sparkles,Sun,Terminal,TreePine,Upload,X}from"lucide-react";import"./styles.css";import{ollamaAvailable}from"./health.js";
const api=async(p,o={})=>{const r=await fetch(p,{headers:{"Content-Type":"application/json",...(o.headers||{})},...o}),d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||"Request failed");return d};
function App(){const[dark,setDark]=useState(localStorage.getItem("rp-dark")==="1"),[url,setUrl]=useState(""),[repo,setRepo]=useState(null),[health,setHealth]=useState(null),[loading,setLoading]=useState(false),[error,setError]=useState(""),[tab,setTab]=useState("overview"),[query,setQuery]=useState(""),[results,setResults]=useState([]),[question,setQuestion]=useState(""),[answer,setAnswer]=useState(""),[asking,setAsking]=useState(false),[arch,setArch]=useState(""),[archLoading,setArchLoading]=useState(false),[uploadName,setUploadName]=useState("");
const sessionId=useRef(0),importId=useRef(0),searchId=useRef(0),answerId=useRef(0),architectureId=useRef(0);
function clearRepoScopedState(){
  sessionId.current++;searchId.current++;answerId.current++;architectureId.current++;
  setTab("overview");setQuery("");setResults([]);setQuestion("");setAnswer("");setArch("");
  setAsking(false);setArchLoading(false);setError("");setLoading(false);setUploadName("");
}
function openRepo(nextRepo){clearRepoScopedState();setRepo(nextRepo)}
function switchRepo(){importId.current++;clearRepoScopedState();setRepo(null);setUrl("")}
useEffect(()=>{localStorage.setItem("rp-dark",dark?"1":"0")},[dark]);useEffect(()=>{api("/api/health").then(setHealth).catch(e=>setHealth({ollama:{online:false,error:e.message}}))},[]);
async function analyze(){
  setError("");if(!url.trim())return setError("Paste a public GitHub repository URL.");
  const request=++importId.current;setLoading(true);
  try{
    const data=await api("/api/analyze",{method:"POST",body:JSON.stringify({url})});
    if(request===importId.current)openRepo(data);
  }catch(e){if(request===importId.current)setError(e.message)}
  finally{if(request===importId.current)setLoading(false)}
}
async function upload(file){
  if(!file)return;
  if(!file.name.toLowerCase().endsWith(".zip"))return setError("Upload a .zip repository archive.");
  const request=++importId.current;setError("");setUploadName(file.name);setLoading(true);
  try{
    const form=new FormData();form.append("file",file);
    const r=await fetch("/api/upload",{method:"POST",body:form});
    const data=await r.json().catch(()=>({}));
    if(!r.ok)throw Error(data.detail||"Upload failed");
    if(request===importId.current)openRepo(data);
  }catch(e){if(request===importId.current)setError(e.message)}
  finally{if(request===importId.current)setLoading(false)}
}
async function search(){
  if(!repo||!query.trim())return;
  const activeSession=sessionId.current,request=++searchId.current;
  setError("");setResults([]);
  try{
    const data=await api("/api/search",{method:"POST",body:JSON.stringify({repo_id:repo.repo_id,query})});
    if(activeSession===sessionId.current&&request===searchId.current)setResults(data.results);
  }catch(e){if(activeSession===sessionId.current&&request===searchId.current)setError(e.message)}
}
async function ask(){
  if(!repo||!question.trim())return;
  const activeSession=sessionId.current,request=++answerId.current;
  setError("");setAnswer("");setAsking(true);
  try{
    const data=await api("/api/ask",{method:"POST",body:JSON.stringify({repo_id:repo.repo_id,question})});
    if(activeSession===sessionId.current&&request===answerId.current)setAnswer(data.answer);
  }catch(e){if(activeSession===sessionId.current&&request===answerId.current)setError(e.message)}
  finally{if(activeSession===sessionId.current&&request===answerId.current)setAsking(false)}
}
async function architecture(){
  if(!repo)return;
  const activeSession=sessionId.current,request=++architectureId.current;
  setError("");setArch("");setArchLoading(true);
  try{
    const data=await api("/api/architecture",{method:"POST",body:JSON.stringify({repo_id:repo.repo_id,question:"architecture"})});
    if(activeSession===sessionId.current&&request===architectureId.current)setArch(data.answer);
  }catch(e){if(activeSession===sessionId.current&&request===architectureId.current)setError(e.message)}
  finally{if(activeSession===sessionId.current&&request===architectureId.current)setArchLoading(false)}
}
return <div className={dark?"app dark":"app"}><header><div className="brand"><div className="logo"><Bot/></div><div><b>RepoPilot</b><small>LOCAL AI CODEBASE ENGINEER</small></div></div><div className="headright"><span className={"pill "+(ollamaAvailable(health)?"on":"")}><i/>Ollama {ollamaAvailable(health)?"online":"offline"}</span><button className="icon" onClick={()=>setDark(!dark)}>{dark?<Sun/>:<Moon/>}</button></div></header>{!repo?<main className="hero"><section><div className="eyebrow"><Sparkles/> CODEBASE, UNDERSTOOD LOCALLY</div><h1>Talk to your<br/><span>entire repo.</span></h1><p>Analyze a public GitHub repository or upload a ZIP, inspect its architecture, search source code, and ask a local AI engineer how it actually works.</p><div className="chips"><b>🔒 Local-first</b><b>🧠 Ollama</b><b>🌳 Code-aware</b><b>⚡ No paid API</b></div></section><section className="connect"><div className="ctop"><Github/><div><b>Connect repository</b><small>GitHub URL or local ZIP archive</small></div></div><label>GITHUB REPOSITORY URL</label><div className="input"><Github/><input value={url} onChange={e=>setUrl(e.target.value)} onKeyDown={e=>e.key==="Enter"&&analyze()} placeholder="https://github.com/owner/repository"/></div><button className="primary" disabled={loading} onClick={analyze}>{loading&&!uploadName?<><Loader2 className="spin"/>Cloning & indexing...</>:<>Analyze repository<ChevronRight/></>}</button><div className="upload-divider"><span>OR</span></div><label className="zip-upload"><Upload/><span><b>{uploadName||"Upload a ZIP repository"}</b><small>Up to 50 MB · files are analyzed locally</small></span><input type="file" accept=".zip,application/zip" onChange={e=>{setUploadName(e.target.files?.[0]?.name||"");void upload(e.target.files?.[0])}}/></label><p className="note"><Terminal/>RepoPilot never executes cloned project code.</p>{error&&<div className="error"><AlertTriangle/>{error}</div>}</section></main>:<main className="workspace"><div className="repohead"><div><div className="rname">{repo.source_url?.startsWith("ZIP:")?<Upload/>:<Github/>}<h2>{repo.source_url?.replace(/^https?:\/\/github.com\//,"").replace(/\.git$/,"")||"Uploaded repository"}</h2><span>{repo.source_url?.startsWith("ZIP:")?"ZIP":"PUBLIC"}</span></div><small>{repo.file_count} indexed files · {repo.total_lines.toLocaleString()} lines · {repo.languages.slice(0,4).map(x=>x.name).join(" · ")}</small></div><button className="secondary" onClick={switchRepo}><X/>New repo</button></div>{error&&<div className="error">{error}</div>}<nav>{[["overview","Overview",Activity],["ask","Ask AI",Bot],["search","Code Search",Search],["tree","File Tree",TreePine]].map(([id,n,I])=><button key={id} className={tab===id?"active":""} onClick={()=>setTab(id)}><I/>{n}</button>)}</nav>{tab==="overview"&&<div className="grid"><section className="panel"><div className="pt"><span><HeartPulse/>Repository health</span><strong>{repo.score}<small>/100</small></strong></div><div className="track"><i style={{width:repo.score+"%"}}/></div><div className="signals">{Object.entries(repo.signals).map(([k,v])=><div key={k} className={v?"good":"bad"}>{v?<CheckCircle2/>:<AlertTriangle/>}{k}</div>)}</div>{repo.warnings.map(w=><p key={w} className="warning"><AlertTriangle/>{w}</p>)}</section><section className="panel"><div className="pt"><span><Code2/>Languages</span></div>{repo.languages.map(l=><div className="lang" key={l.name}><span>{l.name}</span><b>{l.files}</b></div>)}</section><section className="panel wide"><div className="pt"><span><Sparkles/>Local architecture engineer</span><button className="small" onClick={architecture}>{archLoading?<Loader2 className="spin"/>:<Bot/>}{archLoading?"Thinking...":"Explain architecture"}</button></div>{arch?<pre>{arch}</pre>:<div className="empty"><Bot/><p>Ask the local model to map components and data flow.</p></div>}</section></div>}{tab==="ask"&&<div className="askgrid"><section className="panel"><div className="pt"><span><Bot/>Ask the codebase</span><em>LOCAL LLM</em></div><textarea value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Where is authentication handled? How does the API flow work?"/><button className="primary" disabled={asking} onClick={ask}>{asking?<><Loader2 className="spin"/>Reading code...</>:<><Send/>Ask RepoPilot</>}</button><div className="suggest">{["Where is authentication handled?","How does the API request flow work?","Where is the database connection?","Explain the main architecture."].map(q=><button key={q} onClick={()=>setQuestion(q)}>{q}</button>)}</div></section><section className="panel answer"><div className="pt"><span>Engineer answer</span></div>{answer?<pre>{answer}</pre>:<div className="empty"><Bot/><p>File-aware answer appears here.</p></div>}</section></div>}{tab==="search"&&<section className="panel"><div className="search"><Search/><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key==="Enter"&&search()} placeholder="Search functions, variables, routes, imports..."/><button onClick={search}>Search</button></div>{results.length?results.map(r=><div className="result" key={`${r.path}:${r.line}`}><b><FileCode2/>{r.path}<small>:{r.line}</small></b><code>{r.text}</code></div>):<div className="empty"><Search/><p>Search the indexed source code.</p></div>}</section>}{tab==="tree"&&<section className="panel"><div className="pt"><span><TreePine/>Indexed file tree</span><small>{repo.files.length} files</small></div>{repo.files.slice(0,400).map(f=><div className="file" key={f.path}><FileCode2/><span>{f.path}</span><small>{f.lines} lines</small></div>)}</section>}</main>}<footer>RepoPilot · built by <b>@harshitethic</b></footer></div>}createRoot(document.getElementById("root")).render(<App/>);
