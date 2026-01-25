from typing import Dict, Any, List, Union
from brimley.schemas import ToolDefinition, ReturnType
from brimley.backend.sqlite import SQLiteConnection
import sqlite3
import sys
import json

def run_local_sql(tool_def: ToolDefinition, validated_args: Dict[str, Any], db_path: str) -> Any:
    """
    Executes a SQL-based tool against the local SQLite database.

    Args:
        tool_def: The tool definition.
        validated_args: The arguments (already validated and casted).
        db_path: Path to the SQLite database file.

    Returns:
        The result of the execution formatted according to return_shape.
    """
    if not tool_def.implementation.sql_template:
        raise ValueError(f"Tool {tool_def.tool_name} is missing sql_template.")

    sql_query = "\n".join(tool_def.implementation.sql_template)
    rt = tool_def.return_shape.type

    with SQLiteConnection(db_path) as conn:
        cursor = conn.cursor()
        # Debug: log the SQL and bound parameters to stderr (keeps MCP stdio clean)
        try:
            debug_params = json.dumps(validated_args, default=str)
        except Exception:
            debug_params = str(validated_args)
        print(f"DEBUG SQL:\n{sql_query}\nBINDINGS: {debug_params}", file=sys.stderr)

        cursor.execute(sql_query, validated_args)
        
        result: Any = None

        # Fetch Logic
        if rt == ReturnType.TABLE:
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            
        elif rt == ReturnType.RECORD:
            row = cursor.fetchone()
            if row:
                result = dict(row)
            else:
                result = None
                
        elif rt == ReturnType.VALUE:
            row = cursor.fetchone()
            if row:
                # Get the first column
                result = row[0]
            else:
                result = None
                
        elif rt == ReturnType.LIST:
            rows = cursor.fetchall()
            # List of first column
            result = [row[0] for row in rows]
            
        elif rt == ReturnType.VOID:
            # For VOID, we might want to return rows affected
            result = {"rows_affected": cursor.rowcount}

        # Commit Logic
        # If it's a write operation, we must commit. 
        # SQLite determines 'write' by SQL content usually, but safe to always commit if we are done fetching?
        # Committing a pure SELECT is harmless (no-op or commits read transaction).
        conn.commit()
        
        return result

