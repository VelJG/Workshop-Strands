"""FastAPI transport for the bounded Strands multi-agent workflow."""
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
import sqlite3
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from langchain_core.runnables.graph_mermaid import draw_mermaid_png
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .identity import presenter_gate
from .memory import CapacityReached, Store
from .observability import LimitBody, event, request_log
from .policy import DecisionConflict
from .tools import ProviderUnavailable


class Chat(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    message: str = Field(min_length=1, max_length=1500)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: StrictBool


def architecture_mermaid():
    """Schematic of the Strands graph plus each specialist's internal tool loop."""
    return """flowchart TB
    START([User]) --> API[FastAPI]
    API --> ROUTER[Strands router]
    ROUTER -. qa .-> QA[qa_agent]
    ROUTER -. ticket .-> TICKET[ticket_agent]
    ROUTER -. research .-> RESEARCH[research_agent]
    QA --> POLICY[search_policy / FAISS]
    POLICY --> QA
    TICKET --> DRAFT[draft_ticket]
    DRAFT --> TICKET
    RESEARCH --> WEB[search_web / Tavily]
    WEB --> RESEARCH
    QA --> RESULT[API response]
    RESEARCH --> RESULT
    TICKET --> APPROVAL[FastAPI approval gate]
    APPROVAL --> RESULT
    """


def save_graph_visualization(output: Path) -> Path:
    """Render an architecture schematic without calling model or search providers."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(draw_mermaid_png(architecture_mermaid()))
    return output


def create_app(db: Path, *, agents_factory, token=None, hosted=False, ticket_notifier=None,
               trace_client=None):
    gate = presenter_gate(token, hosted)
    store = Store(db)

    @asynccontextmanager
    async def lifespan(app):
        store.initialize()
        app.state.agents = agents_factory()
        try:
            yield
        finally:
            if trace_client is not None:
                trace_client.flush()

    app = FastAPI(title="Mini Enterprise AI Support Agent", lifespan=lifespan,
                  docs_url=None if hosted else "/docs",
                  redoc_url=None, openapi_url=None if hosted else "/openapi.json")
    app.add_middleware(LimitBody, limit=8192)
    app.middleware("http")(request_log)

    if not hosted and not token:
        static = Path(__file__).resolve().parent / "static"

        @app.get("/", include_in_schema=False)
        def chat_page():
            return FileResponse(static / "index.html", headers={"Cache-Control": "no-store"})

        @app.get("/ui.js", include_in_schema=False)
        def chat_script():
            return FileResponse(static / "ui.js", media_type="text/javascript",
                                headers={"Cache-Control": "no-store"})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/chat", dependencies=[Depends(gate)])
    def chat(body: Chat, request: Request):
        try:
            trace = (trace_client.start_as_current_observation(
                name="workshop.chat", metadata={"request_id": request.state.request_id})
                if trace_client is not None else nullcontext())
            with trace:
                result = request.app.state.agents.run(body.message)
            if "draft" not in result:
                return {"kind": "answer", "agent": result["agent"],
                        "answer": result["answer"], "sources": result.get("sources", []),
                        "citations": result.get("citations", [])}
            draft = result["draft"]
            approval = store.propose(draft.content, title=draft.title,
                                     category=draft.category, priority=draft.priority)
        except ProviderUnavailable:
            event("provider_unavailable", request_id=request.state.request_id)
            raise HTTPException(503, "AI or search provider unavailable. Check server logs and retry.") from None
        except CapacityReached:
            raise HTTPException(503, "Ticket store is full; use a fresh database.") from None
        except sqlite3.OperationalError:
            raise HTTPException(503, "Ticket store unavailable.") from None
        event("approval_requested", request_id=request.state.request_id, approval_id=approval)
        return {"kind": "approval_required", "agent": "ticket",
                "approval_id": approval, "draft": draft.model_dump()}

    @app.post("/approvals/{approval_id}", dependencies=[Depends(gate)])
    def approval(approval_id: UUID, body: Decision, request: Request):
        try:
            result, newly_approved = store.decide(str(approval_id), body.approve)
        except DecisionConflict as exc:
            raise HTTPException(409, str(exc)) from None
        except sqlite3.OperationalError:
            raise HTTPException(503, "Ticket store unavailable.") from None
        if result is None:
            raise HTTPException(404, "Approval not found.")
        if newly_approved and ticket_notifier is not None:
            try:
                ticket_notifier(result)
                event("ticket_notification_sent", request_id=request.state.request_id,
                      ticket_ref=result["ticket_ref"])
            except Exception:
                event("ticket_notification_failed", request_id=request.state.request_id,
                      ticket_ref=result["ticket_ref"])
        event("approval_decided", request_id=request.state.request_id,
              approval_id=str(approval_id), decision=result["status"])
        return result

    @app.get("/tickets/{ticket_id}", dependencies=[Depends(gate)])
    def ticket(ticket_id: UUID):
        try:
            result = store.ticket(str(ticket_id))
        except sqlite3.OperationalError:
            raise HTTPException(503, "Ticket store unavailable.") from None
        if result is None:
            raise HTTPException(404, "Ticket not found.")
        return result

    @app.get("/tickets", dependencies=[Depends(gate)])
    def tickets():
        try:
            return store.list_tickets()
        except sqlite3.OperationalError:
            raise HTTPException(503, "Ticket store unavailable.") from None

    return app
