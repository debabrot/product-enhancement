# Architecture Overview

## Goal

Build a minimal Product Enrichment POC using:
- Streamlit frontend
- FastAPI backend
- Pydantic schemas
- Simple LangChain enrichment flow

The system should:
1. Accept a product selection
2. Accept external context text
3. Generate enriched product information
4. Return structured output

This is intentionally lightweight and not production-ready.

---

# High-Level Flow

Frontend (Streamlit)
    ->
FastAPI /enrich
    ->
Enrichment Service
    ->
LangChain Bot
    ->
Structured Response

---

# Project Structure

/app
  main.py
  dependencies.py

  /core
    config.py

  /api
    enrich.py

  /services
    enrichment_service.py

  /schemas
    enrich.py

  /agents
    enrichment_agent.py
  
  /llm
    provider.py

/frontend
  app.py

/data
  products.csv

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
/data/products.csv