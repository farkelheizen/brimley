import sys
from pathlib import Path

# Add source directory to sys.path for local development testing
CURRENT_DIR = Path(__file__).parent.resolve()
SRC_PATH = CURRENT_DIR.parent.parent / "src"
if SRC_PATH.exists() and str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from brimley.mcp.main import app
from typer.main import get_command

# This script is now just a wrapper around the standard brimley-mcp CLI.
# In a real deployment, you would just install the package and run 'brimley-mcp'.

if __name__ == "__main__":
    # We can inject default arguments if we want this script to be "zero config"
    # for this specific example folder.
    
    # Check if user provided args. If not, provide defaults for this example.
    if len(sys.argv) == 1:
        print("Running with default example arguments...", file=sys.stderr)
        sys.argv.extend([
            "start",
            "--db-path", str(CURRENT_DIR / "demo.db"),
            "--tools-dir", str(CURRENT_DIR / "tools"),
            "--extensions-file", str(CURRENT_DIR / "extensions.py"),
            "--name", "Brimley Demo Server"
        ])
    
    app()
