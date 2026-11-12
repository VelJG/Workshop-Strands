# Workshop Demo Implementation Plan

> Historical Workshop2 planning note copied for reference. The current Workshop Strands runtime and presentation are documented in the root README and SPEAKER_SCRIPT.md; this is not the active implementation plan.

**Goal:** Rehearse the prototype-to-container story without credentials; offer opt-in live RAG.
**Architecture:** One LangGraph workflow proposes actions; FastAPI and SQLite own approval and ticket writes.
**Stack:** Python, FastAPI, LangGraph, SQLite, Docker; optional OpenAI and FAISS.

- [x] Write API acceptance tests: grounding, pending action, deny, replay, restart, identity and bounded input. Run red.
- [x] Implement named teaching components and run the tests green.
- [x] Verify the presenter CLI against a local server. Package the same app for Docker.
- [x] Document the AWS target, four pillars, and ordered AgentCore comparison. Do not provision anything.
- [ ] Rehearse Docker on a host with Docker and optionally test a real model provider with the presenter's account.

