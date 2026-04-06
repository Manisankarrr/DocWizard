import os
import json
import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer

# Initialize embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Directory to store FAISS indexes
INDEXES_DIR = Path('faiss_indexes')
INDEXES_DIR.mkdir(exist_ok=True)


def _sanitize_repo_url(repo_url: str) -> str:
    """Sanitize repository URL to create a valid filename."""
    return repo_url.replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_').replace(':', '_')[:63]


def store_docs(repo_url: str, docs_list: List[Dict[str, Any]]) -> None:
    """
    Stores generated documentation in FAISS with sentence-transformers embeddings.
    
    Args:
        repo_url: The repository URL (used for index filename)
        docs_list: List of dicts containing 'filename' and 'documentation'
    """
    repo_slug = _sanitize_repo_url(repo_url)
    print(f"[STORE_DOCS] Starting storage for repo: {repo_url}")
    print(f"[STORE_DOCS] Repo slug: {repo_slug}")
    
    # Extract all documentation text
    doc_texts = []
    doc_metadata = []
    
    for doc_item in docs_list:
        text = doc_item['documentation']
        filename = doc_item['filename']
        doc_texts.append(text)
        doc_metadata.append({'filename': filename, 'repo_url': repo_url})
    
    print(f"[STORE_DOCS] Extracted {len(doc_texts)} documents")
    
    if not doc_texts:
        print(f"[STORE_DOCS] No documents to store, returning early")
        return
    
    # Generate embeddings for all documents
    print(f"[STORE_DOCS] Generating embeddings for {len(doc_texts)} documents...")
    embeddings = model.encode(doc_texts, convert_to_numpy=True)
    print(f"[STORE_DOCS] Embeddings shape: {embeddings.shape}")
    
    # Create FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype(np.float32))
    print(f"[STORE_DOCS] FAISS index created with {index.ntotal} vectors")
    
    # Save FAISS index
    index_path = INDEXES_DIR / f'{repo_slug}.index'
    faiss.write_index(index, str(index_path))
    print(f"[STORE_DOCS] FAISS index saved to: {index_path}")
    
    # Save text chunks and metadata
    texts_path = INDEXES_DIR / f'{repo_slug}_texts.json'
    with open(texts_path, 'w') as f:
        json.dump({
            'texts': doc_texts,
            'metadata': doc_metadata,
            'repo_url': repo_url
        }, f)
    print(f"[STORE_DOCS] Metadata saved to: {texts_path}")
    print(f"[STORE_DOCS] Storage complete!")


def update_docs(repo_url: str, updated_docs_list: List[Dict[str, Any]]) -> None:
    """
    Updates documentation for specific files in an existing FAISS index.
    Loads existing index, updates entries for the specified files, and rebuilds.
    
    Args:
        repo_url: The repository URL
        updated_docs_list: List of dicts with 'filename' and 'documentation' to update
    """
    repo_slug = _sanitize_repo_url(repo_url)
    print(f"[UPDATE_DOCS] Starting update for repo: {repo_url}")
    print(f"[UPDATE_DOCS] Updating {len(updated_docs_list)} files")
    
    index_path = INDEXES_DIR / f'{repo_slug}.index'
    texts_path = INDEXES_DIR / f'{repo_slug}_texts.json'
    
    # Load existing index and texts
    if not index_path.exists() or not texts_path.exists():
        print(f"[UPDATE_DOCS] No existing index found, creating new one")
        # No existing index, create new one with these docs
        store_docs(repo_url, updated_docs_list)
        return
    
    try:
        # Load existing data
        with open(texts_path, 'r') as f:
            data = json.load(f)
        
        existing_texts = data['texts']
        existing_metadata = data['metadata']
        print(f"[UPDATE_DOCS] Loaded {len(existing_texts)} existing documents")
        
        # Get filenames being updated
        updated_filenames = {doc['filename'] for doc in updated_docs_list}
        
        # Remove entries for files being updated
        filtered_texts = []
        filtered_metadata = []
        for text, meta in zip(existing_texts, existing_metadata):
            if meta.get('filename') not in updated_filenames:
                filtered_texts.append(text)
                filtered_metadata.append(meta)
        
        print(f"[UPDATE_DOCS] After filtering: {len(filtered_texts)} documents remain")
        
        # Add new entries
        for doc in updated_docs_list:
            filtered_texts.append(doc['documentation'])
            filtered_metadata.append({
                'filename': doc['filename'],
                'repo_url': repo_url
            })
        
        print(f"[UPDATE_DOCS] After adding updates: {len(filtered_texts)} documents total")
        
        if not filtered_texts:
            print(f"[UPDATE_DOCS] No documents remaining, returning early")
            return
        
        # Rebuild FAISS index
        print(f"[UPDATE_DOCS] Rebuilding FAISS index...")
        embeddings = model.encode(filtered_texts, convert_to_numpy=True)
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings.astype(np.float32))
        print(f"[UPDATE_DOCS] FAISS index rebuilt with {index.ntotal} vectors")
        
        # Save updated index
        faiss.write_index(index, str(index_path))
        print(f"[UPDATE_DOCS] Updated FAISS index saved to: {index_path}")
        
        # Save updated texts
        with open(texts_path, 'w') as f:
            json.dump({
                'texts': filtered_texts,
                'metadata': filtered_metadata,
                'repo_url': repo_url
            }, f)
        print(f"[UPDATE_DOCS] Updated metadata saved to: {texts_path}")
        print(f"[UPDATE_DOCS] Update complete!")
    
    except Exception as e:
        print(f"Error updating index for {repo_url}: {e}")
        raise


def search_docs(repo_url: str, question: str, num_results: int = 3) -> List[Dict[str, Any]]:
    """
    Searches stored documentation using semantic similarity.
    
    Args:
        repo_url: The repository URL
        question: Natural language question to search for
        num_results: Number of top results to return (default: 3)
    
    Returns:
        List of dicts containing 'document', 'filename', and 'distance'
    """
    repo_slug = _sanitize_repo_url(repo_url)
    print(f"[SEARCH_DOCS] Searching for: '{question}' in repo: {repo_url}")
    
    # Check if index exists
    index_path = INDEXES_DIR / f'{repo_slug}.index'
    texts_path = INDEXES_DIR / f'{repo_slug}_texts.json'
    
    if not index_path.exists() or not texts_path.exists():
        print(f"[SEARCH_DOCS] ERROR: No index found for repo. Please generate documentation first.")
        print(f"[SEARCH_DOCS] Expected paths: {index_path} and {texts_path}")
        return []
    
    try:
        # Load FAISS index
        print(f"[SEARCH_DOCS] Loading FAISS index from: {index_path}")
        index = faiss.read_index(str(index_path))
        print(f"[SEARCH_DOCS] FAISS index loaded with {index.ntotal} vectors")
        
        # Load text chunks
        with open(texts_path, 'r') as f:
            data = json.load(f)
        
        texts = data['texts']
        metadata = data['metadata']
        print(f"[SEARCH_DOCS] Loaded {len(texts)} text documents and metadata")
    except Exception as e:
        print(f"[SEARCH_DOCS] Error loading index for {repo_url}: {e}")
        return []
    
    # Embed the question
    print(f"[SEARCH_DOCS] Encoding question embedding...")
    question_embedding = model.encode([question], convert_to_numpy=True)
    
    # Search the index
    print(f"[SEARCH_DOCS] Searching for top {min(num_results, len(texts))} results...")
    distances, indices = index.search(question_embedding.astype(np.float32), min(num_results, len(texts)))
    
    # Format results
    formatted_results = []
    for idx, distance in zip(indices[0], distances[0]):
        if idx == -1:  # No valid result
            continue
        formatted_results.append({
            'document': texts[idx],
            'filename': metadata[idx].get('filename', 'unknown'),
            'distance': float(distance)
        })
    
    print(f"[SEARCH_DOCS] Found {len(formatted_results)} results")
    return formatted_results
