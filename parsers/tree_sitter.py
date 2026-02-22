"""
Tree-sitter Code Analyzer for Honda Repository
===============================================

This script parses all source files using Tree-sitter and extracts:
1. Functions and their locations
2. Function call relationships
3. Packet byte assignments (for HSI traceability)
4. Class/struct definitions

Output is structured for knowledge base creation.
"""
import os
import json
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set
from datetime import datetime

# ============================================================================
# DATA STRUCTURES (What we extract)
# ============================================================================

@dataclass
class FunctionInfo:
    """Information about a function/method"""
    name: str
    file: str
    line_start: int
    line_end: int
    language: str
    class_name: Optional[str] = None  # For methods
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    
    @property
    def full_name(self):
        if self.class_name:
            return f"{self.class_name}::{self.name}"
        return self.name


@dataclass  
class FunctionCall:
    """A function calling another function"""
    caller: str
    callee: str
    file: str
    line: int


@dataclass
class ByteAssignment:
    """Packet byte assignment (for HSI tracing)"""
    array_name: str
    index: str  # Can be number or expression
    value: str
    file: str
    line: int
    function: str


@dataclass
class ClassInfo:
    """Class or struct definition"""
    name: str
    file: str
    line_start: int
    line_end: int
    language: str
    members: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)


@dataclass
class Relationship:
    """Generic relationship for knowledge graph"""
    source: str
    relation: str
    target: str
    metadata: Dict = field(default_factory=dict)


# ============================================================================
# SIMPLIFIED PARSER (No external tree-sitter dependency)
# ============================================================================
# This version uses regex-based parsing for portability.
# For production, replace with actual tree-sitter parsing.

class CodeAnalyzer:
    """Analyzes source code and extracts structure."""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.functions: List[FunctionInfo] = []
        self.calls: List[FunctionCall] = []
        self.byte_assignments: List[ByteAssignment] = []
        self.classes: List[ClassInfo] = []
        self.relationships: List[Relationship] = []
        
    def analyze_all(self):
        """Analyze all source files in the repository."""
        print("\n" + "=" * 70)
        print("TREE-SITTER CODE ANALYSIS")
        print("=" * 70)
        
        # Find all source files (dataset lives under Data/)
        cpp_files = list((self.repo_root / "Data" / "firmware").glob("*.cpp"))
        cpp_headers = list((self.repo_root / "Data" / "firmware").glob("*.h"))
        py_files = list((self.repo_root / "Data" / "cloud").glob("*.py"))
        
        print(f"\nFound {len(cpp_files)} C++ files, {len(cpp_headers)} headers, {len(py_files)} Python files")
        
        # Analyze each file
        for f in cpp_files + cpp_headers:
            self._analyze_cpp_file(f)
            
        for f in py_files:
            self._analyze_python_file(f)
            
        # Build relationships
        self._build_relationships()
        
        print(f"\n[EXTRACTED]")
        print(f"  - {len(self.functions)} functions")
        print(f"  - {len(self.calls)} function calls")
        print(f"  - {len(self.byte_assignments)} byte assignments")
        print(f"  - {len(self.classes)} classes/structs")
        print(f"  - {len(self.relationships)} relationships")
        
    def _analyze_cpp_file(self, filepath: Path):
        """Parse a C++ file and extract functions, calls, etc."""
        print(f"  Parsing: {filepath.name}")
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        rel_path = str(filepath.relative_to(self.repo_root))
        current_function = None
        current_class = None
        brace_depth = 0
        func_start_line = 0
        
        # Pattern for C++ function definitions
        func_pattern = re.compile(
            r'^(?:static\s+)?'  # optional static
            r'(?:(?:inline|virtual|explicit)\s+)?'  # optional keywords
            r'([\w:<>*&\s]+?)\s+'  # return type
            r'((?:\w+::)?(\w+))\s*'  # class::name or just name
            r'\(([^)]*)\)'  # parameters
            r'\s*(?:const)?\s*(?:override)?\s*$'  # trailing qualifiers
        )
        
        # Pattern for class/struct
        class_pattern = re.compile(r'(?:class|struct)\s+(\w+)')
        
        # Pattern for function calls
        call_pattern = re.compile(r'(\w+(?:::\w+)?)\s*\(')
        
        # Pattern for array assignments: arr[index] = value
        byte_pattern = re.compile(r'(\w+)\[(\d+)\]\s*=\s*([^;]+);')
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Track brace depth for function boundaries
            brace_depth += line.count('{') - line.count('}')
            
            # Detect class/struct
            class_match = class_pattern.search(stripped)
            if class_match and '{' in stripped:
                current_class = class_match.group(1)
                self.classes.append(ClassInfo(
                    name=current_class,
                    file=rel_path,
                    line_start=i,
                    line_end=i,  # Will be updated
                    language="cpp"
                ))
            
            # Detect function definition
            if stripped and not stripped.startswith('//') and '(' in stripped and '{' in content[sum(len(l)+1 for l in lines[:i]):sum(len(l)+1 for l in lines[:i+2])]:
                func_match = func_pattern.match(stripped)
                if func_match:
                    return_type = func_match.group(1).strip()
                    full_name = func_match.group(2)
                    func_name = func_match.group(3)
                    params_str = func_match.group(4)
                    
                    # Determine class name if method
                    class_name = None
                    if '::' in full_name:
                        class_name = full_name.split('::')[0]
                    
                    params = [p.strip() for p in params_str.split(',') if p.strip()]
                    
                    func_info = FunctionInfo(
                        name=func_name,
                        file=rel_path,
                        line_start=i,
                        line_end=i,  # Will need more parsing to get exact end
                        language="cpp",
                        class_name=class_name,
                        parameters=params,
                        return_type=return_type
                    )
                    self.functions.append(func_info)
                    current_function = func_info.full_name
                    func_start_line = i
            
            # Detect function calls within functions
            if current_function:
                for call_match in call_pattern.finditer(stripped):
                    callee = call_match.group(1)
                    # Skip control structures and common non-functions
                    if callee not in ['if', 'for', 'while', 'switch', 'return', 'sizeof', 'static_cast', 'reinterpret_cast', 'const_cast', 'dynamic_cast']:
                        self.calls.append(FunctionCall(
                            caller=current_function,
                            callee=callee,
                            file=rel_path,
                            line=i
                        ))
            
            # Detect byte assignments
            for byte_match in byte_pattern.finditer(stripped):
                self.byte_assignments.append(ByteAssignment(
                    array_name=byte_match.group(1),
                    index=byte_match.group(2),
                    value=byte_match.group(3).strip(),
                    file=rel_path,
                    line=i,
                    function=current_function or "global"
                ))
                
    def _analyze_python_file(self, filepath: Path):
        """Parse a Python file and extract functions, calls, etc."""
        print(f"  Parsing: {filepath.name}")
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        rel_path = str(filepath.relative_to(self.repo_root))
        current_function = None
        current_class = None
        current_indent = 0
        
        # Patterns
        func_pattern = re.compile(r'^(\s*)def\s+(\w+)\s*\(([^)]*)\)')
        class_pattern = re.compile(r'^(\s*)class\s+(\w+)')
        call_pattern = re.compile(r'(\w+)\s*\(')
        byte_pattern = re.compile(r'(\w+)\[(\d+)\]\s*=\s*([^#\n]+)')
        
        for i, line in enumerate(lines, 1):
            # Detect class
            class_match = class_pattern.match(line)
            if class_match:
                indent = len(class_match.group(1))
                current_class = class_match.group(2)
                self.classes.append(ClassInfo(
                    name=current_class,
                    file=rel_path,
                    line_start=i,
                    line_end=i,
                    language="python"
                ))
            
            # Detect function
            func_match = func_pattern.match(line)
            if func_match:
                indent = len(func_match.group(1))
                func_name = func_match.group(2)
                params_str = func_match.group(3)
                params = [p.strip().split(':')[0].strip() for p in params_str.split(',') if p.strip()]
                
                # Determine if it's a method (inside a class)
                class_name = None
                if indent > 0 and current_class:
                    class_name = current_class
                
                func_info = FunctionInfo(
                    name=func_name,
                    file=rel_path,
                    line_start=i,
                    line_end=i,
                    language="python",
                    class_name=class_name,
                    parameters=params
                )
                self.functions.append(func_info)
                current_function = func_info.full_name
                current_indent = indent
            
            # Detect function calls
            if current_function:
                for call_match in call_pattern.finditer(line):
                    callee = call_match.group(1)
                    if callee not in ['if', 'for', 'while', 'print', 'range', 'len', 'int', 'str', 'list', 'dict', 'set', 'tuple', 'type', 'isinstance', 'hasattr', 'getattr']:
                        self.calls.append(FunctionCall(
                            caller=current_function,
                            callee=callee,
                            file=rel_path,
                            line=i
                        ))
            
            # Detect byte assignments
            for byte_match in byte_pattern.finditer(line):
                self.byte_assignments.append(ByteAssignment(
                    array_name=byte_match.group(1),
                    index=byte_match.group(2),
                    value=byte_match.group(3).strip(),
                    file=rel_path,
                    line=i,
                    function=current_function or "global"
                ))
    
    def _build_relationships(self):
        """Build relationships for knowledge graph."""
        
        # Function DEFINED_IN file
        for func in self.functions:
            self.relationships.append(Relationship(
                source=func.full_name,
                relation="DEFINED_IN",
                target=func.file,
                metadata={"line": func.line_start, "language": func.language}
            ))
        
        # Function CALLS function
        for call in self.calls:
            self.relationships.append(Relationship(
                source=call.caller,
                relation="CALLS",
                target=call.callee,
                metadata={"file": call.file, "line": call.line}
            ))
        
        # Byte assignments IMPLEMENTS HSI
        hsi_mapping = {
            "0": "version",
            "1": "sensor_id", 
            "2": "temperature_raw_high",
            "3": "temperature_raw_low",
            "4": "pressure_raw_high",
            "5": "pressure_raw_low",
            "6": "humidity_raw_high",
            "7": "humidity_raw_low",
            "8": "fuel_raw_high",
            "9": "fuel_raw_low",
            "10": "status_flags",
            "11": "checksum"
        }
        
        for ba in self.byte_assignments:
            if ba.array_name == "pkt" and ba.index in hsi_mapping:
                self.relationships.append(Relationship(
                    source=ba.function,
                    relation="IMPLEMENTS_HSI",
                    target=f"SENSOR_PKT.{hsi_mapping[ba.index]}",
                    metadata={"file": ba.file, "line": ba.line, "value": ba.value}
                ))
        
        # Method BELONGS_TO class
        for func in self.functions:
            if func.class_name:
                self.relationships.append(Relationship(
                    source=func.full_name,
                    relation="BELONGS_TO",
                    target=func.class_name,
                    metadata={"file": func.file}
                ))


# ============================================================================
# OUTPUT FORMATTERS
# ============================================================================

def generate_knowledge_base_output(analyzer: CodeAnalyzer) -> dict:
    """Generate structured output suitable for knowledge base."""
    
    # Group functions by file
    functions_by_file = {}
    for func in analyzer.functions:
        if func.file not in functions_by_file:
            functions_by_file[func.file] = []
        functions_by_file[func.file].append({
            "name": func.full_name,
            "line": func.line_start,
            "parameters": func.parameters,
            "return_type": func.return_type
        })
    
    # Build call graph
    call_graph = {}
    for call in analyzer.calls:
        if call.caller not in call_graph:
            call_graph[call.caller] = set()
        call_graph[call.caller].add(call.callee)
    
    # Convert sets to lists for JSON
    call_graph = {k: list(v) for k, v in call_graph.items()}
    
    # HSI traceability
    hsi_trace = {}
    for rel in analyzer.relationships:
        if rel.relation == "IMPLEMENTS_HSI":
            if rel.target not in hsi_trace:
                hsi_trace[rel.target] = []
            hsi_trace[rel.target].append({
                "function": rel.source,
                "file": rel.metadata.get("file"),
                "line": rel.metadata.get("line"),
                "value": rel.metadata.get("value")
            })
    
    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "repo": "Honda Automotive Dataset",
            "analyzer": "Tree-sitter Code Analyzer v1.0"
        },
        "summary": {
            "total_functions": len(analyzer.functions),
            "total_classes": len(analyzer.classes),
            "total_calls": len(analyzer.calls),
            "total_relationships": len(analyzer.relationships)
        },
        "functions_by_file": functions_by_file,
        "call_graph": call_graph,
        "hsi_traceability": hsi_trace,
        "classes": [asdict(c) for c in analyzer.classes],
        "relationships": [asdict(r) for r in analyzer.relationships]
    }


def print_human_readable_report(analyzer: CodeAnalyzer):
    """Print a human-readable report."""
    
    print("\n")
    print("=" * 70)
    print("                    KNOWLEDGE BASE EXTRACTION REPORT")
    print("=" * 70)
    
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("SECTION 1: ALL FUNCTIONS")
    print("-" * 70)
    
    # Group by file
    by_file = {}
    for func in analyzer.functions:
        if func.file not in by_file:
            by_file[func.file] = []
        by_file[func.file].append(func)
    
    for file, funcs in sorted(by_file.items()):
        print(f"\n  [{file}]")
        for func in funcs:
            params = ", ".join(func.parameters[:3])
            if len(func.parameters) > 3:
                params += ", ..."
            ret = f" -> {func.return_type}" if func.return_type else ""
            print(f"    Line {func.line_start:3d}: {func.full_name}({params}){ret}")
    
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("SECTION 2: FUNCTION CALL GRAPH (Who calls whom)")
    print("-" * 70)
    
    call_graph = {}
    for call in analyzer.calls:
        if call.caller not in call_graph:
            call_graph[call.caller] = set()
        call_graph[call.caller].add(call.callee)
    
    for caller, callees in sorted(call_graph.items()):
        print(f"\n  {caller}")
        for callee in sorted(callees):
            print(f"    └── calls → {callee}")
    
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("SECTION 3: HSI TRACEABILITY (Code ↔ Specification)")
    print("-" * 70)
    
    print("\n  SENSOR_PKT v3 (12 bytes) Implementation:")
    print("  " + "─" * 50)
    
    hsi_fields = {
        "0": ("version", "byte 0"),
        "1": ("sensor_id", "byte 1"),
        "2": ("temperature_raw (high)", "byte 2"),
        "3": ("temperature_raw (low)", "byte 3"),
        "4": ("pressure_raw (high)", "byte 4"),
        "5": ("pressure_raw (low)", "byte 5"),
        "6": ("humidity_raw (high)", "byte 6"),
        "7": ("humidity_raw (low)", "byte 7"),
        "8": ("fuel_raw (high)", "byte 8"),
        "9": ("fuel_raw (low)", "byte 9"),
        "10": ("status_flags", "byte 10"),
        "11": ("checksum (CRC-8)", "byte 11"),
    }
    
    for ba in analyzer.byte_assignments:
        if ba.array_name == "pkt" and ba.index in hsi_fields:
            field_name, byte_pos = hsi_fields[ba.index]
            print(f"    HSI: {byte_pos:8s} = {field_name:25s}")
            print(f"    Code: pkt[{ba.index}] = {ba.value:20s}  @ {ba.file}:{ba.line}")
            print(f"    Function: {ba.function}")
            print("    Status: ✓ IMPLEMENTED")
            print()
    
    # -------------------------------------------------------------------------
    print("-" * 70)
    print("SECTION 4: CLASSES AND THEIR METHODS")
    print("-" * 70)
    
    # Group methods by class
    class_methods = {}
    for func in analyzer.functions:
        if func.class_name:
            if func.class_name not in class_methods:
                class_methods[func.class_name] = []
            class_methods[func.class_name].append(func.name)
    
    for cls_name, methods in sorted(class_methods.items()):
        print(f"\n  class {cls_name}:")
        for method in methods:
            print(f"    ├── {method}()")
    
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("SECTION 5: RELATIONSHIP SUMMARY")
    print("-" * 70)
    
    rel_counts = {}
    for rel in analyzer.relationships:
        rel_counts[rel.relation] = rel_counts.get(rel.relation, 0) + 1
    
    print("\n  Relationship Types Extracted:")
    for rel_type, count in sorted(rel_counts.items()):
        print(f"    {rel_type:20s}: {count:4d} instances")
    
    print("\n" + "=" * 70)
    print("END OF REPORT")
    print("=" * 70)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for the analyzer."""
    
    # Find repo root (parent of parsers directory)
    parsers_dir = Path(__file__).parent
    repo_root = parsers_dir.parent
    
    print(f"Repository root: {repo_root}")
    
    # Create analyzer and run
    analyzer = CodeAnalyzer(repo_root)
    analyzer.analyze_all()
    
    # Print human-readable report
    print_human_readable_report(analyzer)
    
    # Generate JSON output for knowledge base
    output = generate_knowledge_base_output(analyzer)
    
    output_file = parsers_dir / "ast_knowledge_base.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n[OUTPUT] Knowledge base saved to: {output_file}")
    print("\nThis JSON file can be imported into:")
    print("  - Neo4j (graph database)")
    print("  - Elasticsearch (search)")
    print("  - Any knowledge graph system")


if __name__ == "__main__":
    main()
