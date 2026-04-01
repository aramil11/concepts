# concepts.py — Personal Knowledge Ledger

Analyzes any GitHub repo (or local folder) and writes a `CONCEPTS.md` —
a living booklet of every real engineering concept hiding in your code.

Run it on every project you build. Watch your knowledge compound.

```
🔍 Reading repo...
📦 Found 23 source files
🧠 Analyzing batch 1/5...
🧠 Analyzing batch 2/5...
🔬 Synthesizing...
✍️  Writing CONCEPTS.md...
✅ Done. 8 new concepts added.
```

---

## Install

```bash
pip install anthropic openai rich gitpython
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY
```

---

## Usage

```bash
# Analyze a GitHub repo
python concepts.py https://github.com/user/repo

# Analyze a local folder — appends to existing CONCEPTS.md
python concepts.py ./my-project

# Custom output location — recommended: one file that grows across all your repos
python concepts.py https://github.com/user/repo --output ~/CONCEPTS.md

# Use a specific provider / model
python concepts.py https://github.com/user/repo --provider openai --model gpt-4o-mini
python concepts.py https://github.com/user/repo --provider ollama --model llama3
```

### Claude Code slash command

This repo ships a `/concepts` slash command for [Claude Code](https://claude.ai/code). Once you have `concepts` on your PATH (see below), open any project in Claude Code and type:

```
/concepts
```

It analyzes the current folder and appends new concepts to `~/CONCEPTS.md`.

**Add `concepts` to your PATH:**

```bash
chmod +x /path/to/concepts.py
ln -s /path/to/concepts.py /usr/local/bin/concepts
```

---

## How it works

1. **Clone** — clones the repo (or reads local folder), no auth needed for public repos
2. **Filter** — keeps only source files; ignores `node_modules`, `dist`, lock files, images
3. **Extract** — sends files in batches to an LLM, pulls every genuine CS concept
4. **Synthesize** — deduplicates across batches, keeps the best 15 per repo
5. **Write** — appends to `CONCEPTS.md`, never overwrites existing concepts

---

## Output

```markdown
### RAG — Retrieval-Augmented Generation
`advanced` · matcher.py · 2026-03-31

Fetch your own data first, then hand it to the LLM so it doesn't guess.

```python
queries = agent.generate_search_queries(user.profile.query)
for q in queries:
    results = search_bills(q, k=5)
explanation = agent.match_and_summarize(user.profile.query, [bill])
```
```

Every concept gets:
- A **level** badge — `foundational` · `intermediate` · `advanced` · `expert`
- A **one-liner** in plain English, no jargon
- The **actual code snippet** from your file
- Organized by **domain** — AI & ML, Backend, Auth, Frontend, Infrastructure, and more

Concepts deduplicate across runs. Analyze 10 repos and your `CONCEPTS.md` becomes a personal CS textbook written in your own code.

---

## Provider support

| Provider   | Flag                                           | Key needed          |
|------------|------------------------------------------------|---------------------|
| Anthropic  | `--provider anthropic`                         | `ANTHROPIC_API_KEY` |
| OpenAI     | `--provider openai`                            | `OPENAI_API_KEY`    |
| Ollama     | `--provider ollama`                            | none (runs locally) |
| Any OpenAI-compatible | `--provider custom --base-url http://...` | optional   |

Auto-detects from environment if `--provider` is omitted.

---

## Supported languages

`.py` · `.ts` · `.tsx` · `.js` · `.jsx` · `.go` · `.rs` · `.rb` · `.css` · `.scss`

---

## License

MIT
