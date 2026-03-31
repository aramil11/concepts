---
vibelearn: "0.1"
repos_analyzed: 1
concepts_total: 11
last_updated: "2026-03-31"
---

# My Concept Ledger

**11 concepts** · **1 repo** · last updated March 2026

---

## AI & Machine Learning

### RAG — Retrieval-Augmented Generation
`advanced` · matcher.py · 2026-03-31

Fetch your own data first, then hand it to the LLM so it doesn't guess.

```python
queries = agent.generate_search_queries(user.profile.query)
for q in queries:
    results = search_bills(q, k=5)
    for r in results:
        candidate_ids.add(r["id"])
explanation = agent.match_and_summarize(user.profile.query, [bill])
```

---

### Vector Embeddings & Semantic Search
`advanced` · vector_store.py · 2026-03-31

GPS coordinates for meaning — similar ideas cluster together even with different words.

```python
results = vector_store.similarity_search_with_relevance_scores(query, k=k)
for doc, score in results:
    if score < SIMILARITY_THRESHOLD:
        continue
    unique_bills.append({"id": b_id, "title": doc.metadata["title"], "score": score})
```

---

### LLM Binary Classification
`intermediate` · matcher.py · 2026-03-31

Ask the LLM a yes/no question as a quality gate — no training data needed.

```python
resp = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human)])
verdict = resp.content.strip().upper().strip(".,!? \n")
if verdict != "YES":
    db.session.delete(item)
    removed += 1
```

---

### Text Chunking for Embeddings
`intermediate` · vector_store.py · 2026-03-31

Split long documents into overlapping pieces so nothing falls through the cracks.

```python
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
chunks = text_splitter.split_text(text)
docs = [
    Document(page_content=chunk, metadata={"bill_id": bill.id, "title": bill.title})
    for chunk in chunks
]
vector_store.add_documents(docs)
```

---

### Multi-Stage LLM Orchestration
`expert` · scraper.py · 2026-03-31

Chain multiple LLM calls, each with a different role, to refine raw data into decisions.

```python
llm_tags = agent.generate_tags(bill)          # call 1: categorize
queries = agent.generate_search_queries(...)   # call 2: query generation
explanation = agent.match_and_summarize(...)   # call 3: final judgment
verdict = llm.invoke([filter_prompt, human])   # call 4: quality gate
message = _write_notification(llm, prompt, ...) # call 5: compose message
```

---

## Backend & APIs

### Server-Sent Events (Streaming Responses)
`advanced` · bills.py · 2026-03-31

Hold the connection open and trickle tokens to the browser as they arrive.

```python
def generate():
    for chunk in llm.stream([SystemMessage(content=system), HumanMessage(content=human)]):
        token = chunk.content
        if token:
            full_text += token
            yield f"data: {token}\n\n"
    yield "data: [DONE]\n\n"

return Response(stream_with_context(generate()), mimetype="text/event-stream")
```

---

## Databases & Storage

### Content Hashing for Idempotency
`intermediate` · vector_store.py · 2026-03-31

Fingerprint a document — if the fingerprint hasn't changed, skip re-processing it.

```python
def compute_bill_hash(bill: Bill) -> str:
    content = f"{bill.title}\n{bill.full_text or bill.summary or ''}\n{bill.topics}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def index_bill(bill: Bill):
    new_hash = compute_bill_hash(bill)
    if bill.is_indexed and bill.content_hash == new_hash:
        return  # nothing changed, skip entirely
```

---

### ORM Relationships & Foreign Keys
`foundational` · models.py · 2026-03-31

Let Python objects reference each other so the database join happens automatically.

```python
class User(UserMixin, db.Model):
    profile = db.relationship("UserProfile", back_populates="user", uselist=False)
    notifications = db.relationship("Notification", back_populates="user")

class UserProfile(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", back_populates="profile")
```

---

## Auth & Security

### JWT Authentication via OIDC
`advanced` · auth.py · 2026-03-31

Verify a cryptographically signed token to prove identity without storing passwords.

```python
claims = verify_telegram_id_token(id_token, current_app.config["TELEGRAM_CLIENT_ID"])
telegram_id = str(claims.get("id") or claims.get("sub"))
user = User.query.filter_by(telegram_id=telegram_id).first()
if not user:
    user = User(telegram_id=telegram_id, username=claims.get("preferred_username"))
    db.session.add(user)
```

---

## Frontend & UI

### State Machine in Vanilla JavaScript
`intermediate` · stt.js · 2026-03-31

A button with three behaviors — which one runs depends on which state it's in.

```javascript
function setState(state) {
    btn.dataset.sttState = state;
    if (state === 'recording') { iconEl.textContent = 'stop'; }
    else if (state === 'loading') { iconEl.textContent = 'hourglass_empty'; }
    else if (inputEl.value.trim()) { iconEl.textContent = 'arrow_upward'; }
    else { iconEl.textContent = 'mic'; }
}
```

---

## Architecture & Patterns

### Flask App Factory & Blueprint Architecture
`intermediate` · __init__.py · 2026-03-31

Build the app inside a function and split routes into modules — makes testing work.

```python
def create_app(config=None):
    app = Flask(__name__)
    with app.app_context():
        app.register_blueprint(auth, url_prefix="/auth")
        app.register_blueprint(bills, url_prefix="/bills")
        app.register_blueprint(admin, url_prefix="/admin")
        db.create_all()
    return app
```

---
