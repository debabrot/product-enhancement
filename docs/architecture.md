# Architecture Overview

## Goal

Build a minimal Product Enrichment POC using:
- Streamlit frontend
- FastAPI backend
- Pydantic schemas
- LangGraph enrichment flow

The system should:
1. Accept a product selection
2. Accept external context text
3. Generate enriched product information
4. Return structured output

This is intentionally lightweight and not production-ready.

---

# High-Level Flow

```text
Streamlit Frontend
        │
        ▼
FastAPI /enrich
        │
        ▼
Enrichment Service
        │
        ▼
LangGraph Workflow
        │
        ├── Retrieval Agent
        └── Enrichment Agent
        │
        ▼
Structured Enriched Output
```

---

# Project Structure

/app
  main.py
  dependencies.py
  exceptions.py

  /core
    config.py
    logging.py
    tracing.py

  /api
    enrich.py

  /services
    enrichment_service.py

  /schemas
    enrich.py

  /agents
    enrichment_agent.py
    retrieval_agent.py
  
  /llm
    provider.py

/frontend
  app.py
  /data
    demo_products.csv

---

# Frontend

The Streamlit frontend should contain:
- product dropdown
- multiline context textbox
- enrich button
- response display section

The frontend should call the backend `/enrich` endpoint.

---

# Dummy Product Data

Store sample products in:

```text
frontend/data/demo_products.csv