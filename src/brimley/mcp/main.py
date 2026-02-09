import sys
import os
import logging
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

import typer
from dotenv import load_dotenv

# Import core Brimley components
# Logic handles import paths if installed or running from source
try:
    from brimley.core import BrimleyEngine
    from brimley.mcp.adapter import BrimleyMCPAdapter
    from fastmcp import FastMCP
except ImportError:
    # If not installed, these might fail. 
    # In a real installed scenario, dependencies are guaranteed.
    pass

# Load .env file explicitly before defining Typer app
# This allows Typer to pick up env vars automatically if configured,
# but we are defining them manually in Annotated options for clarity.
load_dotenv()

app = typer.Typer(
    help="Brimley MCP Server - Expose local SQL and tools to AI agents."
)

def configure_logging(debug: bool):
    """
    Configures logging to output strictly to stderr.
    This is CRITICAL for MCP servers, as stdout is used for the protocol.
    """
    level = logging.DEBUG if debug else logging.INFO
    format_str = "%(levelname)s: %(message)s"
    
    # Remove all existing handlers to be safe
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)
            
    logging.basicConfig(
        level=level,
        format=format_str,
        stream=sys.stderr  # FORCE stderr
    )

@app.command()
def start(
    db_path: Annotated[
        Path, 
        typer.Option(
            "--db-path", "-d",
            envvar="BRIMLEY_DB_PATH",
            help="Path to the SQLite database file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        )
    ],
    tools_dir: Annotated[
        Path,
        typer.Option(
            "--tools-dir", "-t",
            envvar="BRIMLEY_TOOLS_DIR",
            help="Path to the directory containing tool definitions.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
        )
    ],
    extensions_file: Annotated[
        Optional[Path],
        typer.Option(
            "--extensions-file", "-e",
            envvar="BRIMLEY_EXTENSIONS_FILE",
            help="Path to a Python file containing custom extensions.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        )
    ] = None,
    name: Annotated[
        str,
        typer.Option(
            "--name", "-n",
            envvar="BRIMLEY_SERVER_NAME",
            help="Name of the MCP server.",
        )
    ] = "Brimley Server",
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable debug logging to stderr.",
        )
    ] = False,
):
    """
    Start the MCP server.
    """
    configure_logging(debug)
    logger = logging.getLogger("brimley.mcp")
    
    logger.info(f"Starting server '{name}'")
    logger.debug(f"DB Path: {db_path}")
    logger.debug(f"Tools Dir: {tools_dir}")
    
    if extensions_file:
         logger.info(f"Loading extensions from: {extensions_file}")
    
    try:
        # Initialize Brimley Engine
        # We assume BrimleyEngine handles extensions file loading if passed string
        engine = BrimleyEngine(
            tools_dir=str(tools_dir),
            db_path=str(db_path),
            extensions_file=str(extensions_file) if extensions_file else None
        )
        
        # Initialize FastMCP
        mcp = FastMCP(name)
        
        # Create Adapter and Register Tools
        adapter = BrimleyMCPAdapter(engine, mcp)
        count = adapter.register_tools()
        
        logger.info(f"Registered {count} tools successfully.")
        
        # Run the server
        # This blocks until the process is killed
        mcp.run()
        
    except Exception as e:
        logger.critical(f"Server failed to start: {e}", exc_info=debug)
        sys.exit(1)

if __name__ == "__main__":
    app()
