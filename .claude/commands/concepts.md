Analyze the current project and extract CS/engineering concepts into ~/CONCEPTS.md.

## Steps

1. Use Glob to find all source files (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, `.rb`, `.css`, `.scss`). Skip `node_modules`, `dist`, `build`, `.git`, `__pycache__`, `.venv`, `vendor`.

2. Read the most important files (prioritize `src/`, `app/`, `lib/`, `core/`, entry points like `main.py`, `index.ts`). Read up to 40 files total.

3. Analyze the code and identify genuine CS/engineering concepts — things a student would need to deliberately learn. Ignore syntax, variable names, trivial patterns. Good examples: RAG pipelines, rate limiting, database connection pooling, JWT auth, event-driven architecture, memoization, etc.

4. For each concept produce:
   - **name**: the concept name
   - **level**: foundational | intermediate | advanced | expert
   - **one_liner**: plain English, max 12 words, no jargon, never use "powerful/robust/seamlessly/leverage/utilize/paradigm"
   - **file**: filename where it appears
   - **snippet**: 4-8 lines of actual code that best illustrates it
   - **domain**: one of — AI & Machine Learning | Backend & APIs | Databases & Storage | Auth & Security | Frontend & UI | Infrastructure | Architecture & Patterns

   Max 15 concepts. Quality over quantity.

5. Read `~/CONCEPTS.md` if it exists. Skip any concepts whose names already appear in it (deduplicate).

6. Append new concepts to `~/CONCEPTS.md` in this format:

```
### {name}
`{level}` · {file} · {today's date}

{one_liner}

```{language}
{snippet}
```

---
```

   Group under `## {domain}` headers. If the domain section already exists, append inside it. If not, create it. Update the summary line at the top: `**N concepts** · **N repos** · last updated {Month Year}`.

   If `~/CONCEPTS.md` doesn't exist yet, create it with this header:
   ```
   ---
   concepts_total: N
   last_updated: "YYYY-MM-DD"
   ---

   # My Concept Ledger

   **N concepts** · **1 repos** · last updated {Month Year}

   ---
   ```

7. Report how many concepts were added and the path to the file.
