from typing import Any, Dict
from brimley.core.models import SqlFunction
from brimley.core.context import BrimleyContext
from brimley.execution.arguments import ArgumentResolver

class SqlRunner:
    """
    Executes SqlFunctions against a database connection.
    Currently mocked to log output to stdout.
    """

    def run(self, func: SqlFunction, args: Dict[str, Any], context: BrimleyContext) -> Any:
        """
        Prepares arguments and 'executes' the SQL query.
        """
        # 1. Resolve Arguments (merges user input, context, defaults)
        resolved_params = ArgumentResolver.resolve(func, args, context)
        
        # 2. Identify Connection
        connection_name = func.connection

        # 3. Log execution (Mock behavior)
        print(f"[SQL Runner] Executing '{func.name}' on connection '{connection_name}'.")
        print(f"Query: {func.sql_body}")
        print(f"Params: {resolved_params}")

        # 4. Return mock result for verification
        return {
            "function": func.name,
            "connection": connection_name,
            "executed_sql": func.sql_body,
            "parameters": resolved_params,
            "mock_data": [] # In a real implementation, this would be rows
        }
