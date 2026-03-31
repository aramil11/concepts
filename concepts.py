#!/usr/bin/env python3
"""
concepts.py — Personal Knowledge Ledger Generator

Analyzes a GitHub repo (or local folder) and writes/updates a CONCEPTS.md
file: a living booklet of every real engineering concept in your code.

Usage:
    python concepts.py https://github.com/user/repo
    python concepts.py ./local-folder
    python concepts.py https://github.com/user/repo --output ~/notes/CONCEPTS.md
    python concepts.py https://github.com/user/repo --provider openai --model gpt-4o
    python concepts.py https://github.com/user/repo --provider ollama --model llama3

https://github.com/your-handle/concepts
"""
from __future__ import annotations

import subprocess
import sys
import os

# ---------------------------------------------------------------------------
# Dependency bootstrap — auto-install if missing
# ---------------------------------------------------------------------------

def _ensure(*packages: tuple[str, str]) -> None:
    import importlib
    for pip_name, import_name in packages:
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"  installing {pip_name}...", flush=True)
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pip_name, "-q"],
                stdout=subprocess.DEVNULL,
            )

_ensure(("anthropic", "anthropic"), ("openai", "openai"), ("rich", "rich"))

# ---------------------------------------------------------------------------
# Standard imports (after bootstrap)
# ---------------------------------------------------------------------------

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import textwrap
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel

console = Console()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "0.1"

SKIP_DIRS = {
    "node_modules", ".next", "dist", "build", ".git", ".github", "coverage",
    ".turbo", "out", ".vercel", "storybook-static", "__pycache__", ".mypy_cache",
    ".pytest_cache", "venv", ".venv", "env", ".env", "vendor", "target",
}
SKIP_EXT = {
    ".lock", ".min.js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".webp", ".avif",
    ".mp4", ".mp3", ".wav", ".pdf", ".zip", ".tar", ".gz", ".exe", ".bin",
    ".pyc", ".pyo", ".class", ".o", ".so", ".dylib",
}
KEEP_EXT = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".rb",
    ".css", ".scss", ".md",
}
KEEP_NAMES = {"package.json", "go.mod", "Cargo.toml", "Gemfile", "requirements.txt"}

DOMAINS = [
    "AI & Machine Learning",
    "Backend & APIs",
    "Databases & Storage",
    "Auth & Security",
    "Frontend & UI",
    "Infrastructure",
    "Architecture & Patterns",
]

MAX_FILES = 40
MAX_CONCEPTS = 15
BATCH_SIZE = 5
MAX_FILE_LINES = 500
HEAD_LINES = 200
TAIL_LINES = 50

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RawConcept:
    name: str
    file: str
    snippet: str
    description: str

@dataclass
class Concept:
    name: str
    level: str          # foundational | intermediate | advanced | expert
    one_liner: str      # max 12 words, plain English
    file: str
    snippet: str
    domain: str
    date_added: str = field(default_factory=lambda: str(date.today()))

# ---------------------------------------------------------------------------
# LLM provider abstraction
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: Optional[str]
    base_url: Optional[str]

def _detect_provider(args) -> LLMConfig:
    """Auto-detect provider from env vars or explicit flags."""
    provider = getattr(args, "provider", None)
    model = getattr(args, "model", None)
    api_key = getattr(args, "api_key", None)
    base_url = getattr(args, "base_url", None)

    if provider == "anthropic":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            console.print("[red]ANTHROPIC_API_KEY not set. Export it or pass --api-key.[/red]")
            sys.exit(1)
        return LLMConfig("anthropic", model or "claude-opus-4-6", key, None)

    if provider == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            console.print("[red]OPENAI_API_KEY not set. Export it or pass --api-key.[/red]")
            sys.exit(1)
        return LLMConfig("openai", model or "gpt-4o", key, None)

    if provider == "ollama":
        return LLMConfig("ollama", model or "llama3", "ollama", "http://localhost:11434/v1")

    if provider == "custom":
        if not base_url:
            console.print("[red]--provider custom requires --base-url.[/red]")
            sys.exit(1)
        return LLMConfig("custom", model or "gpt-4o", api_key or "sk-custom", base_url)

    # Auto-detect
    if os.environ.get("ANTHROPIC_API_KEY"):
        return LLMConfig("anthropic", model or "claude-opus-4-6", os.environ["ANTHROPIC_API_KEY"], None)
    if os.environ.get("OPENAI_API_KEY"):
        return LLMConfig("openai", model or "gpt-4o", os.environ["OPENAI_API_KEY"], None)

    console.print(Panel(
        "[bold yellow]No API key found.[/bold yellow]\n\n"
        "Set one of:\n"
        "  [cyan]export ANTHROPIC_API_KEY=sk-ant-...[/cyan]\n"
        "  [cyan]export OPENAI_API_KEY=sk-...[/cyan]\n\n"
        "Or pass explicitly:\n"
        "  [cyan]--provider anthropic --api-key sk-ant-...[/cyan]\n"
        "  [cyan]--provider ollama[/cyan]  (no key needed, runs locally)",
        title="Setup required",
        border_style="yellow",
    ))
    sys.exit(1)


def _call_llm(cfg: LLMConfig, prompt: str) -> str:
    """Single LLM call. Returns the text content."""
    if cfg.provider == "anthropic":
        import anthropic as _ant
        client = _ant.Anthropic(api_key=cfg.api_key)
        resp = client.messages.create(
            model=cfg.model,
            max_tokens=4096,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    else:
        # openai, ollama, custom — all use the openai SDK
        from openai import OpenAI
        kwargs: dict = {"api_key": cfg.api_key}
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        client = OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=cfg.model,
            temperature=0,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()


def _parse_json(raw: str) -> list:
    """Strip markdown fences and parse JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()
    return json.loads(raw)

# ---------------------------------------------------------------------------
# Step 1: Repo ingestion
# ---------------------------------------------------------------------------

def clone_repo(url: str) -> tuple[str, str, bool]:
    """Returns (local_path, repo_name, is_temp)."""
    if os.path.isdir(url):
        return url, Path(url).resolve().name, False

    repo_name = url.rstrip("/").replace(".git", "").split("/")[-1]
    tmp = tempfile.mkdtemp(prefix="concepts_")

    try:
        import git
        console.print(f"  cloning [cyan]{url}[/cyan]...")
        git.Repo.clone_from(url, tmp, depth=1)
        return tmp, repo_name, True
    except ImportError:
        # fallback: system git
        result = subprocess.run(
            ["git", "clone", "--depth=1", url, tmp],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return tmp, repo_name, True
        shutil.rmtree(tmp, ignore_errors=True)
        _maybe_private(url, result.stderr)
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        _maybe_private(url, str(e))


def _maybe_private(url: str, detail: str):
    if "authentication" in detail.lower() or "not found" in detail.lower() or "403" in detail:
        console.print(
            "[red]This repo is private. Clone it locally first and pass the folder path.[/red]"
        )
    else:
        console.print(f"[red]Clone failed: {detail}[/red]")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Step 2: Filter and rank files
# ---------------------------------------------------------------------------

def collect_files(repo_path: str) -> list[dict]:
    all_files = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        rel_root = os.path.relpath(root, repo_path)

        for fname in files:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, repo_path).replace("\\", "/")
            ext = Path(fname).suffix.lower()

            if ext in SKIP_EXT:
                continue
            if fname not in KEEP_NAMES and ext not in KEEP_EXT:
                continue
            # skip minified
            if fname.endswith(".min.js") or fname.endswith(".min.css"):
                continue

            try:
                content = Path(fpath).read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = content.splitlines()
            line_count = len(lines)

            # Truncate long files
            if line_count > MAX_FILE_LINES:
                truncated = (
                    "\n".join(lines[:HEAD_LINES])
                    + f"\n\n# [...truncated {line_count - HEAD_LINES - TAIL_LINES} lines...]\n\n"
                    + "\n".join(lines[-TAIL_LINES:])
                )
            else:
                truncated = content

            # Priority tier
            if fname in KEEP_NAMES or fname in {"__init__.py", "main.py", "index.ts", "index.js", "app.py", "wsgi.py"}:
                priority = 0
            elif any(seg in rel for seg in ["src/", "app/", "lib/", "core/"]):
                priority = 1
            else:
                priority = 2

            all_files.append({
                "rel": rel,
                "name": fname,
                "ext": ext,
                "line_count": line_count,
                "content": truncated,
                "priority": priority,
            })

    all_files.sort(key=lambda f: (f["priority"], -f["line_count"]))
    total = len(all_files)

    if total == 0:
        console.print(
            "[red]No source files found. Supported: .py .ts .tsx .js .jsx .go .rs .rb[/red]"
        )
        sys.exit(1)

    if total > MAX_FILES:
        skipped = total - MAX_FILES
        console.print(f"  [yellow]{total} files found — keeping top {MAX_FILES}, skipping {skipped}[/yellow]")
        all_files = all_files[:MAX_FILES]
    else:
        console.print(f"  📦 Found [cyan]{total}[/cyan] source files")

    return all_files

# ---------------------------------------------------------------------------
# Step 3: LLM extraction — batched
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """\
Analyze these source files. Find every genuine CS/engineering concept demonstrated.
Ignore: syntax, variable names, library names (unless the concept IS the pattern).
Only include things a CS student would need to deliberately learn — not "using a for loop" or "importing a module."

Files:
{file_contents}

For each concept return a JSON array:
[{{"name": "...", "file": "filename_only.py", "snippet": "4-8 lines of actual code that best illustrates this", "description": "one sentence — what this concept is"}}]

Return valid JSON only. No prose. No markdown fences.\
"""

def extract_raw_concepts(files: list[dict], cfg: LLMConfig) -> list[RawConcept]:
    batches = [files[i:i+BATCH_SIZE] for i in range(0, len(files), BATCH_SIZE)]
    all_raw: list[RawConcept] = []

    for idx, batch in enumerate(batches, 1):
        console.print(f"  🧠 Analyzing batch [cyan]{idx}/{len(batches)}[/cyan] ({len(batch)} files)...")
        file_block = ""
        for f in batch:
            file_block += f"\n\n{'='*60}\nFILE: {f['rel']}\n{'='*60}\n{f['content']}"

        prompt = EXTRACTION_PROMPT.format(file_contents=file_block)

        for attempt in range(2):
            try:
                raw = _call_llm(cfg, prompt)
                data = _parse_json(raw)
                for item in data:
                    if isinstance(item, dict) and item.get("name"):
                        all_raw.append(RawConcept(
                            name=item.get("name", ""),
                            file=Path(item.get("file", "")).name,
                            snippet=item.get("snippet", ""),
                            description=item.get("description", ""),
                        ))
                console.print(f"    [green]→ {len(data)} concepts found[/green]")
                break
            except Exception as e:
                if attempt == 0:
                    console.print(f"    [yellow]retrying batch {idx}... ({e})[/yellow]")
                else:
                    console.print(f"    [yellow]skipping batch {idx}: {e}[/yellow]")

    return all_raw

# ---------------------------------------------------------------------------
# Step 4: Synthesis — single call
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = """\
Given these raw concept candidates extracted from a codebase:
{candidates}

Produce the final concept list.

Rules:
- Deduplicate: if the same concept appears multiple times, keep the best/clearest example
- Max {max_concepts} concepts total — quality over quantity, raise the bar
- Skip trivial things (a for loop, a conditional, string formatting)
- The one_liner must be understandable by a smart non-programmer — max 12 words
- Never use: powerful, robust, seamlessly, leverage, utilize, paradigm

For each concept produce exactly:
{{"name": "...", "level": "foundational|intermediate|advanced|expert",
 "one_liner": "plain English, max 12 words, no jargon",
 "file": "filename_only", "snippet": "4-8 lines of actual code",
 "domain": "AI & Machine Learning|Backend & APIs|Databases & Storage|Auth & Security|Frontend & UI|Infrastructure|Architecture & Patterns"}}

Return a valid JSON array only. No prose.\
"""

def synthesize_concepts(raw: list[RawConcept], cfg: LLMConfig) -> list[Concept]:
    candidates_json = json.dumps([
        {"name": r.name, "file": r.file, "snippet": r.snippet, "description": r.description}
        for r in raw
    ], indent=2)

    prompt = SYNTHESIS_PROMPT.format(
        candidates=candidates_json,
        max_concepts=MAX_CONCEPTS,
    )

    for attempt in range(2):
        try:
            raw_resp = _call_llm(cfg, prompt)
            data = _parse_json(raw_resp)
            concepts = []
            for item in data:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                domain = item.get("domain", "Architecture & Patterns")
                if domain not in DOMAINS:
                    domain = "Architecture & Patterns"
                concepts.append(Concept(
                    name=item["name"],
                    level=item.get("level", "intermediate"),
                    one_liner=item.get("one_liner", ""),
                    file=Path(item.get("file", "")).name,
                    snippet=item.get("snippet", ""),
                    domain=domain,
                ))
            return concepts
        except Exception as e:
            if attempt == 0:
                console.print(f"  [yellow]synthesis retry... ({e})[/yellow]")
            else:
                console.print(f"  [red]synthesis failed: {e}[/red]")
                sys.exit(1)

    return []

# ---------------------------------------------------------------------------
# Step 5: CONCEPTS.md — read, merge, write
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
H3_RE = re.compile(r"^### (.+)$", re.MULTILINE)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _read_existing(path: Path) -> tuple[dict, set[str], str]:
    """Returns (frontmatter_dict, existing_concept_slugs, body_after_frontmatter)."""
    if not path.exists():
        return {}, set(), ""

    text = path.read_text(encoding="utf-8")
    fm: dict = {}
    body = text

    m = FRONTMATTER_RE.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')
        body = text[m.end():]

    existing_names = {_slug(m.group(1)) for m in H3_RE.finditer(body)}
    return fm, existing_names, body


def _lang_tag(filename: str) -> str:
    ext_map = {
        ".py": "python", ".ts": "typescript", ".tsx": "tsx",
        ".js": "javascript", ".jsx": "jsx", ".go": "go",
        ".rs": "rust", ".rb": "ruby", ".css": "css", ".scss": "scss",
    }
    return ext_map.get(Path(filename).suffix.lower(), "")


def _render_concept(c: Concept) -> str:
    lang = _lang_tag(c.file)
    snippet = c.snippet.strip()
    today = c.date_added
    return (
        f"### {c.name}\n"
        f"`{c.level}` · {c.file} · {today}\n\n"
        f"{c.one_liner}\n\n"
        f"```{lang}\n{snippet}\n```\n\n---\n"
    )


def _render_full(fm: dict, existing_body: str, new_concepts: list[Concept]) -> str:
    today = str(date.today())
    repos = int(fm.get("repos_analyzed", 0)) + (1 if new_concepts or not existing_body else 0)

    # Count existing concepts from body
    existing_count = len(H3_RE.findall(existing_body)) if existing_body else 0
    total = existing_count + len(new_concepts)

    fm_block = (
        f"---\n"
        f'vibelearn: "{VERSION}"\n'
        f"repos_analyzed: {repos}\n"
        f"concepts_total: {total}\n"
        f'last_updated: "{today}"\n'
        f"---\n"
    )

    # Format date for display
    try:
        from datetime import datetime
        display_date = datetime.strptime(today, "%Y-%m-%d").strftime("%B %Y")
    except Exception:
        display_date = today

    if existing_body.strip():
        # Update the summary line in existing body
        header = f"\n# My Concept Ledger\n\n**{total} concepts** · **{repos} repos** · last updated {display_date}\n\n---\n"
        # Strip old header if present
        body_stripped = re.sub(r"\n# My Concept Ledger\n.*?---\n", "", existing_body, flags=re.DOTALL, count=1).lstrip("\n")
    else:
        body_stripped = ""
        header = f"\n# My Concept Ledger\n\n**{total} concepts** · **{repos} repos** · last updated {display_date}\n\n---\n"

    # Group new concepts by domain
    by_domain: dict[str, list[Concept]] = {}
    for c in new_concepts:
        by_domain.setdefault(c.domain, []).append(c)

    # Build new sections
    new_sections = ""
    for domain in DOMAINS:
        if domain not in by_domain:
            continue
        # Check if domain already exists in body
        if f"## {domain}" in body_stripped:
            # Append concepts to existing section
            rendered = "".join(_render_concept(c) for c in by_domain[domain])
            body_stripped = body_stripped.replace(
                f"## {domain}\n",
                f"## {domain}\n\n" + rendered,
                1,
            )
        else:
            new_sections += f"\n## {domain}\n\n"
            new_sections += "".join(_render_concept(c) for c in by_domain[domain])

    return fm_block + header + body_stripped + new_sections


def write_concepts_md(
    output_path: Path,
    new_concepts: list[Concept],
    existing_fm: dict,
    existing_body: str,
    existing_slugs: set[str],
) -> int:
    # Deduplicate
    deduped = [c for c in new_concepts if _slug(c.name) not in existing_slugs]
    added = len(deduped)

    rendered = _render_full(existing_fm, existing_body, deduped)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    return added

# ---------------------------------------------------------------------------
# README auto-generation
# ---------------------------------------------------------------------------

README_TEMPLATE = """\
# concepts.py — Personal Knowledge Ledger

Analyzes any GitHub repo (or local folder) and writes a `CONCEPTS.md` —
a living booklet of every real engineering concept hiding in your code.
Run it on every project you build. Watch your knowledge compound.

## Install

```bash
pip install anthropic openai rich gitpython
```

Set your API key:
```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY
```

## Usage

```bash
# Analyze a GitHub repo
python concepts.py https://github.com/user/repo

# Analyze a local folder, append to existing CONCEPTS.md
python concepts.py ./my-project

# Use a specific provider / model
python concepts.py https://github.com/user/repo --provider openai --model gpt-4o-mini
python concepts.py https://github.com/user/repo --provider ollama --model llama3

# Custom output location
python concepts.py https://github.com/user/repo --output ~/notes/CONCEPTS.md
```

## How it works

1. Clones the repo (or reads the local folder)
2. Filters to source files — ignores node_modules, build artifacts, generated files
3. Sends files in batches to an LLM, extracts every genuine CS/engineering concept
4. Synthesizes and deduplicates — keeps the best 15 concepts per repo
5. Writes or updates `CONCEPTS.md` — never overwrites, only appends new concepts

## Output format

Each concept gets:
- A **level** badge (foundational / intermediate / advanced / expert)
- A **one-liner** in plain English — no jargon
- The **actual code snippet** from your file that demonstrates it
- Organized by **domain**: AI & ML, Backend & APIs, Auth & Security, and more

Concepts are deduplicated across runs — analyze 10 repos and your `CONCEPTS.md`
becomes a personal CS textbook, written in your own code.

## Provider support

| Provider   | Flag                          | Key needed              |
|------------|-------------------------------|-------------------------|
| Anthropic  | `--provider anthropic`        | `ANTHROPIC_API_KEY`     |
| OpenAI     | `--provider openai`           | `OPENAI_API_KEY`        |
| Ollama     | `--provider ollama`           | none (runs locally)     |
| Any OpenAI-compatible | `--provider custom --base-url http://...` | optional |

Auto-detects from environment if `--provider` is omitted.

## License

MIT
"""

def ensure_readme(here: Path) -> None:
    readme = here / "README.md"
    if not readme.exists():
        readme.write_text(README_TEMPLATE, encoding="utf-8")
        console.print("  📄 Created [cyan]README.md[/cyan]")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="concepts.py",
        description="Personal Knowledge Ledger — extract CS concepts from any codebase.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              python concepts.py https://github.com/user/repo
              python concepts.py ./local-folder --output ~/notes/CONCEPTS.md
              python concepts.py https://github.com/user/repo --provider ollama --model llama3
        """),
    )
    p.add_argument("repo", help="GitHub URL or local folder path")
    p.add_argument("--output", "-o", default="CONCEPTS.md",
                   help="output path (default: ./CONCEPTS.md)")
    p.add_argument("--provider", choices=["anthropic", "openai", "ollama", "custom"],
                   help="LLM provider (auto-detected from env if omitted)")
    p.add_argument("--model", help="model name (overrides provider default)")
    p.add_argument("--api-key", dest="api_key", help="API key (or use env var)")
    p.add_argument("--base-url", dest="base_url",
                   help="base URL for --provider custom")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]concepts.py[/bold cyan] — Personal Knowledge Ledger\n"
        "[dim]extracting what you built, naming what you learned[/dim]",
        border_style="cyan",
    ))

    # Detect LLM
    cfg = _detect_provider(args)
    console.print(
        f"  using [cyan]{cfg.provider}[/cyan] / [cyan]{cfg.model}[/cyan]"
    )

    output_path = Path(args.output).expanduser().resolve()

    # Read existing CONCEPTS.md
    existing_fm, existing_slugs, existing_body = _read_existing(output_path)
    if existing_slugs:
        console.print(f"  found existing CONCEPTS.md with [cyan]{len(existing_slugs)}[/cyan] concepts")

    tmp_dir = None
    try:
        # Step 1: Clone / read
        console.print("\n[bold]🔍 Reading repo...[/bold]")
        local_path, repo_name, is_temp = clone_repo(args.repo)
        if is_temp:
            tmp_dir = local_path

        # Step 2: Collect files
        files = collect_files(local_path)

        # Step 3: Extract
        console.print(f"\n[bold]🧠 Extracting concepts from {len(files)} files...[/bold]")
        raw = extract_raw_concepts(files, cfg)
        console.print(f"  [green]{len(raw)} raw candidates[/green]")

        if not raw:
            console.print("[yellow]No concepts extracted — repo may be mostly config or boilerplate.[/yellow]")
            sys.exit(0)

        # Step 4: Synthesize
        console.print("\n[bold]🔬 Synthesizing...[/bold]")
        concepts = synthesize_concepts(raw, cfg)
        console.print(f"  [green]{len(concepts)} refined concepts[/green]")

        # Step 5: Write
        console.print(f"\n[bold]✍️  Writing {output_path.name}...[/bold]")
        added = write_concepts_md(output_path, concepts, existing_fm, existing_body, existing_slugs)

        # README
        ensure_readme(Path(__file__).parent)

        # Summary
        total_now = len(existing_slugs) + added
        console.print(f"\n[bold green]✅ Done.[/bold green]")
        console.print(f"   {added} new concepts added  ({total_now} total)")
        console.print(f"   [link=file://{output_path}]{output_path}[/link]")

    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
