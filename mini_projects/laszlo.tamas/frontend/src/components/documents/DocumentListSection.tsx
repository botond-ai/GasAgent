/**
 * Document List Section
 * Enhanced document listing with share, delete, and content preview
 * Includes filtering and sorting functionality
 */

import { useState } from "react";
import { DocumentSummary } from "../../types";
import { API_BASE_URL } from "../../config/constants";
import { DocumentShareModal } from "./DocumentShareModal";

interface DocumentListSectionProps {
  tenantId: number;
  userId: number;
  documents: DocumentSummary[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onDocumentDeleted: () => void;
}

type SortField = 'title' | 'uploaded_at' | 'content_length' | 'visibility';
type SortOrder = 'asc' | 'desc';

export function DocumentListSection({ 
  tenantId, 
  userId, 
  documents, 
  loading, 
  error, 
  onRefresh, 
  onDocumentDeleted 
}: DocumentListSectionProps) {
  const [sortField, setSortField] = useState<SortField>('uploaded_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [filterVisibility, setFilterVisibility] = useState<'all' | 'private' | 'tenant'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDocument, setSelectedDocument] = useState<DocumentSummary | null>(null);
  const [documentToDelete, setDocumentToDelete] = useState<DocumentSummary | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Filter and sort documents
  const filteredAndSortedDocuments = documents
    .filter(doc => {
      // Filter by visibility
      if (filterVisibility !== 'all' && doc.visibility !== filterVisibility) {
        return false;
      }
      
      // Filter by search term
      if (searchTerm) {
        const term = searchTerm.toLowerCase();
        return doc.title.toLowerCase().includes(term) ||
               doc.content_preview?.toLowerCase().includes(term) ||
               doc.owner_nickname.toLowerCase().includes(term);
      }
      
      return true;
    })
    .sort((a, b) => {
      let aValue: any = (a as any)[sortField];
      let bValue: any = (b as any)[sortField];
      
      // Handle date sorting
      if (sortField === 'uploaded_at') {
        aValue = new Date(aValue as string);
        bValue = new Date(bValue as string);
      }
      
      // Handle numeric sorting
      if (sortField === 'content_length') {
        aValue = Number(aValue) || 0;
        bValue = Number(bValue) || 0;
      }
      
      // Handle string sorting
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        const comparison = aValue.localeCompare(bValue);
        return sortOrder === 'asc' ? comparison : -comparison;
      }
      
      // Handle numeric/date comparison
      if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const handleDeleteDocument = async (doc: DocumentSummary) => {
    setIsDeleting(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/documents/${doc.id}?user_id=${userId}&tenant_id=${tenantId}`, 
        {
          method: 'DELETE',
        }
      );
      
      if (!response.ok) {
        const errorText = await response.text();
        
        let errorMessage = "Sikertelen törlés";
        try {
          const errorData = JSON.parse(errorText);
          
          // Handle different error formats
          if (response.status === 403) {
            errorMessage = "⛔ Nincs jogosultságod törölni ezt a dokumentumot.\nCsak saját dokumentumokat törölhetsz.";
          } else if (errorData.detail) {
            errorMessage = errorData.detail;
          } else if (errorData.message) {
            errorMessage = errorData.message;
          }
        } catch {
          errorMessage = `HTTP ${response.status}: ${errorText}`;
        }
        
        // Don't close modal on error, show error in alert
        alert(errorMessage);
        return; // Exit without closing modal
      }

      // Successful deletion - close modal and refresh
      setDocumentToDelete(null);
      onDocumentDeleted();
    } catch (error) {
      console.error('Delete failed:', error);
      alert('⚠️ Hiba történt a törlés során. Kérlek próbáld újra.');
    } finally {
      setIsDeleting(false);
    }
  };

  const getVisibilityBadge = (visibility: string, isOwner: boolean) => {
    if (visibility === 'private') {
      return (
        <span className="visibility-badge private">
          🔒 Private
        </span>
      );
    } else {
      return (
        <span className="visibility-badge tenant">
          🏢 Tenant{!isOwner ? ' (shared)' : ''}
        </span>
      );
    }
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



  const getSortIcon = (field: SortField) => {
    if (sortField !== field) return '↕️';
    return sortOrder === 'asc' ? '⬆️' : '⬇️';
  };

  if (loading) {
    return (
      <div className="list-section loading">
        <div className="loading-spinner">📄</div>
        <p>Loading documents...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="list-section error">
        <div className="error-message">
          ⚠️ {error}
        </div>
        <button onClick={onRefresh} className="retry-button">
          🔄 Retry
        </button>
      </div>
    );
  }

  return (
    <div className="list-section">
      {/* Controls Bar */}
      <div className="controls-bar">
        <div className="search-and-filter">
          {/* Search Input */}
          <div className="search-input">
            <input
              type="text"
              placeholder="🔍 Search documents..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-field"
            />
          </div>

          {/* Visibility Filter */}
          <select
            value={filterVisibility}
            onChange={(e) => setFilterVisibility(e.target.value as 'all' | 'private' | 'tenant')}
            className="visibility-filter"
          >
            <option value="all">All Documents</option>
            <option value="private">Private Only</option>
            <option value="tenant">Tenant Only</option>
          </select>
        </div>

        <div className="list-actions">
          <button onClick={onRefresh} className="refresh-button" disabled={loading}>
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Results Summary */}
      <div className="results-summary">
        Showing {filteredAndSortedDocuments.length} of {documents.length} documents
      </div>

      {/* Document Table */}
      {filteredAndSortedDocuments.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📭</div>
          <h3>No Documents Found</h3>
          <p>
            {searchTerm || filterVisibility !== 'all' 
              ? 'Try adjusting your search or filter settings.'
              : 'Upload your first document to get started!'
            }
          </p>
        </div>
      ) : (
        <div className="documents-table">
          {/* Table Header */}
          <div className="table-header">
            <div className="header-cell title" onClick={() => handleSort('title')}>
              📄 Document {getSortIcon('title')}
            </div>
            <div className="header-cell visibility" onClick={() => handleSort('visibility')}>
              🔒 Access {getSortIcon('visibility')}
            </div>
            <div className="header-cell date" onClick={() => handleSort('uploaded_at')}>
              📅 Uploaded {getSortIcon('uploaded_at')}
            </div>
            <div className="header-cell size" onClick={() => handleSort('content_length')}>
              📊 Size {getSortIcon('content_length')}
            </div>
            <div className="header-cell actions">
              ⚙️ Actions
            </div>
          </div>

          {/* Scrollable Table Body */}
          <div className="table-body" style={{
            maxHeight: "400px",
            overflowY: "auto",
            overflowX: "hidden"
          }}>

          {/* Table Rows */}
          {filteredAndSortedDocuments.map((doc) => {
            const isOwner = doc.owner_id === userId;
            return (
              <div key={doc.id} className="table-row">
                {/* Document Info */}
                <div className="cell title">
                  <div className="document-info">
                    <h4 className="document-title">{doc.title}</h4>
                    <p className="document-owner">by {doc.owner_nickname}</p>
                    {doc.content_preview && (
                      <p className="content-preview">
                        {doc.content_preview.substring(0, 100)}
                        {doc.content_preview.length > 100 ? '...' : ''}
                      </p>
                    )}
                  </div>
                </div>

                {/* Visibility */}
                <div className="cell visibility">
                  {getVisibilityBadge(doc.visibility, isOwner)}
                </div>

                {/* Upload Date */}
                <div className="cell date">
                  {formatDate(doc.uploaded_at)}
                </div>

                {/* Size Info */}
                <div className="cell size">
                  <div className="size-info">
                    <div>{doc.content_length?.toLocaleString()} chars</div>
                    <div className="chunks-info">
                      🧩 {doc.chunk_count || 0} chunks
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="cell actions">
                  <div className="action-buttons">
                    {/* Share Button */}
                    <button
                      onClick={() => setSelectedDocument(doc)}
                      className="action-button share"
                      title="Share document"
                    >
                      🔗
                    </button>

                    {/* Delete Button */}
                    <button
                      onClick={() => setDocumentToDelete(doc)}
                      style={{
                        background: "linear-gradient(135deg, #dc3545 0%, #c82333 100%)",
                        color: "white",
                        border: "none",
                        padding: "8px 16px",
                        borderRadius: "6px",
                        cursor: "pointer",
                        fontSize: "14px",
                        fontWeight: "500",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px"
                      }}
                      title="Delete document"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
          </div> {/* End scrollable table-body */}
        </div>
      )}

      {/* Share Modal */}
      {selectedDocument && (
        <DocumentShareModal
          document={selectedDocument}
          onClose={() => setSelectedDocument(null)}
        />
      )}

      {/* Delete Confirmation Modal */}
      {documentToDelete && (
        <div className="modal-overlay">
          <div className="confirmation-modal">
            <h3>🗑️ Delete Document</h3>
            <p>
              Are you sure you want to delete <strong>"{documentToDelete.title}"</strong>?
            </p>
            <p className="warning-text">
              ⚠️ This action cannot be undone. All chunks and embeddings will be removed.
            </p>
            <div className="modal-actions">
              <button
                onClick={() => handleDeleteDocument(documentToDelete)}
                disabled={isDeleting}
                className="delete-confirm-button"
              >
                {isDeleting ? "Deleting..." : "🗑️ Delete"}
              </button>
              <button
                onClick={() => setDocumentToDelete(null)}
                disabled={isDeleting}
                className="cancel-button"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}