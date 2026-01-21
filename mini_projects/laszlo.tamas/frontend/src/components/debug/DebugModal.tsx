import { useEffect, useState } from "react";
import { DebugInfo, LongTermMemory } from "../../types";
import { fetchDebugInfo, deleteUserConversations, resetPostgres, resetQdrant, resetCache, fetchLongTermMemories } from "../../api";
import { useWorkflowState } from "../../hooks/useWorkflowState";
import { DebugWorkflowState } from "./DebugWorkflowState";
import { DebugCacheStats } from "./DebugCacheStats";
import { DebugUserData } from "./DebugUserData";
import { DebugResetActions } from "./DebugResetActions";
import { DebugPromptInspector } from "./DebugPromptInspector";
import "./DebugModal.css";

interface DebugModalProps {
  userId: number;
  tenantId: number;
  sessionId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onConversationsDeleted?: () => void;
  promptDetails?: any;  // From last chat response
}

/**
 * Debug Modal - SOLID Architecture
 * 
 * Single Responsibility: Orchestrates debug UI sections
 * Open/Closed: New sections added without modifying existing code
 * Dependency Inversion: Components injected via props
 */
export function DebugModal({ userId, tenantId, sessionId, isOpen, onClose, onConversationsDeleted, promptDetails }: DebugModalProps) {
  const [debugInfo, setDebugInfo] = useState<DebugInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isResettingPostgres, setIsResettingPostgres] = useState(false);
  const [isResettingQdrant, setIsResettingQdrant] = useState(false);
  const [isResettingCache, setIsResettingCache] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  // Accordion states
  const [accordionOpen, setAccordionOpen] = useState({
    userData: true,
    longTermMemory: false,
    workflowState: false,
    promptInspector: false,
    cacheStats: false,
    resetActions: false
  });

  // Long-term memory state
  const [longTermMemories, setLongTermMemories] = useState<LongTermMemory[]>([]);
  const [ltmCount, setLtmCount] = useState<number>(0);
  const [isLoadingLTM, setIsLoadingLTM] = useState(false);
  const [ltmError, setLtmError] = useState<string | null>(null);
  
  // Workflow state WebSocket (only enabled when accordion is open)
  const {
    stateHistory,
    latestState,
    currentNode,
    isConnected,
    clearHistory
  } = useWorkflowState({
    enabled: isOpen,  // Always collect when modal is open, not just when accordion is open
    sessionId: sessionId
  });

  const loadDebugInfo = () => {
    if (userId && tenantId) {
      setIsLoading(true);
      setError(null);
      fetchDebugInfo(userId, tenantId)
        .then(setDebugInfo)
        .catch((err) => {
          console.error("Failed to load debug info:", err);
          setError(err.message || "Failed to load debug information");
        })
        .finally(() => setIsLoading(false));
    }
  };

  // Initial load when modal opens
  useEffect(() => {
    if (isOpen && userId) {
      loadDebugInfo();
      // Clear workflow history when modal opens
      clearHistory();
    }
  }, [isOpen, userId]);
  
  const toggleAccordion = (section: keyof typeof accordionOpen) => {
    const wasOpen = accordionOpen[section];
    
    setAccordionOpen(prev => ({
      ...prev,
      [section]: !prev[section]
    }));

    // Lazy-load long-term memories when accordion opens (and not already loaded)
    if (section === 'longTermMemory' && !wasOpen && longTermMemories.length === 0) {
      loadLongTermMemories();
    }
  };

  const loadLongTermMemories = async () => {
    setIsLoadingLTM(true);
    setLtmError(null);
    try {
      const result = await fetchLongTermMemories(userId, 50);
      setLongTermMemories(result.memories);
      setLtmCount(result.count);
    } catch (err: any) {
      console.error("Failed to load long-term memories:", err);
      setLtmError(err.message || "Failed to load long-term memories");
    } finally {
      setIsLoadingLTM(false);
    }
  };
  
  const handleResetCache = async () => {
    const confirmed = window.confirm(
      "Are you sure you want to clear ALL caches?\n\nThis will clear:\n- Database cache (cached_prompts table)\n- Python memory cache\n\nThis action cannot be undone!"
    );

    if (!confirmed) return;

    setIsResettingCache(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const result = await resetCache();
      setSuccessMessage(`Cache cleared! DB rows: ${result.db_cleared}, Memory: ${result.memory_cleared ? 'Cleared' : 'Failed'}`);
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: any) {
      console.error("Failed to reset cache:", err);
      setError(err.message || "Failed to reset cache");
    } finally {
      setIsResettingCache(false);
    }
  };

  const handleResetPostgres = async () => {
    const confirmed = window.confirm(
      "Are you sure you want to delete ALL documents and chunks from PostgreSQL?\n\nThis will remove all uploaded documents and their metadata.\n\nThis action cannot be undone!"
    );

    if (!confirmed) return;

    setIsResettingPostgres(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const result = await resetPostgres();
      setSuccessMessage(`PostgreSQL reset successful! Deleted ${result.documents_deleted} documents and ${result.chunks_deleted} chunks.`);
      setTimeout(() => setSuccessMessage(null), 5000);
      loadDebugInfo();
    } catch (err: any) {
      console.error("Failed to reset PostgreSQL:", err);
      setError(err.message || "Failed to reset PostgreSQL");
    } finally {
      setIsResettingPostgres(false);
    }
  };

  const handleResetQdrant = async () => {
    const confirmed = window.confirm(
      "Are you sure you want to delete ALL document vectors from Qdrant?\n\nThis will remove all document embeddings from the vector database.\n\nThis action cannot be undone!"
    );

    if (!confirmed) return;

    setIsResettingQdrant(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const result = await resetQdrant();
      setSuccessMessage(`Qdrant reset successful! ${result.message}`);
      setTimeout(() => setSuccessMessage(null), 5000);
      loadDebugInfo();
    } catch (err: any) {
      console.error("Failed to reset Qdrant:", err);
      setError(err.message || "Failed to reset Qdrant");
    } finally {
      setIsResettingQdrant(false);
    }
  };

  const handleDeleteConversations = async () => {
    if (!debugInfo) return;

    const confirmed = window.confirm(
      `Are you sure you want to delete all conversation history for user ${debugInfo.user_data.firstname} ${debugInfo.user_data.lastname}?\n\nThis action cannot be undone!`
    );

    if (!confirmed) return;

    setIsDeleting(true);
    setError(null);

    try {
      await deleteUserConversations(userId);
      setSuccessMessage("Chat history deleted successfully!");
      setTimeout(() => setSuccessMessage(null), 3000);
      loadDebugInfo();
      if (onConversationsDeleted) {
        onConversationsDeleted();
      }
    } catch (err: any) {
      console.error("Failed to delete conversations:", err);
      setError(err.message || "Failed to delete conversation history");
    } finally {
      setIsDeleting(false);
    }
  };

  if (!isOpen) return null;

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString("hu-HU");
  };

  return (
    <div className="debug-panel">
      <div className="debug-panel-header">
        <h2>Debug Information</h2>
        <div className="debug-panel-controls">
          <button className="debug-panel-close" onClick={onClose}>
            ×
          </button>
        </div>
      </div>

      <div className="debug-panel-content">
          {isLoading && <div className="debug-loading">Loading...</div>}
          
          {error && <div className="debug-error">{error}</div>}
          {successMessage && <div className="debug-success">{successMessage}</div>}
          
          {debugInfo && (
            <>
              {/* ACCORDION 1: User Data */}
              <DebugUserData 
                debugInfo={debugInfo}
                isOpen={accordionOpen.userData}
                onToggle={() => toggleAccordion('userData')}
                formatTimestamp={formatTimestamp}
              />

              {/* ACCORDION 2: Long-term Memory */}
              <section className="debug-section">
                <div 
                  className="debug-accordion-header"
                  onClick={() => toggleAccordion('longTermMemory')}
                  style={{ cursor: 'pointer', userSelect: 'none' }}
                >
                  <h3>
                    {accordionOpen.longTermMemory ? '▼' : '▶'} 🧠 Long-term Memory ({ltmCount})
                  </h3>
                </div>
                {accordionOpen.longTermMemory && (
                  <div style={{ marginTop: '10px' }}>
                    {isLoadingLTM && <div className="debug-loading">Loading memories...</div>}
                    {ltmError && <div className="debug-error">{ltmError}</div>}
                    {!isLoadingLTM && !ltmError && longTermMemories.length === 0 && (
                      <div style={{ color: '#888', fontStyle: 'italic' }}>No long-term memories yet</div>
                    )}
                    {longTermMemories.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {longTermMemories.map((memory) => (
                          <div 
                            key={memory.id} 
                            style={{ 
                              padding: '10px', 
                              backgroundColor: 'rgba(255,255,255,0.05)', 
                              borderRadius: '5px',
                              borderLeft: memory.memory_type === 'explicit_fact' ? '3px solid #4CAF50' : '3px solid #2196F3'
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                              <span style={{ 
                                fontSize: '0.85em', 
                                fontWeight: 'bold',
                                color: memory.memory_type === 'explicit_fact' ? '#4CAF50' : '#2196F3'
                              }}>
                                {memory.memory_type === 'explicit_fact' ? '💡 Explicit Fact' : '📝 Session Summary'}
                              </span>
                              <span style={{ fontSize: '0.8em', color: '#888' }}>
                                {formatTimestamp(memory.created_at)}
                              </span>
                            </div>
                            <div style={{ marginBottom: '5px', lineHeight: '1.4' }}>
                              {memory.content}
                            </div>
                            <div style={{ fontSize: '0.75em', color: '#666' }}>
                              Source: {memory.source}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </section>

              {/* ACCORDION 3: Workflow State (WebSocket) */}
              <section className="debug-section">
                <div 
                  className="debug-accordion-header"
                  onClick={() => toggleAccordion('workflowState')}
                  style={{ cursor: 'pointer', userSelect: 'none' }}
                >
                  <h3>
                    {accordionOpen.workflowState ? '▼' : '▶'} 🔄 Workflow State (Real-time)
                  </h3>
                </div>
                {accordionOpen.workflowState && (
                  <div style={{ marginTop: '10px' }}>
                    <DebugWorkflowState
                      stateHistory={stateHistory}
                      latestState={latestState}
                      currentNode={currentNode}
                      isConnected={isConnected}
                    />
                  </div>
                )}
              </section>

              {/* ACCORDION 4: Prompt Inspector */}
              <DebugPromptInspector 
                promptDetails={promptDetails}
                isOpen={accordionOpen.promptInspector}
                onToggle={() => toggleAccordion('promptInspector')}
              />

              {/* ACCORDION 5: Cache Statistics (P0.17) */}
              <DebugCacheStats />

              {/* ACCORDION 6: Reset Actions */}
              <DebugResetActions
                isOpen={accordionOpen.resetActions}
                onToggle={() => toggleAccordion('resetActions')}
                isDeleting={isDeleting}
                isResettingPostgres={isResettingPostgres}
                isResettingQdrant={isResettingQdrant}
                isResettingCache={isResettingCache}
                onDeleteHistory={handleDeleteConversations}
                onResetPostgres={handleResetPostgres}
                onResetQdrant={handleResetQdrant}
                onResetCache={handleResetCache}
              />
            </>
          )}
        </div>
    </div>
  );
}
