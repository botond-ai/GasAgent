/**
 * DocumentList Component
 * Displays all accessible documents with filtering
 */

import { useState, useEffect } from 'react';
import { listDocuments, deleteDocument } from '../../api';
import { DocumentSummary, DocumentListResponse } from '../../types';
import { DocumentShareModal } from './DocumentShareModal';
import './DocumentList.css';

interface DocumentListProps {
  userId: number;
  tenantId: number;
  isOpen?: boolean;
  onClose?: () => void;
}

export function DocumentList({ userId, tenantId, isOpen = false, onClose }: DocumentListProps) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<DocumentSummary | null>(null);

  // Don't load if modal is not open
  useEffect(() => {
    if (isOpen) {
      loadDocuments();
    }
  }, [userId, tenantId, isOpen]);

  const loadDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const response: DocumentListResponse = await listDocuments(userId, tenantId);
      setDocuments(response.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const getVisibilityBadge = (visibility: string) => {
    const colors: Record<string, string> = {
      'private': '#6c757d',
      'tenant': '#17a2b8'
    };
    return (
      <span 
        className="visibility-badge"
        style={{ backgroundColor: colors[visibility] || '#999' }}
      >
        {visibility === 'private' ? 'Private' : 'Tenant-wide'}
      </span>
    );
  };

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleDelete = async (doc: DocumentSummary) => {
    if (!confirm(`Are you sure you want to delete "${doc.title}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await deleteDocument(doc.id, userId, tenantId);
      // Refresh the list
      await loadDocuments();
    } catch (err) {
      alert(`Failed to delete document: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  // Don't render if not open
  if (!isOpen) return null;

  if (loading) {
    return (
      <div className="document-list-modal-overlay">
        <div className="document-list-modal">
          <div className="modal-header">
            <h3>📚 My Documents</h3>
            <button className="close-button" onClick={onClose}>✕</button>
          </div>
          <div className="loading-message">Loading documents...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="document-list-modal-overlay">
        <div className="document-list-modal">
          <div className="modal-header">
            <h3>📚 My Documents</h3>
            <button className="close-button" onClick={onClose}>✕</button>
          </div>
          <div className="error-message">
            ⚠️ {error}
          </div>
          <button onClick={loadDocuments} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="document-list-modal-overlay" onClick={onClose}>
      <div className="document-list-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>📚 My Documents ({documents.length})</h3>
          <button className="close-button" onClick={onClose}>✕</button>
        </div>

        <div className="document-list-content">
          <div className="document-list-toolbar">
            <button onClick={loadDocuments} className="refresh-button" title="Refresh list">
              🔄 Refresh
            </button>
          </div>

          {documents.length === 0 ? (
            <div className="empty-state">
              <p>No documents found.</p>
              <p className="empty-hint">Upload a document to get started!</p>
            </div>
          ) : (
            <div className="documents-grid">
              {documents.map((doc) => (
                <div key={doc.id} className="document-card">
                  <div className="document-card-header">
                    <h3 className="document-title" title={doc.title}>
                      {doc.title}
                    </h3>
                    {getVisibilityBadge(doc.visibility)}
                  </div>
                  
                  <div className="document-meta">
                    <span className="document-source">{doc.source}</span>
                    <span className="document-date">{formatDate(doc.created_at)}</span>
                  </div>

                  <div className="document-actions">
                    <button
                      onClick={() => handleDelete(doc)}
                      className="delete-btn-red"
                      title="Delete document"
                      disabled={doc.user_id !== userId && doc.visibility === 'private'}
                    >
                      🗑️ Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Share Modal */}
        {selectedDocument && (
          <DocumentShareModal
            document={selectedDocument}
            onClose={() => setSelectedDocument(null)}
          />
        )}
      </div>
    </div>
  );
}
