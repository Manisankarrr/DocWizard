import ast
from typing import Dict, List, Any


def parse_python_file(filename: str, content: str) -> Dict[str, List[Any]]:
    """
    Parses a Python file and extracts functions, classes, and imports.
    
    Args:
        filename: The name of the Python file
        content: The content of the Python file as a string
    
    Returns:
        Dict with keys 'functions', 'classes', and 'imports'.
        Each function/class dict contains 'name' and 'docstring'.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Syntax error in {filename}: {e}")
        return {'functions': [], 'classes': [], 'imports': []}
    
    functions = []
    classes = []
    imports = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            docstring = ast.get_docstring(node)
            functions.append({
                'name': node.name,
                'docstring': docstring
            })
        elif isinstance(node, ast.ClassDef):
            docstring = ast.get_docstring(node)
            classes.append({
                'name': node.name,
                'docstring': docstring
            })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                if module:
                    imports.append(f"from {module} import {alias.name}")
                else:
                    imports.append(f"import {alias.name}")
    
    return {
        'functions': functions,
        'classes': classes,
        'imports': imports
    }
