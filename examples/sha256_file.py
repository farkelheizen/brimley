"""
---
name: sha256_file
type: python_function
description: "Calculates SHA256 hash of a file."
arguments:
  inline:
    filepath: { type: string }
return_shape: string
mcp:
  type: tool
---
"""
import hashlib
def sha256_file(filepath: str) -> str:
    """Calculates SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read in chunks to avoid memory issues with large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()