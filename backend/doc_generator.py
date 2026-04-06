import os
import time
import requests
from typing import Dict, List, Any
from openai import OpenAI
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# LLM model with environment variable override
MODEL = os.getenv("LLM_MODEL", "qwen/qwen3-coder:free")


def generate_docs_for_repo(parsed_files: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Generates Markdown documentation for an entire repository in a SINGLE API call.
    
    Args:
        parsed_files: List of dicts, each with keys:
            - 'filename': str (the file path)
            - 'parsed_data': dict with 'functions', 'classes', 'imports' from parser.py
    
    Returns:
        Dict mapping filename -> markdown documentation string
    """
    if not parsed_files:
        return {}
    
    # Get API key from environment
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")
    
    # Initialize OpenAI client with OpenRouter base URL
    client = OpenAI(
        api_key=api_key,
        base_url='https://openrouter.ai/api/v1'
    )
    
    # Build ONE comprehensive prompt for all files
    files_summary = []
    for file_item in parsed_files:
        filename = file_item['filename']
        parsed_data = file_item['parsed_data']
        
        functions_text = "\n".join([
            f"  - {func['name']}(): {func['docstring'] or 'No docstring'}"
            for func in parsed_data.get('functions', [])
        ])
        
        classes_text = "\n".join([
            f"  - {cls['name']}: {cls['docstring'] or 'No docstring'}"
            for cls in parsed_data.get('classes', [])
        ])
        
        imports_text = "\n".join([
            f"  - {imp}"
            for imp in parsed_data.get('imports', [])
        ])
        
        file_summary = f"""### File: {filename}
Functions:
{functions_text or "  None"}

Classes:
{classes_text or "  None"}

Imports:
{imports_text or "  None"}
"""
        files_summary.append(file_summary)
    
    # Single comprehensive prompt with detailed formatting instructions
    combined_prompt = f"""You are a professional code documentation expert. I have a Python repository with {len(parsed_files)} file(s) to document.

For EACH file below, write RICH, DETAILED Markdown documentation following this EXACT structure:

## filename.py
### Overview
[ONE LINE SUMMARY: What this file does in plain English]

### Key Components
[CREATE A TABLE with columns: Name | Type | Purpose | Parameters]
[Include ALL important functions and classes]
[Format: | function_name() | Function | Brief purpose | parameter_types |]
[Format: | ClassName | Class | Brief purpose | __init__ params |]

### Usage Example
[REALISTIC code example with actual variable names and imports]
[Show how to actually use the main components]
[Include multiple lines if needed]

### Notes
[Important gotchas, warnings, or tips about this file]
[Performance considerations if relevant]
[Dependencies or requirements if relevant]

---

IMPORTANT FORMATTING RULES:
1. Use ## for file headers ONLY
2. Use ### for section headers (Overview, Key Components, Usage Example, Notes)
3. For Key Components table, use markdown table format with pipes
4. Code examples must be in ```python code blocks
5. Always end with --- (three dashes) between files
6. Be verbose and helpful - this is for developers who need to understand code quickly
7. Include actual sample data/variable names in usage examples
8. Explain WHY and HOW, not just WHAT

=== REPOSITORY FILES ===

{''.join(files_summary)}

=== DOCUMENTATION ===

Now write comprehensive documentation for each file following the structure above exactly."""

    # Make ONE API call for the entire repository
    markdown_output = ""
    retry_count = 0
    max_retries = 1
    
    while retry_count <= max_retries:
        try:
            stream = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        'role': 'user',
                        'content': combined_prompt
                    }
                ],
                stream=True,
                max_tokens=8000,
                timeout=30,
                extra_headers={
                    'HTTP-Referer': 'http://localhost:3000',
                    'X-Title': 'DocWizard'
                }
            )
            
            # Collect all streamed chunks
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    markdown_output += chunk.choices[0].delta.content
            
            break  # Success, exit retry loop
        
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Cannot reach OpenRouter - check internet connection: {e}")
            raise
        
        except requests.exceptions.Timeout as e:
            print(f"❌ Request timed out (30s): {e}")
            raise
        
        except requests.exceptions.HTTPError as e:
            # Check for 429 (rate limit)
            if e.response and e.response.status_code == 429:
                if retry_count < max_retries:
                    print(f"⚠️ Rate limit hit (HTTP 429) - waiting 60 seconds before retry...")
                    time.sleep(60)
                    retry_count += 1
                    continue
                else:
                    print(f"❌ Rate limit hit (HTTP 429) - max retries exhausted")
                    raise
            else:
                print(f"❌ HTTP Error {e.response.status_code if e.response else 'unknown'}: {e}")
                raise
        
        except Exception as e:
            # Print full exception details so we can debug
            print(f"❌ Unexpected error: {type(e).__name__}: {e}")
            import traceback
            print("Full traceback:")
            traceback.print_exc()
            raise
    
    # Parse the response and split by filename
    result = {}
    current_filename = None
    current_doc = ""
    
    for line in markdown_output.split('\n'):
        # Check if this is a file header (## filename or ### filename)
        if line.startswith('##') and not line.startswith('###'):
            # Save previous file if exists
            if current_filename and current_doc.strip():
                result[current_filename] = current_doc.strip()
            
            # Extract filename from header
            header_text = line.replace('##', '').strip()
            # Try to match to an actual filename
            for file_item in parsed_files:
                if file_item['filename'] in header_text or header_text in file_item['filename']:
                    current_filename = file_item['filename']
                    current_doc = ""
                    break
            else:
                # Fallback: use the header text as-is
                current_filename = header_text
                current_doc = ""
        elif current_filename:
            current_doc += line + "\n"
    
    # Save the last file
    if current_filename and current_doc.strip():
        result[current_filename] = current_doc.strip()
    
    # Ensure all files have documentation (fallback to combined output if parsing failed)
    if not result:
        # If we couldn't parse individual files, return the combined output for all files
        for file_item in parsed_files:
            result[file_item['filename']] = markdown_output
    else:
        # For files without specific documentation, add a note
        for file_item in parsed_files:
            if file_item['filename'] not in result:
                result[file_item['filename']] = f"Documentation for {file_item['filename']} is included in the comprehensive repository documentation above."
    
    return result


def generate_readme_for_repo(repo_url: str, docs_list: List[Dict[str, str]]) -> str:
    """
    Generates a comprehensive README.md for a repository using AI.
    
    Args:
        repo_url: The repository URL
        docs_list: List of dicts with 'filename' and 'documentation' keys
    
    Returns:
        README markdown content as a string
    """
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")
    
    client = OpenAI(
        api_key=api_key,
        base_url='https://openrouter.ai/api/v1'
    )
    
    # Extract project name from repo URL
    project_name = repo_url.strip('/').split('/')[-1]
    
    # Prepare documentation summary
    docs_summary = "\n".join([
        f"- {doc.get('filename', 'unknown')}: {doc.get('documentation', '')[:200]}..."
        for doc in docs_list[:10]  # Limit to first 10 files to stay within token limits
    ])
    
    prompt = f"""You are a technical writer. Create a professional README.md for this Python project based on the documentation:

Project Repository: {repo_url}
Project Name: {project_name}

Generated File Documentations:
{docs_summary}

Create a comprehensive README.md that includes:
1. **Project Title and Description** - 2-3 sentences about what the project does
2. **Features** - A bulleted list of 5-7 key features
3. **Installation** - Python-specific installation steps (venv, pip-install pattern)
4. **Usage** - Example code snippets of how to use the project
5. **Project Structure** - Brief descriptions of the main files/directories
6. **Contributing** - Generic contributing guidelines
7. **License** - Standard license section (MIT suggested)

Format the output as proper Markdown. Make it professional and ready for GitHub."""

    try:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            stream=True,
            max_tokens=2000,
            timeout=30,
            extra_headers={
                'HTTP-Referer': 'http://localhost:3000',
                'X-Title': 'DocWizard'
            }
        )
        
        readme_content = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                readme_content += chunk.choices[0].delta.content
        
        return readme_content.strip()
    
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"Cannot reach OpenRouter: {e}")
    except requests.exceptions.Timeout as e:
        raise TimeoutError(f"Request timed out (30s): {e}")
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 429:
            raise Exception("Rate limit hit (HTTP 429) - please wait 60 seconds")
        raise


def generate_gitignore_for_repo(repo_url: str, file_extensions: set, imports: set) -> str:
    """
    Generates a .gitignore file for a repository based on project type.
    
    Args:
        repo_url: The repository URL
        file_extensions: Set of file extensions found in the repo (e.g., {'.py', '.js', '.json'})
        imports: Set of top-level imported modules
    
    Returns:
        .gitignore content as a string
    """
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")
    
    client = OpenAI(
        api_key=api_key,
        base_url='https://openrouter.ai/api/v1'
    )
    
    # Detect project type based on file extensions and imports
    project_types = []
    if '.py' in file_extensions:
        project_types.append('Python')
    if '.js' in file_extensions or '.jsx' in file_extensions:
        project_types.append('Node.js/JavaScript')
    if '.ts' in file_extensions or '.tsx' in file_extensions:
        project_types.append('TypeScript')
    if '.go' in file_extensions:
        project_types.append('Go')
    if 'django' in imports or 'flask' in imports:
        project_types.append('Web Framework (Django/Flask)')
    if 'numpy' in imports or 'pandas' in imports or 'sklearn' in imports:
        project_types.append('Data Science')
    
    project_type_str = ', '.join(project_types) if project_types else 'Python'
    
    prompt = f"""Generate a professional .gitignore file for this {project_type_str} project at {repo_url}.

Include these REQUIRED entries first:
.env
__pycache__/
*.pyc
venv/
node_modules/
faiss_indexes/
.DS_Store

Then add appropriate entries for this project type: {project_type_str}

Include entries for:
- Build artifacts and temporary files
- IDE and editor files (.vscode/, .idea/, *.swp)
- OS-specific files
- Virtual environment and dependency files
- Cache and database files
- Any framework-specific directories

Format as a standard .gitignore file with clear comments describing each section.
Return ONLY the .gitignore content, no explanations."""

    try:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            stream=True,
            max_tokens=1500,
            timeout=30,
            extra_headers={
                'HTTP-Referer': 'http://localhost:3000',
                'X-Title': 'DocWizard'
            }
        )
        
        gitignore_content = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                gitignore_content += chunk.choices[0].delta.content
        
        return gitignore_content.strip()
    
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"Cannot reach OpenRouter: {e}")
    except requests.exceptions.Timeout as e:
        raise TimeoutError(f"Request timed out (30s): {e}")
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 429:
            raise Exception("Rate limit hit (HTTP 429) - please wait 60 seconds")
        raise
    # Test script to debug OpenRouter connection
    print("🧪 Testing OpenRouter API connection...")
    print(f"OPENROUTER_API_KEY set: {'Yes' if os.getenv('OPENROUTER_API_KEY') else 'No'}")
    print(f"MODEL: {MODEL}")
    print()
    
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("❌ ERROR: OPENROUTER_API_KEY not found in environment!")
        print("   Make sure .env file exists with OPENROUTER_API_KEY=your_key_here")
        exit(1)
    
    try:
        print("📤 Sending test request to OpenRouter...")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "DocWizard-Test"
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "say hello"}],
                "max_tokens": 10
            },
            timeout=30
        )
        
        print(f"\n✅ Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"\nResponse Body:\n{response.text}\n")
        
        if response.status_code == 200:
            print("✅ Connection successful!")
        elif response.status_code == 401:
            print("❌ Unauthorized (401) - Check your OPENROUTER_API_KEY")
        elif response.status_code == 429:
            print("❌ Rate limited (429) - Too many requests")
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
    
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: Cannot reach OpenRouter")
        print(f"   {e}")
    except requests.exceptions.Timeout as e:
        print(f"❌ Timeout Error: Request took longer than 30 seconds")
        print(f"   {e}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
