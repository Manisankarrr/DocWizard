import { useState, useEffect } from 'react';
import { marked } from 'marked';

export default function App() {
  // State management
  const [repoUrl, setRepoUrl] = useState('');
  const [generatedRepoUrl, setGeneratedRepoUrl] = useState('');
  const [docs, setDocs] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [expandedFiles, setExpandedFiles] = useState({}); // Track which files are expanded
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [jsZipLoaded, setJsZipLoaded] = useState(false);
  const [readme, setReadme] = useState(null);
  const [readmeLoading, setReadmeLoading] = useState(false);
  const [readmeError, setReadmeError] = useState(null);
  const [gitignore, setGitignore] = useState(null);
  const [gitignoreLoading, setGitignoreLoading] = useState(false);
  const [gitignoreError, setGitignoreError] = useState(null);

  const API_BASE = 'http://localhost:8000';

  // Load JSZip library on mount
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
    script.onload = () => setJsZipLoaded(true);
    document.head.appendChild(script);
  }, []);

  // Utility: Copy to clipboard
  const copyToClipboard = (text, filename) => {
    navigator.clipboard.writeText(text).then(() => {
      alert(`Copied ${filename} to clipboard!`);
    }).catch(() => {
      alert('Failed to copy to clipboard');
    });
  };

  // Utility: Download single markdown file
  const downloadFile = (content, filename) => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Utility: Download all docs as ZIP
  const downloadAllAsZip = async () => {
    if (!docs || docs.length === 0 || !window.JSZip) {
      alert('JSZip library not loaded or no docs available');
      return;
    }

    try {
      const zip = new window.JSZip();
      docs.forEach(file => {
        zip.file(`${file.filename}.md`, file.documentation);
      });

      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `docwizard-${new Date().getTime()}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download ZIP:', err);
      alert('Failed to create ZIP file');
    }
  };

  // Toggle accordion
  const toggleFile = (filename) => {
    setExpandedFiles(prev => ({
      ...prev,
      [filename]: !prev[filename]
    }));
  };

  const handleGenerateDocs = async () => {
    if (!repoUrl.trim()) {
      setError('Please enter a GitHub repository URL');
      return;
    }

    setLoading(true);
    setError(null);
    setDocs(null);
    setProgress(null);
    setStatusMessage('');
    setExpandedFiles({});

    try {
      const response = await fetch(`${API_BASE}/generate-docs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ repo_url: repoUrl }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate documentation');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const processedFiles = [];
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');

        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          if (!line) continue;

          try {
            const data = JSON.parse(line);

            if (data.status === 'file_processed') {
              processedFiles.push(data.file);
              setProgress({
                current: data.current,
                total: data.total,
              });
              setStatusMessage(`Processed ${data.current}/${data.total} files`);
            } else if (data.status === 'rate_limit') {
              setStatusMessage(data.message);
            } else if (data.status === 'complete') {
              setProgress(null);
              setStatusMessage('');
              setDocs(processedFiles);
              setGeneratedRepoUrl(repoUrl);
            } else if (data.status === 'error') {
              throw new Error(data.message);
            }
          } catch (parseError) {
            console.error('Failed to parse line:', line, parseError);
          }
        }

        buffer = lines[lines.length - 1];
      }

      if (buffer.trim()) {
        try {
          const data = JSON.parse(buffer);
          if (data.status === 'error') {
            throw new Error(data.message);
          }
        } catch (parseError) {
          console.error('Failed to parse final buffer:', buffer, parseError);
        }
      }
    } catch (err) {
      setError(err.message || 'An error occurred');
      setDocs(null);
      setProgress(null);
    } finally {
      setLoading(false);
      setStatusMessage('');
    }
  };

  const handleSearch = async () => {
    // Validate that docs have been generated
    if (!generatedRepoUrl) {
      setSearchError('Please generate documentation for a repository first');
      return;
    }

    if (!searchQuery.trim()) {
      setSearchError('Please enter a search question');
      return;
    }

    setSearchLoading(true);
    setSearchError(null);
    setSearchResults(null);

    try {
      const response = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repo_url: generatedRepoUrl,
          question: searchQuery,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to search documentation');
      }

      const data = await response.json();
      if (data.status === 'success') {
        setSearchResults(data.results);
      } else {
        setSearchError(data.message || 'Error searching documentation');
      }
    } catch (err) {
      setSearchError(err.message || 'An error occurred');
    } finally {
      setSearchLoading(false);
    }
  };

  const handleGenerateReadme = async () => {
    if (!generatedRepoUrl) {
      setReadmeError('Please generate documentation first');
      return;
    }

    setReadmeLoading(true);
    setReadmeError(null);
    setReadme(null);

    try {
      const response = await fetch(`${API_BASE}/generate-readme`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repo_url: generatedRepoUrl,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate README');
      }

      const data = await response.json();
      if (data.status === 'success') {
        setReadme(data.readme);
      } else {
        setReadmeError(data.message || 'Error generating README');
      }
    } catch (err) {
      setReadmeError(err.message || 'An error occurred');
    } finally {
      setReadmeLoading(false);
    }
  };

  const handleGenerateGitignore = async () => {
    if (!generatedRepoUrl) {
      setGitignoreError('Please generate documentation first');
      return;
    }

    setGitignoreLoading(true);
    setGitignoreError(null);
    setGitignore(null);

    try {
      const response = await fetch(`${API_BASE}/generate-gitignore`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repo_url: generatedRepoUrl,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate .gitignore');
      }

      const data = await response.json();
      if (data.status === 'success') {
        setGitignore(data.gitignore);
      } else {
        setGitignoreError(data.message || 'Error generating .gitignore');
      }
    } catch (err) {
      setGitignoreError(err.message || 'An error occurred');
    } finally {
      setGitignoreLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-teal-600 to-teal-500 bg-clip-text text-transparent">
              DocWizard
            </h1>
            <p className="text-gray-600 text-sm mt-1">AI-powered code documentation</p>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Input Section */}
        <div className="mb-12">
          <div className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 p-8 border border-gray-100">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Generate Documentation</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  GitHub Repository URL
                </label>
                <input
                  type="text"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleGenerateDocs()}
                  placeholder="https://github.com/user/repo"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none transition text-gray-900"
                />
              </div>

              <button
                onClick={handleGenerateDocs}
                disabled={loading}
                className="w-full bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-700 hover:to-teal-600 disabled:from-gray-400 disabled:to-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition duration-200 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Generating Docs...
                  </>
                ) : (
                  <>
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Generate Docs
                  </>
                )}
              </button>

              {/* Progress Bar */}
              {progress && (
                <div className="space-y-3">
                  <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-gradient-to-r from-teal-600 to-teal-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${(progress.current / progress.total) * 100}%` }}
                    />
                  </div>
                  <p className="text-sm text-gray-600 text-center font-medium">
                    {statusMessage || `Processing ${progress.current}/${progress.total} files...`}
                  </p>
                </div>
              )}

              {/* Error Alert */}
              {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
                  <svg className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <span className="text-sm text-red-800">{error}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Generated Docs Section */}
        {docs && docs.length > 0 && (
          <div className="mb-12">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Generated Documentation</h2>
              <div className="flex gap-3">
                <button
                  onClick={handleGenerateReadme}
                  disabled={readmeLoading || !generatedRepoUrl}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-lg transition"
                  title="Generate project README"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  {readmeLoading ? 'Generating...' : 'Generate README'}
                </button>

                <button
                  onClick={handleGenerateGitignore}
                  disabled={gitignoreLoading || !generatedRepoUrl}
                  className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-lg transition"
                  title="Generate .gitignore"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  {gitignoreLoading ? 'Generating...' : 'Generate .gitignore'}
                </button>

                <button
                  onClick={downloadAllAsZip}
                  disabled={!jsZipLoaded}
                  className="flex items-center gap-2 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-lg transition"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download All as ZIP
                </button>
              </div>
            </div>

            <div className="space-y-3">
              {docs.map((file, index) => (
                <div
                  key={index}
                  className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow"
                >
                  {/* Accordion Header */}
                  <button
                    onClick={() => toggleFile(file.filename)}
                    className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition"
                  >
                    <div className="flex items-center gap-3 flex-1 text-left">
                      <svg
                        className={`h-5 w-5 text-teal-600 transition-transform ${expandedFiles[file.filename] ? 'rotate-180' : ''}`}
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                      <span className="font-mono text-sm font-semibold text-gray-900">{file.filename}</span>
                      <span className="ml-auto text-xs bg-teal-100 text-teal-800 px-2 py-1 rounded">
                        {file.documentation.length} bytes
                      </span>
                    </div>
                  </button>

                  {/* Accordion Content */}
                  {expandedFiles[file.filename] && (
                    <div className="border-t border-gray-200 bg-gray-50 px-6 py-4">
                      {/* Markdown Content */}
                      <div className="prose prose-sm max-w-none mb-6 bg-white rounded p-4 max-h-96 overflow-y-auto text-gray-900">
                        <div dangerouslySetInnerHTML={{ __html: marked(file.documentation) }} />
                      </div>

                      {/* Action Buttons */}
                      <div className="flex gap-3 pt-4 border-t border-gray-200">
                        <button
                          onClick={() => copyToClipboard(file.documentation, file.filename)}
                          className="flex-1 flex items-center justify-center gap-2 bg-blue-100 hover:bg-blue-200 text-blue-700 font-medium py-2 px-4 rounded-lg transition"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                          Copy
                        </button>
                        <button
                          onClick={() => downloadFile(file.documentation, file.filename)}
                          className="flex-1 flex items-center justify-center gap-2 bg-green-100 hover:bg-green-200 text-green-700 font-medium py-2 px-4 rounded-lg transition"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 16v-4m0 0V8m0 4h4m-4 0H8m7 4v2a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2h14a2 2 0 012 2v6a2 2 0 01-2 2z" />
                          </svg>
                          Download .md
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* README Section */}
        {readme && (
          <div className="mb-12">
            <div className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 border border-gray-100 overflow-hidden">
              {/* README Header */}
              <div className="bg-gradient-to-r from-blue-600 to-blue-500 px-6 py-4 text-white">
                <div className="flex items-center justify-between">
                  <h2 className="text-2xl font-bold flex items-center gap-2">
                    <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    README.md
                  </h2>
                </div>
              </div>

              {/* README Content */}
              <div className="p-6">
                <div className="prose prose-sm max-w-none bg-gray-50 rounded-lg p-6 max-h-96 overflow-y-auto">
                  <div dangerouslySetInnerHTML={{ __html: marked(readme) }} />
                </div>

                {/* README Actions */}
                <div className="flex gap-3 mt-6 pt-6 border-t border-gray-200">
                  <button
                    onClick={() => copyToClipboard(readme, 'README.md')}
                    className="flex-1 flex items-center justify-center gap-2 bg-blue-100 hover:bg-blue-200 text-blue-700 font-medium py-2 px-4 rounded-lg transition"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy to Clipboard
                  </button>
                  <button
                    onClick={() => downloadFile(readme, 'README')}
                    className="flex-1 flex items-center justify-center gap-2 bg-green-100 hover:bg-green-200 text-green-700 font-medium py-2 px-4 rounded-lg transition"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download README.md
                  </button>
                </div>

                {readmeError && (
                  <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
                    <svg className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    <span className="text-sm text-red-800">{readmeError}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* .gitignore Section */}
        {gitignore && (
          <div className="mb-12">
            <div className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 border border-gray-100 overflow-hidden">
              {/* Gitignore Header */}
              <div className="bg-gradient-to-r from-purple-600 to-purple-500 px-6 py-4 text-white">
                <div className="flex items-center justify-between">
                  <h2 className="text-2xl font-bold flex items-center gap-2">
                    <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    .gitignore
                  </h2>
                </div>
              </div>

              {/* Gitignore Content */}
              <div className="p-6">
                <div className="bg-gray-900 text-gray-100 rounded-lg p-6 max-h-96 overflow-y-auto font-mono text-sm whitespace-pre-wrap">
                  {gitignore}
                </div>

                {/* Gitignore Actions */}
                <div className="flex gap-3 mt-6 pt-6 border-t border-gray-200">
                  <button
                    onClick={() => copyToClipboard(gitignore, '.gitignore')}
                    className="flex-1 flex items-center justify-center gap-2 bg-purple-100 hover:bg-purple-200 text-purple-700 font-medium py-2 px-4 rounded-lg transition"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy to Clipboard
                  </button>
                  <button
                    onClick={() => downloadFile(gitignore, '.gitignore')}
                    className="flex-1 flex items-center justify-center gap-2 bg-green-100 hover:bg-green-200 text-green-700 font-medium py-2 px-4 rounded-lg transition"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download .gitignore
                  </button>
                </div>

                {gitignoreError && (
                  <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
                    <svg className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    <span className="text-sm text-red-800">{gitignoreError}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Search Section */}
        <div className="mb-12">
          <div className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 p-8 border border-gray-100">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Search Documentation</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Ask a Question
                </label>
                <div className="relative">
                  <textarea
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter' && e.ctrlKey) {
                        handleSearch();
                      }
                    }}
                    placeholder="Ask a question about the code... (Press Ctrl+Enter to search)"
                    rows="3"
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none resize-none text-gray-900 placeholder-gray-500"
                  />
                </div>
              </div>

              <button
                onClick={handleSearch}
                disabled={searchLoading || !generatedRepoUrl}
                className="w-full bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-700 hover:to-teal-600 disabled:from-gray-400 disabled:to-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition duration-200 flex items-center justify-center gap-2"
              >
                {searchLoading ? (
                  <>
                    <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Searching...
                  </>
                ) : (
                  <>
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    Search Docs
                  </>
                )}
              </button>

              {searchError && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
                  <svg className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <span className="text-sm text-red-800">{searchError}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Search Results Section */}
        {searchResults && searchResults.length > 0 && (
          <div className="mb-12">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">
              Search Results
              <span className="ml-3 text-lg font-normal text-gray-500">
                {searchResults.length} result{searchResults.length !== 1 ? 's' : ''}
              </span>
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {searchResults.map((result, index) => (
                <div
                  key={index}
                  className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between mb-4">
                    <span className="inline-block bg-teal-100 text-teal-800 text-xs font-semibold px-3 py-1 rounded-full">
                      {result.filename}
                    </span>
                    <span className="text-xs text-gray-500">
                      Relevance: {(1 / (1 + result.distance)).toFixed(2)}
                    </span>
                  </div>

                  <div className="prose prose-sm max-w-none text-gray-700 max-h-48 overflow-y-auto">
                    <div dangerouslySetInnerHTML={{ __html: marked(result.document) }} />
                  </div>

                  <button
                    onClick={() => copyToClipboard(result.document, `${result.filename}-result`)}
                    className="mt-4 text-sm text-teal-600 hover:text-teal-700 font-medium flex items-center gap-1"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy Result
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {!docs && !searchResults && !loading && (
          <div className="text-center py-16">
            <svg className="h-16 w-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No documentation yet</h3>
            <p className="text-gray-600 mb-6">Enter a GitHub repository URL above to get started</p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-gray-50 border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-center text-sm text-gray-600">
          <p>DocWizard · AI-powered documentation generator</p>
        </div>
      </footer>
    </div>
  );
}
