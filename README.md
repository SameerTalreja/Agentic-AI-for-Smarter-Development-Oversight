<<<<<<< HEAD
# Agentic Infra Analyst

An AI-powered agentic system for querying, auditing, and reviewing infrastructure project data.

## Project Structure

```
agentic-infra-analyst/
├── core/          # Data loaders, LLM client, tools, and utilities
├── agents/        # Query, Audit, and Review Board agent implementations
├── db/            # SQLAlchemy models, database config, and seed data
├── backend/       # FastAPI application and API routes
├── frontend/      # Vite + React frontend
├── tests/         # Pytest test suite
├── data/          # Default data directory (add Projects.xlsx manually)
└── docs/          # Architecture diagrams and documentation
```

## Getting Started

1. Copy `.env.example` to `.env` and fill in your API keys.
2. Install Python dependencies: `pip install -r requirements.txt`
3. Install frontend dependencies: `cd frontend && npm install`
4. Run the backend: `uvicorn backend.main:app --reload`
5. Run the frontend: `cd frontend && npm run dev`

## Agents

| Agent | Description |
|-------|-------------|
| **Query Agent** | Answers natural-language questions over structured project data |
| **Audit Agent** | Detects data quality issues and policy violations |
| **Review Board** | Multi-agent panel that synthesises findings from sub-agents |

## License

See [LICENSE](LICENSE).
=======
# Agentic-AI-for-Smarter-Development-Oversight
Agentic AI-powered platform for BSDI project intelligence, auditing, monitoring, and transparent development decision support.
>>>>>>> 5243bb1a3aa18fccf02e081e66dd2b8ab0c9ebca
