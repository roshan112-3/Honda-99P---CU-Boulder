"""
Setup script for Tree-sitter language parsers.
Downloads and builds C++ and Python grammars.

Run this once before using analyze.py
"""
import os
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent
PARSERS_DIR = TOOLS_DIR / "parsers"
BUILD_DIR = TOOLS_DIR / "build"

GRAMMARS = {
    "cpp": "https://github.com/tree-sitter/tree-sitter-cpp",
    "python": "https://github.com/tree-sitter/tree-sitter-python"
}


def setup_parsers():
    """Download grammar repos and build the shared library."""
    
    # Create directories
    PARSERS_DIR.mkdir(exist_ok=True)
    BUILD_DIR.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("TREE-SITTER PARSER SETUP")
    print("=" * 60)
    
    # Clone grammar repositories
    for lang, url in GRAMMARS.items():
        dest = PARSERS_DIR / f"tree-sitter-{lang}"
        if dest.exists():
            print(f"[OK] {lang} grammar already exists at {dest}")
        else:
            print(f"[DOWNLOAD] Cloning {lang} grammar from {url}...")
            subprocess.run(["git", "clone", url, str(dest)], check=True)
            print(f"[OK] {lang} grammar downloaded")
    
    # Build the shared library
    print("\n[BUILD] Building language library...")
    
    try:
        from tree_sitter import Language
        
        Language.build_library(
            str(BUILD_DIR / "languages.so"),
            [
                str(PARSERS_DIR / "tree-sitter-cpp"),
                str(PARSERS_DIR / "tree-sitter-python")
            ]
        )
        print(f"[OK] Built library at {BUILD_DIR / 'languages.so'}")
        
    except Exception as e:
        print(f"[ERROR] Build failed: {e}")
        print("\nTrying alternative build method...")
        
        # Alternative: use .dll on Windows
        try:
            Language.build_library(
                str(BUILD_DIR / "languages.dll"),
                [
                    str(PARSERS_DIR / "tree-sitter-cpp"),
                    str(PARSERS_DIR / "tree-sitter-python")
                ]
            )
            print(f"[OK] Built library at {BUILD_DIR / 'languages.dll'}")
        except Exception as e2:
            print(f"[ERROR] Alternative build also failed: {e2}")
            sys.exit(1)
    
    print("\n" + "=" * 60)
    print("SETUP COMPLETE!")
    print("You can now run: python analyze.py")
    print("=" * 60)


if __name__ == "__main__":
    setup_parsers()
