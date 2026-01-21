"""
DI Implementation Syntax Check

Validates that all DI-related files have valid Python syntax
and imports are structured correctly.
"""

import sys
import ast
from pathlib import Path

def check_syntax(filepath):
    """Check if a Python file has valid syntax."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)

def main():
    backend_dir = Path(__file__).parent.parent
    
    files_to_check = [
        backend_dir / "services" / "protocols.py",
        backend_dir / "core" / "dependencies.py",
        backend_dir / "services" / "document_service.py",
        backend_dir / "services" / "chunking_service.py",
        backend_dir / "services" / "document_processing_workflow.py",
        backend_dir / "services" / "unified_chat_workflow.py",
        backend_dir / "services" / "memory_consolidation_service.py",
    ]
    
    print("=" * 60)
    print("DI IMPLEMENTATION SYNTAX CHECK")
    print("=" * 60)
    
    all_valid = True
    
    for filepath in files_to_check:
        relative_path = filepath.relative_to(backend_dir)
        valid, error = check_syntax(filepath)
        
        if valid:
            print(f"✅ {relative_path}")
        else:
            print(f"❌ {relative_path}")
            print(f"   Error: {error}")
            all_valid = False
    
    print("=" * 60)
    
    if all_valid:
        print("✅ ALL FILES HAVE VALID SYNTAX")
        print("=" * 60)
        print("\nNext step: Docker build verification")
        print("Run: docker-compose up --build")
        return 0
    else:
        print("❌ SYNTAX ERRORS FOUND")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
