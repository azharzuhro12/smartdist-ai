"""
Safe Text-to-SQL Tool for SmartDist AI Assistant.
Executes natural language queries against PostgreSQL with strict validation and provenance.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ai_assistant.sql_agent.nl_to_sql import NLToSQLAgent


class SafeSQLTool:
    """Tool for querying the database via natural language to SQL."""

    name = "safe_sql_agent"
    description = "Executes safe, read-only analytical SQL queries over sales, inventory, branches, suppliers, and anomalies."

    def __init__(self, agent: Optional[NLToSQLAgent] = None):
        self.agent = agent or NLToSQLAgent()

    def execute_natural_query(self, natural_language_query: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Translates and safely executes an analytical question."""
        return self.agent.query(natural_language_query, db=db)

