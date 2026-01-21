/**
 * Integrated Document Management Panel
 * Combines: Upload + List + Share + Delete functionality
 * Features: Session management, progress tracking, duplicate detection
 */

import { useState, useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import { getWebSocketUrl, MAX_FILE_SIZE_MB } from "../../config/constants";
import { DocumentSummary, DocumentListResponse } from "../../types";
import { listDocuments } from "../../api";
import { DocumentUploadSection } from "./DocumentUploadSection";
import { DocumentListSection } from "./DocumentListSection";
import "./DocumentManagement.css";

interface DocumentManagementProps {
  tenantId: number;
  userId: number;
  isOpen?: boolean;
  onClose?: () => void;
}

export type DocumentManagementTab = 'upload' | 'list';

export interface DocumentUploadStatus {
  isUploading: boolean;
  progress: number;
  steps: Array<{
    label: string;
    icon: string;
    status: 'pending' | 'active' | 'completed' | 'failed' | 'waiting';
  }>;
  sessionId: string | null;
  duplicateInfo?: any;
  similarDocs?: any;
  error?: string | null;
  success?: string | null;
}

export function DocumentManagement({ 
  tenantId, 
  userId, 
  isOpen = false, 
  onClose 
}: DocumentManagementProps) {
  const [activeTab, setActiveTab] = useState<DocumentManagementTab>('upload');
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  
  // Upload state - lift up from DocumentUploadSection
  const [uploadStatus, setUploadStatus] = useState<DocumentUploadStatus>({
    isUploading: false,
    progress: 0,
    steps: [],
    sessionId: null,
    error: null,
    success: null
  });
  
  const wsRef = useRef<WebSocket | null>(null);

  // Load documents when list tab is active
  useEffect(() => {
    if (isOpen && activeTab === 'list') {
      loadDocuments();
    }
  }, [isOpen, activeTab, tenantId, userId]);

  const loadDocuments = async () => {
    setDocumentsLoading(true);
    setDocumentsError(null);
    try {
      const response: DocumentListResponse = await listDocuments(userId, tenantId);
      setDocuments(response.documents);
    } catch (err) {
      setDocumentsError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setDocumentsLoading(false);
    }
  };

  // Refresh documents list after successful upload
  const handleUploadSuccess = () => {
    // Reload documents (but stay on upload tab)
    loadDocuments();
  };

  // Initialize session and WebSocket connection
  // Returns a Promise that resolves with sessionId when WebSocket is ready
  const initializeUploadSession = (): Promise<string> => {
    return new Promise((resolve) => {
      const sessionId = uuidv4();
      setUploadStatus(prev => ({ ...prev, sessionId }));
      
      // Connect WebSocket for real-time progress
      const ws = new WebSocket(getWebSocketUrl(sessionId));
      wsRef.current = ws;
      
      // Set a timeout in case WebSocket fails to connect
      const timeout = setTimeout(() => {
        console.warn('[DocumentManagement] WebSocket connection timeout, proceeding anyway');
        resolve(sessionId);
      }, 3000);
      
      ws.onopen = () => {
        clearTimeout(timeout);
        console.log('[DocumentManagement] WebSocket connected for session:', sessionId);
        // Small delay to ensure connection is fully established
        setTimeout(() => resolve(sessionId), 100);
      };
      
      ws.onerror = (error) => {
        clearTimeout(timeout);
        console.error('[DocumentManagement] WebSocket error:', error);
        // Still resolve to allow upload without real-time progress
        resolve(sessionId);
      };
      
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('[DocumentManagement] WebSocket message:', message);
          
          // Handle workflow progress updates here
          // This will be passed down to DocumentUploadSection
          if (message.type === 'workflow_state_update' || message.type === 'workflow_node') {
            // Update progress steps based on message
            // Implementation details in DocumentUploadSection
          }
        } catch (parseErr) {
          console.error('[DocumentManagement] Failed to parse WebSocket message:', parseErr);
        }
      };
    
      ws.onclose = () => {
        console.log('[DocumentManagement] WebSocket closed for session:', sessionId);
      };
    });
  };

  // Cleanup WebSocket on close
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  // Don't render if not open
  if (!isOpen) return null;

  return (
    <div className="document-management-overlay" onClick={onClose}>
      <div className="document-management-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <h2>🗂️ Document Management</h2>
          <button className="close-button" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="tab-navigation">
          <button 
            className={`tab-button ${activeTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveTab('upload')}
          >
            📤 Upload Document
            {uploadStatus.isUploading && <span className="upload-indicator">●</span>}
          </button>
          <button 
            className={`tab-button ${activeTab === 'list' ? 'active' : ''}`}
            onClick={() => setActiveTab('list')}
          >
            📚 My Documents ({documents.length})
          </button>
        </div>

        {/* Tab Content */}
        <div className="tab-content">
          {activeTab === 'upload' && (
            <DocumentUploadSection
              tenantId={tenantId}
              userId={userId}
              uploadStatus={uploadStatus}
              setUploadStatus={setUploadStatus}
              wsRef={wsRef}
              onUploadSuccess={handleUploadSuccess}
              initializeSession={initializeUploadSession}
            />
          )}
          
          {activeTab === 'list' && (
            <DocumentListSection
              tenantId={tenantId}
              userId={userId}
              documents={documents}
              loading={documentsLoading}
              error={documentsError}
              onRefresh={loadDocuments}
              onDocumentDeleted={loadDocuments}
            />
          )}
        </div>

        {/* Footer Info */}
        <div className="modal-footer">
          <div className="info-text">
            <span className="info-item">
              📄 Supported: PDF, TXT, MD files (max {MAX_FILE_SIZE_MB}MB)
            </span>
            <span className="info-item">
              🔒 Private documents are only visible to you
            </span>
            <span className="info-item">
              🏢 Tenant documents are visible to all tenant users
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}