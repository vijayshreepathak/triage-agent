"""Symptom Triage Agent.

Clean Architecture layout — each package has exactly one responsibility:

- ``api``      HTTP layer. Validates requests, calls the graph. Zero business logic.
- ``graph``    LangGraph orchestration. Owns wiring and routing, not logic.
- ``nodes``    One node = one responsibility. All triage logic lives here.
- ``models``   Internal domain models (GraphState, clinical signals, traces).
- ``prompts``  Prompt templates. Prompts never live inside node code.
- ``tools``    External integrations behind interfaces (search, LLM providers).
- ``services`` Reusable business logic shared by nodes (red-flag engine, scoring).
- ``config``   Settings, constants, scoring weights. No magic numbers elsewhere.
- ``utils``    Cross-cutting helpers (structured logging, timing, retries).
- ``schemas``  API request/response contracts (external validation boundary).
"""
