# Source-grounded RAG (local BM25)

RepoPilot now exposes **retrieval-augmented generation (RAG)** for imported
repositories. It is deliberately **lexical RAG**, not an embeddings/vector
database product: it works offline without a paid API, using pure-Python
BM25 plus deterministic source/path signals.

The retrieval endpoint works even when Ollama is unavailable. Generation is
optional and requires your configured local Ollama model.

## How it works

1. Validate the existing 12-character repository ID and resolve only inside
   RepoPilot's managed imports.
2. Use the existing safety-filtered text-file iterator (no symlink traversal,
   ignored build artifacts, 300 KB maximum per file).
3. Split source into overlapping 36-line windows, retaining the original
   source path and 1-based line ranges.
4. Tokenize source symbols including snake_case and camelCase, calculate BM25
   term frequency/inverse document frequency and apply documented filename
   and exact-phrase boosts.
5. Reduce near-duplicate evidence with maximum marginal relevance (MMR).
6. Return source snippets and line-range citations. For optional generation,
   bound the evidence prompt and label repository content as **untrusted**.

## Retrieval (no AI required)

After importing a ZIP or GitHub repository, use its returned repo_id:

~~~bash
curl --fail-with-body -sS http://127.0.0.1:8000/api/rag/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"repo_id":"YOUR_REPO_ID","query":"where is authorization handled","limit":6}'
~~~

Result shape:

~~~json
{
  "retriever": "bm25",
  "count": 1,
  "results": [
    {
      "citation": "src/auth.py:L14-L30",
      "path": "src/auth.py",
      "start_line": 14,
      "end_line": 30,
      "score": 3.45,
      "text": "source excerpt ..."
    }
  ]
}
~~~

The JSON above is an **illustrative schema**, not evidence of a specific
repository's contents or a live model call. Specify "path_prefix":"src"
to restrict retrieval to a directory subtree.

## Optional model-based answer

~~~bash
curl --fail-with-body -sS http://127.0.0.1:8000/api/rag/ask \
  -H 'Content-Type: application/json' \
  -d '{"repo_id":"YOUR_REPO_ID","question":"where is authorization handled"}'
~~~

Response fields: answer, sources (each source's original path and line range),
and model_used. If retrieval yields no evidence, RepoPilot returns
model_used=false and does not query Ollama or invent a citation. If evidence
exists but Ollama is unavailable, it responds with HTTP 503. Sources are
**retrieval references**, not a claim that every generated sentence is verified.

## Design constraints

- No background indexing service, vector embeddings, remote LLM provider or
  paid subscription. Files are scanned on each query and bounded by a
  2,000-file / 4,000-chunk maximum (subject to future tuning).
- Each retrieval response includes at most 20 snippets, with excerpt text
  bounded to 1,800 characters; model context is capped to 12,000 characters.
- Results can miss synonym-only matches because BM25 is lexical.
- Generic question words are ignored during ranking; direct snake_case symbol
  queries are treated atomically to avoid unrelated partial-word matches.
- Long source lines are capped during chunking; retrieval citations still
  identify the original source lines.
- Prompt injection in repository content remains a real LLM risk. Evidence
  is explicitly labeled untrusted, and local AI has no tool-execution bridge
  in this flow. Model output must still be checked against cited files.
- The local-only API boundary is unchanged. Do not expose this service
  publicly without authentication, rate limits and isolation.
- The existing cross-process AI work-admission pool guards both new endpoints.
- No persistent retrieval cache is created: deletion of an imported repo
  cannot leave a searchable stale index.

## Verify locally

~~~bash
python -m pip install -r backend/requirements-test.txt
PYTHONPATH=backend python -m unittest discover -s backend/tests -p 'test_rag*.py' -v
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python examples/rag_demo.py
python examples/rag_live_http_smoke.py   # localhost HTTP + intentionally stubbed Ollama
~~~
