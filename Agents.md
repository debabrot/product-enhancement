## Project Overview
This project demonstrates an agentic workflow for enriching product data using:
- user-provided context
- external information sources
- LLM-powered enrichment

The project is intended as a Proof of Concept (POC) and not for production usage.

The system should accept partially complete product information and generate improved structured product data.

## PRD
/docs/PRD.md

## Architecture
/docs/architecture/overview.md

## Stack
Python 3.11, FastAPI, LangGraph, LangChain, Streamlit, Pydantic v2

## Rules (always enforce these)
- Route handlers must remain thin
- Business logic belongs in services/workflows only
- Repository layer handles data access only
- Typed returns everywhere — no `Any`
- Raise domain exceptions from `src/exceptions.py`
- Never return error dicts
- Use structlog, never print()
- No new dependencies without approval
- Prefer simple implementations over premature abstractions
- Build features incrementally using thin vertical slices

## Tests
- pytest, 80% coverage minimum
- Unit tests for service methods, integration tests for API routes

## Current Scope
Current implementation supports:
- single enrichment workflow
- user-provided context
- structured response generation

Not yet implemented:
- multi-agent orchestration
- vector databases
- human review
- persistent storage