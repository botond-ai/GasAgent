/**
 * Documents page with sidebar layout.
 * Left: Document list, Right: Detail view or upload form
 */
import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/client';
import { DocumentList } from '../components/documents/DocumentList';
import { DocumentDetail } from '../components/documents/DocumentDetail';
import { UploadDocumentForm } from '../components/documents/UploadDocumentForm';
import type { Document, DocumentDetail as DocumentDetailType, DocumentStats } from '../types';
import '../styles/components.css';

const CATEGORIES = [
  'Billing',
  'Technical',
  'Account',
  'Shipping',
  'Product',
  'General'
];

export default function Documents() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentDetailType | null>(null);
  const [stats, setStats] = useState<DocumentStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('');

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.listDocuments(selectedCategory || undefined);
      setDocuments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, [selectedCategory]);

  const loadStats = useCallback(async () => {
    try {
      const data = await apiClient.getDocumentStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }, []);

  const loadDocumentDetail = async (docId: string) => {
    setDetailLoading(true);
    setError(null);
    try {
      const doc = await apiClient.getDocument(docId);
      setSelectedDocument(doc);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load document');
      setSelectedDocument(null);
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
    loadStats();
  }, [loadDocuments, loadStats]);

  const handleSelectDocument = (docId: string) => {
    setShowUploadForm(false);
    loadDocumentDetail(docId);
  };

  const handleUpload = async (
    file: File,
    title: string,
    category: string,
    description?: string
  ) => {
    const result = await apiClient.uploadDocument(file, title, category, description);
    if (result.success && result.document) {
      setShowUploadForm(false);
      await loadDocuments();
      await loadStats();
      // Select the newly uploaded document
      loadDocumentDetail(result.document.id);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!window.confirm('Are you sure you want to delete this document? This will remove all indexed chunks.')) {
      return;
    }

    try {
      await apiClient.deleteDocument(docId);
      setSelectedDocument(null);
      await loadDocuments();
      await loadStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete document');
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Knowledge Base</h1>
        {stats && (
          <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.9rem', color: '#6e6e80' }}>
            <span>{stats.total_documents} documents</span>
            <span>{stats.total_chunks} chunks</span>
            <span>Status: {stats.collection_status}</span>
          </div>
        )}
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <div className="sidebar-header">
            <h2>Documents</h2>
            <button
              className="btn btn-primary"
              onClick={() => {
                setShowUploadForm(true);
                setSelectedDocument(null);
              }}
              style={{ width: '100%' }}
            >
              + Upload Document
            </button>
            <div style={{ marginTop: '1rem' }}>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="form-input"
                style={{ width: '100%' }}
              >
                <option value="">All Categories</option>
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <DocumentList
            documents={documents}
            selectedDocumentId={selectedDocument?.id || null}
            onSelectDocument={handleSelectDocument}
          />
        </aside>

        <section className="detail-view">
          {error && (
            <div className="error-message" style={{ margin: '2rem' }}>
              {error}
            </div>
          )}

          {(loading || detailLoading) && (
            <div style={{ margin: '2rem', color: '#6e6e80' }}>
              Loading...
            </div>
          )}

          {showUploadForm ? (
            <UploadDocumentForm
              onSubmit={handleUpload}
              onCancel={() => setShowUploadForm(false)}
            />
          ) : selectedDocument ? (
            <DocumentDetail
              document={selectedDocument}
              onDelete={handleDelete}
              loading={detailLoading}
            />
          ) : (
            <div className="detail-empty">
              {documents.length === 0
                ? 'Upload your first document to get started'
                : 'Select a document to view its content'}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
