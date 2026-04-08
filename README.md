# DocWizard 🧙‍♂️

> AI-powered code documentation and search agent — paste a GitHub URL, get professional docs in seconds.

---

## What It Does

DocWizard takes any public GitHub repository, reads every Python file, and automatically generates clean human-readable documentation using AI. It also lets developers search the codebase in plain English — no more digging through files manually.

**Core features:**
- Generates documentation for every file in a repo with one click
- Answers natural language questions about the codebase
- Semantic search powered by FAISS vector embeddings
- Download individual file docs or all docs as a ZIP
- Auto-generates README.md and .gitignore for any project

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| LLM | OpenRouter API (qwen/qwen3-coder:free) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Search | FAISS (faiss-cpu) |
| Code Parsing | Python AST (built-in) |
| GitHub Access | GitHub REST API v3 |
| Frontend | React 18, Vite, Tailwind CSS |
| File Handling | JSZip (client-side ZIP generation) |

**Total cost to run: $0** — all free tier services, no credit card required.

---

## Project Structure

```
DocWizard/
├── backend/
│   ├── main.py              # FastAPI app, all API endpoints
│   ├── doc_generator.py     # OpenRouter API calls, doc generation logic
│   ├── parser.py            # AST-based Python code parser
│   ├── vector_store.py      # FAISS index creation and semantic search
│   ├── github_client.py     # GitHub API, repo file fetching
│   └── requirements.txt     # Python dependencies
├── frontend/
│   └── src/
│       ├── App.jsx          # Main React component, full UI
│       └── components/      # UI sub-components
├── faiss_indexes/           # Auto-generated, gitignored
├── .env                     # Your API keys, gitignored
├── .env.example             # Template for environment variables
├── .gitignore
└── README.md
```

---

## Prerequisites

Make sure these are installed on your machine before starting:

- [Python 3.10+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/)
- [Git](https://git-scm.com/)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/docwizard.git
cd docwizard
```

### 2. Get your API keys

**OpenRouter API key** (free, no credit card):
1. Go to [openrouter.ai](https://openrouter.ai)
2. Sign up → Profile → Keys → Create Key
3. Copy the key (starts with `sk-or-...`)

**GitHub Personal Access Token** (free):
1. Go to GitHub → Settings → Developer settings
2. Personal access tokens → Tokens (classic) → Generate new token
3. Check only the `repo` scope → Generate → Copy the token (starts with `ghp_...`)

### 3. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

```env
OPENROUTER_API_KEY=sk-or-your-key-here
GITHUB_TOKEN=ghp_your-token-here
LLM_MODEL=qwen/qwen3-coder:free
```

### 4. Install backend dependencies

```bash
cd backend
pip install "numpy<2"
pip install -r requirements.txt
```

> **Windows note:** If `faiss-cpu` fails to install, run `pip install faiss-cpu --prefer-binary` instead.

### 5. Install frontend dependencies

```bash
cd ../frontend
npm install
```

---

## Running the App

You need two terminals open simultaneously.

**Terminal 1 — Backend:**
```bash
cd backend
uvicorn main:app --reload
```
Backend runs at `http://127.0.0.1:8000`

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```
Frontend runs at `http://localhost:5173`

Open `http://localhost:5173` in your browser.

---

## How to Use

1. Paste any public GitHub repository URL into the input field
   - Example: `https://github.com/tiangolo/fastapi`
2. Click **Generate Docs** and wait 10–30 seconds
3. Documentation appears for every Python file in the repo
4. Click any file card to expand and read its docs
5. Use the **Copy** or **Download .md** button on each card
6. Click **Download All as ZIP** to get everything at once
7. Type a question in the search bar to query the codebase
   - Example: *"How do I handle authentication?"*
8. Click **Generate README** to create a README for that repo
9. Click **Generate .gitignore** for a project-specific gitignore

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/generate-docs` | Generate docs for a GitHub repo |
| POST | `/ask` | Ask a natural language question |
| POST | `/generate-readme` | Generate a README.md for the repo |
| POST | `/generate-gitignore` | Generate a .gitignore for the repo |

**Example request:**
```bash
curl -X POST http://localhost:8000/generate-docs \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/tiangolo/fastapi"}'
```

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | Yes |
| `GITHUB_TOKEN` | GitHub personal access token | Yes |
| `LLM_MODEL` | Model to use (default: `qwen/qwen3-coder:free`) | No |

---

## Known Limitations

- **Free tier rate limits:** OpenRouter free tier allows 50 requests/day and 20 requests/minute. DocWizard batches all files into one request to stay within this limit.
- **Python only:** The AST parser currently supports Python files only. JavaScript and other languages are planned for a future update.
- **Public repos only:** Private repositories require additional GitHub token scopes.
- **Context window:** Very large repos (100+ files) may exceed the model's context window. DocWizard will document as many files as fit.

---

## Troubleshooting

**`uvicorn main:app --reload` gives NumPy error:**
```bash
pip install "numpy<2" --force-reinstall
```

**Search returns 0 results:**
Generate docs first before searching — the search index is built during doc generation.

**Rate limit error but OpenRouter shows 0 requests:**
Your `.env` file is not being loaded. Make sure `load_dotenv()` is called at the top of `doc_generator.py` and your `.env` file is in the `backend/` folder.

**`npm run dev` fails:**
Make sure you ran `npm install` inside the `frontend/` folder first.

---

## Roadmap

- [ ] JavaScript / TypeScript support
- [ ] Private repository support
- [ ] GitHub Action for auto-updating docs on push
- [ ] Change detection — only re-document modified files
- [ ] Architecture diagram generation
- [ ] Multi-language support (Java, Go, Rust)

---

## License

MIT License — free to use, modify, and distribute.

---

## Acknowledgements

- [OpenRouter](https://openrouter.ai) for free LLM access
- [FAISS](https://github.com/facebookresearch/faiss) by Meta for vector search
- [sentence-transformers](https://www.sbert.net/) for local embeddings
- [FastAPI](https://fastapi.tiangolo.com/) for the backend framework