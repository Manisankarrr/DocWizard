import os
import requests
from typing import List, Dict


def _parse_repo_url(repo_url: str) -> tuple:
    """
    Parse GitHub URL and return owner and repo.
    
    Args:
        repo_url: GitHub URL in format "https://github.com/user/repo"
    
    Returns:
        Tuple of (owner, repo)
    """
    parts = repo_url.rstrip('/').split('/')
    owner = parts[-2]
    repo = parts[-1]
    return owner, repo


def _get_github_headers() -> Dict[str, str]:
    """
    Get headers for GitHub API requests with authentication.
    
    Returns:
        Dict with Authorization header
    """
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        raise ValueError("GITHUB_TOKEN environment variable not set")
    
    return {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3.raw'
    }


def fetch_repo_files(repo_url: str) -> List[Dict[str, str]]:
    """
    Fetches all Python files from a GitHub repository.
    
    Args:
        repo_url: GitHub URL in format "https://github.com/user/repo"
    
    Returns:
        List of dicts with keys 'filename' and 'content'
    """
    owner, repo = _parse_repo_url(repo_url)
    headers = _get_github_headers()
    
    # Fetch the repository tree recursively
    tree_url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1'
    tree_response = requests.get(tree_url, headers=headers)
    tree_response.raise_for_status()
    tree_data = tree_response.json()
    
    # Filter for Python files
    py_files = [item for item in tree_data.get('tree', []) 
                if item['type'] == 'blob' and item['path'].endswith('.py')]
    
    # Fetch content for each Python file
    result = []
    for file_item in py_files:
        content_url = f'https://api.github.com/repos/{owner}/{repo}/contents/{file_item["path"]}'
        content_response = requests.get(content_url, headers=headers)
        content_response.raise_for_status()
        
        result.append({
            'filename': file_item['path'],
            'content': content_response.text
        })
    
    return result


def get_changed_files(repo_url: str, since_commit: str) -> List[Dict[str, str]]:
    """
    Fetches Python files changed since a given commit.
    
    Args:
        repo_url: GitHub URL in format "https://github.com/user/repo"
        since_commit: Commit SHA to compare from (e.g., "abc123def456")
    
    Returns:
        List of dicts with keys 'filename' and 'content' for changed .py files
    """
    owner, repo = _parse_repo_url(repo_url)
    headers = _get_github_headers()
    
    # Get comparison between since_commit and HEAD
    compare_url = f'https://api.github.com/repos/{owner}/{repo}/compare/{since_commit}...HEAD'
    compare_response = requests.get(compare_url, headers=headers)
    compare_response.raise_for_status()
    compare_data = compare_response.json()
    
    # Extract changed files (filter for .py files)
    files = compare_data.get('files', [])
    changed_py_files = [
        f for f in files
        if f['filename'].endswith('.py') and f['status'] != 'removed'
    ]
    
    if not changed_py_files:
        return []
    
    # Fetch content for each changed Python file
    result = []
    for file_item in changed_py_files:
        content_url = f'https://api.github.com/repos/{owner}/{repo}/contents/{file_item["filename"]}'
        try:
            content_response = requests.get(content_url, headers=headers)
            content_response.raise_for_status()
            
            result.append({
                'filename': file_item['filename'],
                'content': content_response.text
            })
        except requests.exceptions.RequestException:
            # File might have been deleted, skip it
            continue
    
    return result
