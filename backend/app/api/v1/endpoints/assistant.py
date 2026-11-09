"""
FastAPI endpoints for SmartDist AI Business Assistant.
Exposes chat, Safe Text-to-SQL, RAG policy lookup, and workflow orchestration.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import require_analyst
from backend.app.core.config import settings
from backend.app.core.rate_limit import check_rate_limit, get_client_ip
from backend.app.models.user import User
from backend.app.db.session import get_db, get_readonly_db
from ai_assistant.orchestrator import AIAssistantOrchestrator
from ai_assistant.sql_agent.nl_to_sql import NLToSQLAgent
from ai_assistant.rag.retriever import RAGRetriever

router = APIRouter()
orchestrator = AIAssistantOrchestrator()
sql_agent = NLToSQLAgent()
rag_retriever = RAGRetriever()


class ChatRequest(BaseModel):
    query: str = Field(..., description="Natural language prompt or operational question")
    conversation_id: Optional[str] = Field(None, description="Optional conversation tracking ID")


class ChatResponse(BaseModel):
    query: str
    intent: str
    answer: str
    tool_used: str
    citations: List[str] = []
    data: Optional[Any] = None
    provenance: str


class WorkflowRequest(BaseModel):
    workflow_name: str = Field(..., description="Name of business workflow (e.g. executive_briefing, replenishment_explanation)")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Workflow parameters")


class SafeSQLRequest(BaseModel):
    query: str = Field(..., description="Natural language question to translate to SQL and execute")


class PolicySearchRequest(BaseModel):
    query: str = Field(..., description="Query for SOP and policy knowledge base")
    top_k: int = Field(3, ge=1, le=10, description="Number of policy passages to retrieve")


@router.post("/chat", response_model=ChatResponse, summary="Chat with AI Business Assistant")
def chat_with_assistant(
    req: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    analyst: User = Depends(require_analyst),
):
    """Routes query through AI Assistant Orchestrator with tool invocation and grounded synthesis."""
    client_ip = get_client_ip(request)
    check_rate_limit(
        f"assistant:chat:{analyst.id}:{client_ip}",
        max_requests=settings.RATE_LIMIT_ASSISTANT_PER_MINUTE,
        window_seconds=60,
    )
    try:
        res = orchestrator.chat(query=req.query, conversation_id=req.conversation_id, db=db)
        return ChatResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Assistant failed to process query: {str(e)}")


@router.post("/workflow", summary="Execute automated business workflow")
def execute_business_workflow(
    req: WorkflowRequest,
    request: Request,
    db: Session = Depends(get_db),
    analyst: User = Depends(require_analyst),
):
    """Executes a multi-step workflow (executive briefing, replenishment explanation, anomaly investigation)."""
    client_ip = get_client_ip(request)
    check_rate_limit(
        f"assistant:workflow:{analyst.id}:{client_ip}",
        max_requests=settings.RATE_LIMIT_ASSISTANT_PER_MINUTE,
        window_seconds=60,
    )
    try:
        return orchestrator.execute_workflow(workflow_name=req.workflow_name, params=req.parameters, db=db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")


@router.get("/workflows", summary="List available business workflows")
def list_available_workflows():
    """Lists supported business workflows and parameter definitions."""
    return {
        "workflows": [
            {
                "id": "executive_briefing",
                "name": "Executive Daily Briefing",
                "description": "Synthesizes sales revenue drivers, operational anomalies, and critical inventory shortage risks into an executive summary.",
                "parameters": {},
            },
            {
                "id": "replenishment_explanation",
                "name": "Replenishment Decision Explanation",
                "description": "Deconstructs why an item requires replenishment, citing SOP-INV-001 service levels, ROP/SS calculations, and EOQ lot sizing.",
                "parameters": {
                    "product_id": "INTEGER (Product ID)",
                    "branch_id": "INTEGER (Branch Store ID)",
                },
            },
            {
                "id": "anomaly_root_cause",
                "name": "Anomaly Root Cause Investigation",
                "description": "Performs deep triage on a detected sales anomaly, comparing observed vs expected volume and mapping SOP-OPS-003 guidelines.",
                "parameters": {
                    "anomaly_id": "OPTIONAL INTEGER (defaults to latest high-severity anomaly)",
                },
            },
        ]
    }


@router.post("/sql", summary="Execute Safe Text-to-SQL query")
def execute_safe_sql(
    req: SafeSQLRequest,
    request: Request,
    db: Session = Depends(get_readonly_db),
    analyst: User = Depends(require_analyst),
):
    """Translates natural language to SQL, enforces strict SELECT safety and allowlists, and returns tabular results."""
    client_ip = get_client_ip(request)
    check_rate_limit(
        f"assistant:sql:{analyst.id}:{client_ip}",
        max_requests=settings.RATE_LIMIT_ASSISTANT_PER_MINUTE,
        window_seconds=60,
    )
    try:
        return sql_agent.query(req.query, db=db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SQL Query failed: {str(e)}")


@router.post("/policy-search", summary="Search SOP & Policy Knowledge Base (RAG)")
def search_policies(
    req: PolicySearchRequest,
    analyst: User = Depends(require_analyst),
):
    """Performs semantic similarity search over company SOPs, procurement policies, and operational rules."""
    try:
        results = rag_retriever.retrieve(req.query, top_k=req.top_k)
        return {
            "query": req.query,
            "passages": results,
            "citation_block": rag_retriever.format_citations_block(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy retrieval failed: {str(e)}")

