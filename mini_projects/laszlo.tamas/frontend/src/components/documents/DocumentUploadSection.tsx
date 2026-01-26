/**
 * Document Upload Section 
 * Enhanced upload with session management, WebSocket progress, duplicate detection
 * Based on KA Chat advanced features
 */

import { useState } from "react";
import { API_BASE_URL, MAX_FILE_SIZE, ALLOWED_FILE_TYPES } from "../../config/constants";
import { DocumentUploadStatus } from "./DocumentManagement";
import { ProgressSteps } from "../ProgressSteps";
import "./DocumentUpload.css";

const MAX_FILE_SIZE_MB = MAX_FILE_SIZE / (1024 * 1024);

interface DocumentUploadSectionProps {
  tenantId: number;
  userId: number;
  uploadStatus: DocumentUploadStatus;
  setUploadStatus: (status: DocumentUploadStatus | ((prev: DocumentUploadStatus) => DocumentUploadStatus)) => void;
  wsRef: React.MutableRefObject<WebSocket | null>;
  onUploadSuccess: (summary: any) => void;
  initializeSession: () => Promise<string>;
}

export function DocumentUploadSection({ 
  tenantId, 
  userId, 
  uploadStatus,
  setUploadStatus,
  wsRef,
  onUploadSuccess,
  initializeSession
}: DocumentUploadSectionProps) {
  const [file, setFile] = useState<File | null>(null);
  const [visibility, setVisibility] = useState<"private" | "tenant">("private");

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    
    // Reset previous states
    setUploadStatus(prev => ({ ...prev, error: null, success: null }));

    if (!selectedFile) {
      setFile(null);
      return;
    }

    // Validate file type
    const fileExt = `.${selectedFile.name.split(".").pop()?.toLowerCase()}` as const;
    if (!ALLOWED_FILE_TYPES.includes(fileExt as any)) {
      setUploadStatus(prev => ({ 
        ...prev, 
        error: `Invalid file type. Allowed: ${ALLOWED_FILE_TYPES.join(", ")}` 
      }));
      setFile(null);
      return;
    }

    // Validate file size
    if (selectedFile.size > MAX_FILE_SIZE) {
      setUploadStatus(prev => ({ 
        ...prev, 
        error: `File too large. Maximum size: ${MAX_FILE_SIZE_MB}MB` 
      }));
      setFile(null);
      return;
    }

    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) {
      setUploadStatus(prev => ({ ...prev, error: "Please select a file" }));
      return;
    }

    // Initialize session and WebSocket (wait for connection)
    const sessionId = await initializeSession();
    console.log('[DocumentUploadSection] WebSocket ready, starting upload with session:', sessionId);
    
    // Reset upload state
    setUploadStatus(prev => ({
      ...prev,
      isUploading: true,
      progress: 0,
      error: null,
      success: null,
      duplicateInfo: undefined,
      similarDocs: undefined,
      sessionId
    }));

    // Initialize progress steps (enhanced from KA Chat)
    const initialSteps = [
      { label: "Validate file", icon: "✅", status: "pending" as const },
      { label: "Extract content", icon: "📄", status: "pending" as const },
      { label: "Check duplicates", icon: "🔍", status: "pending" as const },
      { label: "Check similarity", icon: "🔬", status: "pending" as const },
      { label: "Store document", icon: "💾", status: "pending" as const },
      { label: "Generate chunks", icon: "✂️", status: "pending" as const },
      { label: "Generate embeddings", icon: "🔢", status: "pending" as const },
      { label: "Store in Qdrant", icon: "🗄️", status: "pending" as const },
      { label: "Verify completion", icon: "✅", status: "pending" as const },
    ];
    
    setUploadStatus(prev => ({ ...prev, steps: initialSteps }));

    // Setup WebSocket message handling
    if (wsRef.current) {
      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('[DocumentUploadSection] WebSocket message:', message);

          // Handle workflow node events
          if ((message.type === 'workflow_state_update' || message.type === 'workflow_node') && message.node) {
            const nodeToStepIndex: { [key: string]: number } = {
              'validate_file': 0,
              'extract_content': 1,
              'detect_duplicates': 2,
              'check_similarity': 3,
              'store_document': 4,
              'chunk_document': 5,
              'generate_embeddings': 6,
              'upsert_to_qdrant': 7,
              'verify_completion': 8,
            };

            const stepIndex = nodeToStepIndex[message.node];
            
            // Handle duplicate detection (in state data)
            if (message.state?.type === 'duplicate_detected' && message.state?.duplicate_info) {
              setUploadStatus(prev => ({ 
                ...prev, 
                duplicateInfo: message.state.duplicate_info,
                steps: prev.steps.map((step, index) => 
                  index === 2 ? { ...step, status: 'waiting' } : step
                )
              }));
              return;
            }

            // Handle similar documents detection (in state data)
            if (message.state?.type === 'similar_detected' && message.state?.similar_docs) {
              setUploadStatus(prev => ({ 
                ...prev, 
                similarDocs: message.state.similar_docs,
                steps: prev.steps.map((step, index) => {
                  if (index === 3) return { ...step, status: 'waiting' }; // Mark similarity check as waiting
                  if (index > 3) return { ...step, status: 'pending' }; // Reset subsequent steps  
                  return step;
                })
              }));
              return;
            }

            // Handle normal progress updates
            if (stepIndex !== undefined) {
              console.log(`[Progress] Node: ${message.node}, Step: ${stepIndex}, updating to completed`);
              setUploadStatus(prev => ({
                ...prev,
                steps: prev.steps.map((step, index) => {
                  if (index === stepIndex) {
                    console.log(`[Progress] Step ${index} (${step.label}) -> completed`);
                    return { ...step, status: 'completed' };
                  }
                  if (index === stepIndex + 1 && stepIndex < initialSteps.length - 1) {
                    // Don't auto-activate if it's a decision step
                    const isDuplicateOrSimilarityCheck = index === 2 || index === 3;
                    const newStatus = isDuplicateOrSimilarityCheck ? 'pending' : 'active';
                    console.log(`[Progress] Step ${index} (${prev.steps[index]?.label}) -> ${newStatus}`);
                    return { ...step, status: newStatus };
                  }
                  return step;
                }),
                progress: Math.round(((stepIndex + 1) / initialSteps.length) * 100)
              }));
            }
          }

          // Handle workflow completion
          if (message.type === 'workflow_complete') {
            console.log('[DEBUG] WebSocket workflow_complete:', message);
            setUploadStatus(prev => ({
              ...prev,
              steps: prev.steps.map(step => ({ ...step, status: 'completed' })),
              progress: 100
            }));
          }

          // Handle errors
          if (message.type === 'workflow_error' || message.type === 'error') {
            const activeStepIndex = uploadStatus.steps.findIndex(s => s.status === 'active');
            setUploadStatus(prev => ({
              ...prev,
              steps: prev.steps.map((step, index) => 
                index === activeStepIndex ? { ...step, status: 'failed' } : step
              ),
              error: message.error || "Processing failed"
            }));
          }
        } catch (parseErr) {
          console.error('[DocumentUploadSection] Failed to parse WebSocket message:', parseErr);
        }
      };
    }

    try {
      // Start first step as active
      setUploadStatus(prev => ({
        ...prev,
        steps: prev.steps.map((step, index) => 
          index === 0 ? { ...step, status: 'active' } : step
        )
      }));

      // Prepare form data with session
      const formData = new FormData();
      formData.append("file", file);
      formData.append("tenant_id", tenantId.toString());
      formData.append("user_id", userId.toString());
      formData.append("visibility", visibility);
      formData.append("session_id", sessionId);
      formData.append("enable_streaming", "true");

      // TODO: Change to /documents when REST endpoint is ready
      const response = await fetch(`${API_BASE_URL}/workflows/process-document`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      console.log('[DEBUG] Full response data:', data);
      console.log('[DEBUG] Summary object:', data.summary);
      console.log('[DEBUG] Document ID:', data.document_id);

      // Check if workflow succeeded or failed
      if (data.status === "failed") {
        const errorMsg = data.error || data.summary?.error || "Processing failed";
        setUploadStatus(prev => ({ ...prev, error: errorMsg }));
        return;
      }

      // Success: display summary and complete all steps
      const summary = data.summary || {};
      const successMessage = `✅ "${summary.filename || file.name}" document successfully processed!\n` +
        `📄 Document ID: ${data.document_id}\n` +
        `📊 Content: ${summary.content_length || 0} characters\n` +
        `🧩 Chunks: ${summary.chunk_count || 0}\n` +
        `🔢 Embeddings: ${summary.embedding_count || 0}\n` +
        `💾 Qdrant vectors: ${summary.qdrant_vectors || 0}`;

      setUploadStatus(prev => ({
        ...prev,
        success: successMessage,
        // Mark all steps as completed
        steps: prev.steps.map(step => ({ ...step, status: 'completed' })),
        progress: 100
      }));

      // Notify parent component
      if (onUploadSuccess) {
        onUploadSuccess({
          filename: summary.filename || file.name,
          document_id: data.document_id,
          content_length: summary.content_length || 0,
          chunk_count: summary.chunk_count || 0,
          embedding_count: summary.embedding_count || 0,
          qdrant_vectors: summary.qdrant_vectors || 0
        });
      }

      // Reset form
      setFile(null);
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      if (fileInput) fileInput.value = "";

    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Upload failed";
      setUploadStatus(prev => ({ ...prev, error: errorMsg }));
    } finally {
      setUploadStatus(prev => ({ ...prev, isUploading: false }));
    }
  };

  const handleDecision = async (decision: "replace" | "keep_both" | "cancel", documentId?: number) => {
    if (!uploadStatus.sessionId) return;

    try {
      await fetch(`${API_BASE_URL}/documents/upload-decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: uploadStatus.sessionId,
          decision,
          document_id: documentId
        })
      });

      if (decision === "cancel") {
        setUploadStatus(prev => ({ 
          ...prev, 
          duplicateInfo: undefined,
          similarDocs: undefined,
          error: "Upload cancelled",
          isUploading: false 
        }));
      } else {
        setUploadStatus(prev => ({ 
          ...prev, 
          duplicateInfo: undefined,
          similarDocs: undefined
        }));
      }
    } catch (err) {
      setUploadStatus(prev => ({ ...prev, error: "Failed to send decision" }));
    }
  };

  return (
    <div className="upload-section">
      {/* File Selection */}
      <div className="form-group">
        <label htmlFor="file-input">Select File (PDF, TXT, MD):</label>
        <input
          id="file-input"
          type="file"
          accept=".pdf,.txt,.md"
          onChange={handleFileChange}
          disabled={uploadStatus.isUploading}
          className="file-input"
        />
        {file && (
          <div className="file-info">
            📎 <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)
          </div>
        )}
      </div>

      {/* Visibility Selection */}
      <div className="form-group">
        <label>Document Visibility:</label>
        <div className="radio-group">
          <label className="radio-label">
            <input
              type="radio"
              value="private"
              checked={visibility === "private"}
              onChange={(e) => setVisibility(e.target.value as "private")}
              disabled={uploadStatus.isUploading}
            />
            🔒 Private (only me)
          </label>
          <label className="radio-label">
            <input
              type="radio"
              value="tenant"
              checked={visibility === "tenant"}
              onChange={(e) => setVisibility(e.target.value as "tenant")}
              disabled={uploadStatus.isUploading}
            />
            🏢 Tenant-wide (all users)
          </label>
        </div>
      </div>

      {/* Upload Button */}
      <button
        onClick={handleUpload}
        disabled={!file || uploadStatus.isUploading}
        className="upload-button primary-button"
      >
        {uploadStatus.isUploading ? "Processing..." : "Upload Document"}
      </button>

      {/* Progress Steps */}
      {uploadStatus.steps.length > 0 && (
        <div className="progress-container">
          <div className="progress-header">
            <h4>Processing Progress ({uploadStatus.progress}%)</h4>
          </div>
          <ProgressSteps steps={uploadStatus.steps} />
        </div>
      )}

      {/* Duplicate Detection Panel */}
      {uploadStatus.duplicateInfo && !uploadStatus.error && !uploadStatus.success && (
        <div className="decision-panel duplicate-panel">
          <div className="panel-header">
            <h4>🔶 Duplicate Document Detected</h4>
          </div>
          <div className="panel-content">
            <p>
              <strong>"{uploadStatus.duplicateInfo.title}"</strong> already exists
              {uploadStatus.duplicateInfo.is_same_user 
                ? " (uploaded by you)" 
                : ` (uploaded by ${uploadStatus.duplicateInfo.owner_nickname})`}
            </p>
            <p className="upload-date">
              Uploaded: {new Date(uploadStatus.duplicateInfo.uploaded_at).toLocaleString()}
            </p>
          </div>
          <div className="decision-buttons">
            <button 
              className="btn-replace"
              onClick={() => handleDecision("replace", uploadStatus.duplicateInfo.document_id)}
            >
              🔄 Replace Old Version
            </button>
            <button 
              className="btn-keep-both"
              onClick={() => handleDecision("keep_both")}
            >
              ➕ Keep Both
            </button>
            <button 
              className="btn-cancel"
              onClick={() => handleDecision("cancel")}
            >
              ❌ Cancel Upload
            </button>
          </div>
        </div>
      )}

      {/* Similar Documents Panel */}
      {uploadStatus.similarDocs && !uploadStatus.error && !uploadStatus.success && !uploadStatus.duplicateInfo && (
        <div className="decision-panel similar-panel">
          <div className="panel-header">
            <h4>🔬 Similar Documents Found</h4>
          </div>
          <div className="panel-content">
            <p>Found {uploadStatus.similarDocs.length} document(s) with similar content:</p>
            <ul className="similar-docs-list">
              {uploadStatus.similarDocs.map((doc: any, idx: number) => (
                <li key={idx}>
                  <strong>{doc.title}</strong> ({(doc.similarity_score * 100).toFixed(1)}% match)
                  <p className="chunk-preview">{doc.chunk_preview}...</p>
                </li>
              ))}
            </ul>
          </div>
          <div className="decision-buttons">
            <button 
              className="btn-keep-both"
              onClick={() => handleDecision("keep_both")}
            >
              ✅ Continue Upload
            </button>
            <button 
              className="btn-cancel"
              onClick={() => handleDecision("cancel")}
            >
              ❌ Cancel Upload
            </button>
          </div>
        </div>
      )}

      {/* Error Message */}
      {uploadStatus.error && (
        <div className="message error">
          ❌ {uploadStatus.error}
        </div>
      )}

      {/* Success Message */}
      {uploadStatus.success && (
        <div className="message success">
          {uploadStatus.success}
        </div>
      )}
    </div>
  );
}