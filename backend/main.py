import os
import json
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator, Dict, Any

from github_client import fetch_repo_files, get_changed_files
from parser import parse_python_file
from doc_generator import generate_docs_for_repo, generate_readme_for_repo, generate_gitignore_for_repo
from vector_store import store_docs, search_docs, update_docs
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="DocWizard")

# Add CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateDocsRequest(BaseModel):
    repo_url: str


class AskRequest(BaseModel):
    repo_url: str
    question: str


class UpdateDocsRequest(BaseModel):
    repo_url: str
    since_commit: str


class GenerateReadmeRequest(BaseModel):
    repo_url: str


class GenerateGitignoreRequest(BaseModel):
    repo_url: str


@app.post("/generate-docs")
async def generate_docs(request: GenerateDocsRequest):
    """
    Generates documentation for all Python files in a GitHub repository.
    Makes ONE API call for the entire repository (efficient for free tier).
    Streams results as newline-delimited JSON.
    
    Args:
        request: Contains repo_url like "https://github.com/user/repo"
    
    Yields:
        JSON objects for each file with filename, parsed_data, and documentation
    """
    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Fetch all Python files from GitHub
            repo_files = fetch_repo_files(request.repo_url)
            total_files = len(repo_files)
            
            if total_files == 0:
                yield json.dumps({
                    'status': 'error',
                    'message': 'No Python files found in repository',
                    'repo_url': request.repo_url
                }) + '\n'
                return
            
            # Parse all files locally (no API calls)
            parsed_files_with_names = []
            for file_info in repo_files:
                filename = file_info['filename']
                content = file_info['content']
                parsed_data = parse_python_file(filename, content)
                parsed_files_with_names.append({
                    'filename': filename,
                    'parsed_data': parsed_data
                })
            
            # Generate documentation for ALL files in ONE API call
            yield json.dumps({
                'status': 'generating',
                'message': 'Generating documentation for all files...',
                'total_files': total_files
            }) + '\n'
            
            try:
                docs_by_file = generate_docs_for_repo(parsed_files_with_names)
            except Exception as e:
                if '429' in str(e) or 'rate limit' in str(e).lower():
                    yield json.dumps({
                        'status': 'rate_limit',
                        'message': 'Rate limit hit — waiting 60 seconds...',
                        'total_files': total_files
                    }) + '\n'
                    time.sleep(60)
                    # Retry once
                    docs_by_file = generate_docs_for_repo(parsed_files_with_names)
                else:
                    raise
            
            # Stream the results
            results = []
            for idx, file_item in enumerate(parsed_files_with_names):
                filename = file_item['filename']
                parsed_data = file_item['parsed_data']
                documentation = docs_by_file.get(filename, 'No documentation generated')
                
                result = {
                    'filename': filename,
                    'parsed_data': parsed_data,
                    'documentation': documentation
                }
                results.append(result)
                
                # Yield progress update with result
                yield json.dumps({
                    'status': 'file_processed',
                    'current': idx + 1,
                    'total': total_files,
                    'file': result
                }) + '\n'
            
            # Save all docs to FAISS index BEFORE returning response
            docs_for_storage = [
                {'filename': r['filename'], 'documentation': r['documentation']}
                for r in results
            ]
            store_docs(request.repo_url, docs_for_storage)
            
            # Final success message
            yield json.dumps({
                'status': 'complete',
                'total_files': total_files,
                'repo_url': request.repo_url,
                'message': f'Generated documentation for {total_files} files in 1 API call'
            }) + '\n'
        
        except Exception as e:
            yield json.dumps({
                'status': 'error',
                'message': str(e),
                'repo_url': request.repo_url
            }) + '\n'
    
    return StreamingResponse(generate(), media_type='application/x-ndjson')


@app.post("/ask")
async def ask_question(request: AskRequest) -> Dict[str, Any]:
    """
    Searches stored documentation for answers to a question.
    
    Args:
        request: Contains repo_url and question
    
    Returns:
        Dict with search results containing document chunks and filenames
    """
    try:
        results = search_docs(request.repo_url, request.question)
        
        return {
            'status': 'success',
            'repo_url': request.repo_url,
            'question': request.question,
            'results': results,
            'count': len(results)
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'repo_url': request.repo_url
        }


@app.post("/update-docs")
async def update_docs_endpoint(request: UpdateDocsRequest):
    """
    Updates documentation for files changed since a specific commit.
    Streams results as newline-delimited JSON.
    
    Args:
        request: Contains repo_url and since_commit SHA
    
    Yields:
        JSON objects for each processed file with filename, parsed_data, and documentation
    """
    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Step 1: Get changed files since commit
            changed_files = get_changed_files(request.repo_url, request.since_commit)
            
            if not changed_files:
                yield json.dumps({
                    'status': 'no_changes',
                    'message': 'No Python files changed since the specified commit',
                    'repo_url': request.repo_url,
                    'since_commit': request.since_commit
                }) + '\n'
                return
            
            total_files = len(changed_files)
            
            # Parse all changed files locally
            parsed_files_with_names = []
            for file_info in changed_files:
                filename = file_info['filename']
                content = file_info['content']
                parsed_data = parse_python_file(filename, content)
                parsed_files_with_names.append({
                    'filename': filename,
                    'parsed_data': parsed_data
                })
            
            # Generate documentation for ALL changed files in ONE API call
            yield json.dumps({
                'status': 'generating',
                'message': f'Generating documentation for {total_files} changed files...',
                'total_files': total_files
            }) + '\n'
            
            try:
                docs_by_file = generate_docs_for_repo(parsed_files_with_names)
            except Exception as e:
                if '429' in str(e) or 'rate limit' in str(e).lower():
                    yield json.dumps({
                        'status': 'rate_limit',
                        'message': 'Rate limit hit — waiting 60 seconds...',
                        'total_files': total_files
                    }) + '\n'
                    time.sleep(60)
                    # Retry once
                    docs_by_file = generate_docs_for_repo(parsed_files_with_names)
                else:
                    raise
            
            # Stream the results
            results = []
            for idx, file_item in enumerate(parsed_files_with_names):
                filename = file_item['filename']
                parsed_data = file_item['parsed_data']
                documentation = docs_by_file.get(filename, 'No documentation generated')
                
                result = {
                    'filename': filename,
                    'parsed_data': parsed_data,
                    'documentation': documentation
                }
                results.append(result)
                
                # Yield progress update with result
                yield json.dumps({
                    'status': 'file_processed',
                    'current': idx + 1,
                    'total': total_files,
                    'file': result
                }) + '\n'
            
            # Update FAISS index with changed files
            update_docs(request.repo_url, results)
            
            # Final success message
            yield json.dumps({
                'status': 'complete',
                'total_files': total_files,
                'repo_url': request.repo_url,
                'since_commit': request.since_commit,
                'message': f'Updated {total_files} changed files in FAISS index (1 API call)'
            }) + '\n'
        
        except Exception as e:
            yield json.dumps({
                'status': 'error',
                'message': str(e),
                'repo_url': request.repo_url,
                'since_commit': request.since_commit
            }) + '\n'
    
    return StreamingResponse(generate(), media_type='application/x-ndjson')


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {'status': 'ok'}


@app.post("/generate-readme")
async def generate_readme(request: GenerateReadmeRequest) -> Dict[str, Any]:
    """
    Generates a comprehensive README.md for a repository.
    Uses already-generated documentation from FAISS index.
    
    Args:
        request: Contains repo_url
    
    Returns:
        Dict with status and readme markdown content
    """
    try:
        # Search FAISS for all docs (use a broad query or get all with a dummy search)
        # For now, we'll search for a generic term that should match most documentation
        print(f"[GENERATE_README] Fetching docs for {request.repo_url} from FAISS...")
        results = search_docs(request.repo_url, "overview project structure functions classes", num_results=100)
        
        # Convert search results to the format generate_readme_for_repo expects
        # Extract unique documents
        seen_docs = set()
        docs_list = []
        
        print(f"[GENERATE_README] Retrieved {len(results)} result chunks, extracting unique docs...")
        for result in results:
            filename = result.get('filename', 'unknown')
            if filename not in seen_docs:
                docs_list.append({
                    'filename': filename,
                    'documentation': result.get('document', '')
                })
                seen_docs.add(filename)
        
        if not docs_list:
            print(f"[GENERATE_README] No docs found for {request.repo_url} - generating README anyway")
            # Fallback: create README with repo info
            readme_content = f"""# {request.repo_url.split('/')[-1]}

This project needs documentation. Please generate docs first using the /generate-docs endpoint.
"""
            return {
                'status': 'success',
                'readme': readme_content,
                'repo_url': request.repo_url,
                'message': 'Generated README (note: docs not found - please generate docs first)'
            }
        
        print(f"[GENERATE_README] Calling generate_readme_for_repo with {len(docs_list)} docs...")
        readme_content = generate_readme_for_repo(request.repo_url, docs_list)
        
        print(f"[GENERATE_README] README generated successfully ({len(readme_content)} chars)")
        return {
            'status': 'success',
            'readme': readme_content,
            'repo_url': request.repo_url,
            'message': 'README generated successfully'
        }
    
    except Exception as e:
        print(f"[GENERATE_README] Error: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'repo_url': request.repo_url
        }


@app.post("/generate-gitignore")
async def generate_gitignore(request: GenerateGitignoreRequest) -> Dict[str, Any]:
    """
    Generates a .gitignore file for a repository.
    Analyzes file extensions and imports to detect project type.
    
    Args:
        request: Contains repo_url
    
    Returns:
        Dict with status and gitignore content
    """
    try:
        print(f"[GENERATE_GITIGNORE] Fetching repo files for {request.repo_url}...")
        
        # Fetch repository files
        repo_files = fetch_repo_files(request.repo_url)
        
        # Analyze file extensions and imports
        file_extensions = set()
        all_imports = set()
        
        for file_info in repo_files:
            filename = file_info['filename']
            content = file_info['content']
            
            # Extract file extension
            if '.' in filename:
                ext = filename[filename.rfind('.'):]
                file_extensions.add(ext)
            
            # Parse file to extract imports
            if filename.endswith('.py'):
                parsed_data = parse_python_file(filename, content)
                for imp in parsed_data.get('imports', []):
                    # Extract just the module name
                    module_name = imp.split()[1].split('.')[0] if len(imp.split()) > 1 else imp.split('.')[0]
                    all_imports.add(module_name.lower())
        
        print(f"[GENERATE_GITIGNORE] Found extensions: {file_extensions}")
        print(f"[GENERATE_GITIGNORE] Found imports: {all_imports}")
        
        # Generate gitignore
        print(f"[GENERATE_GITIGNORE] Calling generate_gitignore_for_repo...")
        gitignore_content = generate_gitignore_for_repo(request.repo_url, file_extensions, all_imports)
        
        print(f"[GENERATE_GITIGNORE] .gitignore generated successfully ({len(gitignore_content)} chars)")
        return {
            'status': 'success',
            'gitignore': gitignore_content,
            'repo_url': request.repo_url,
            'message': '.gitignore generated successfully'
        }
    
    except Exception as e:
        print(f"[GENERATE_GITIGNORE] Error: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'repo_url': request.repo_url
        }
