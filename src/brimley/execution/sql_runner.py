import sys
from typing import Any, Dict
from sqlalchemy import text
from brimley.core.models import SqlFunction
from brimley.core.context import BrimleyContext
from brimley.execution.arguments import ArgumentResolver
from brimley.execution.result_mapper import ResultMapper

class SqlRunner:
    """
    Executes SqlFunctions against a database connection using SQLAlchemy.
    """

    def run(self, func: SqlFunction, args: Dict[str, Any], context: BrimleyContext) -> Any:
        """
        Prepares arguments and executes the SQL query.
        """
        # 1. Resolve Arguments (merges user input, context, defaults)
        resolved_params = ArgumentResolver.resolve(func, args, context)
        
        # 2. Get Engine
        connection_name = func.connection
        engine = context.databases.get(connection_name)

        if not engine:
            avail = list(context.databases.keys())
            raise RuntimeError(f"Database connection '{connection_name}' not found. Available: {avail}")

        # 3. Execute
        with engine.connect() as conn:
            stmt = text(func.sql_body)
            result = conn.execute(stmt, resolved_params)
        
            # Check if it returns rows
            if result.returns_rows:
                # Return list of dicts
                raw_rows = [dict(row) for row in result.mappings()]
                return ResultMapper.map_result(raw_rows, func, context)
            else:
                # Commit for INSERT/UPDATE/DELETE if auto-commit isn't on by default
                conn.commit()
                # If the shape is void, we return None as per ResultMapper logic
                if func.return_shape == "void" or not func.return_shape:
                    return ResultMapper.map_result(None, func, context)
                # Otherwise, if they expected something else (like dict), return the rowcount
                return ResultMapper.map_result({"rows_affected": result.rowcount}, func, context)
