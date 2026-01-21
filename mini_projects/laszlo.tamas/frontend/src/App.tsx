import { useState, useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import { User, Message } from "./types";
import { fetchUsers, sendChatMessage, fetchSessionMessages, consolidateSession, fetchIdleTimeout, warmupCaches } from "./api";
import { STORAGE_KEYS } from "./config/constants";
import { UserDropdown } from "./components/UserDropdown";
import { TenantDropdown } from "./components/TenantDropdown";
import { ChatWindow } from "./components/chat/ChatWindow";
import { ChatInput, ChatInputRef } from "./components/chat/ChatInput";
import { DebugModal } from "./components/debug/DebugModal";
import { DocumentManagement } from "./components/documents/DocumentManagement";
import { Sidebar, SidebarRef } from "./components/session/Sidebar";
import { WorkflowModal } from "./components/workflow/WorkflowModal"; // NEW: Workflow visualizer
import "./App.css";

// Idle timeout (fetched from backend, default: 5 minutes)
let IDLE_TIMEOUT_MS = 5 * 60 * 1000;

function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDebugOpen, setIsDebugOpen] = useState(false);
  const [isDocumentManagementOpen, setIsDocumentManagementOpen] = useState(false);
  const [isWorkflowOpen, setIsWorkflowOpen] = useState(false); // NEW: Workflow modal state
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null); // NEW: Selected workflow
  const [promptDetails, setPromptDetails] = useState<any>(null);
  const chatInputRef = useRef<ChatInputRef>(null);
  const sidebarRef = useRef<SidebarRef>(null);
  
  // Idle timer for auto-consolidation
  const idleTimerRef = useRef<number | null>(null);
  const lastActivityRef = useRef<number>(Date.now());

  // NEW: Handle workflow visualization
  const handleWorkflowClick = (executionId: string) => {
    setSelectedExecutionId(executionId);
    setIsWorkflowOpen(true);
  };

  const handleCloseWorkflow = () => {
    setIsWorkflowOpen(false);
    setSelectedExecutionId(null);
  };

  // Helper: Consolidate current session (STM → LTM)
  const consolidateCurrentSession = async () => {
    if (!activeSessionId || !selectedUserId || !selectedTenantId) return;
    
    console.log(`🔄 Consolidating session: ${activeSessionId}`);
    
    // Stop idle timer during consolidation to prevent loops
    if (idleTimerRef.current) {
      window.clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
    
    try {
      const result = await consolidateSession(activeSessionId, selectedUserId, selectedTenantId);
      console.log(`✅ Consolidation result:`, result);
      
      if (result.status === "success" && result.facts_extracted > 0) {
        console.log(`💾 Extracted ${result.facts_extracted} facts from session`);
      }
    } catch (error) {
      console.error("❌ Consolidation failed:", error);
      // Silent failure - don't interrupt user experience
    }
  };

  // Helper: Reset idle timer
  const resetIdleTimer = () => {
    lastActivityRef.current = Date.now();
    
    // Clear existing timer
    if (idleTimerRef.current) {
      window.clearTimeout(idleTimerRef.current);
    }
    
    // Set new timer
    idleTimerRef.current = window.setTimeout(() => {
      console.log(`⏰ Session idle for ${IDLE_TIMEOUT_MS / 1000}s - triggering consolidation`);
      consolidateCurrentSession();
    }, IDLE_TIMEOUT_MS);
  };

  // Reset idle timer on user activity
  useEffect(() => {
    const handleActivity = () => resetIdleTimer();
    
    // Track activity events
    window.addEventListener('mousemove', handleActivity);
    window.addEventListener('keydown', handleActivity);
    window.addEventListener('click', handleActivity);
    
    // Initial timer
    resetIdleTimer();
    
    // Cleanup
    return () => {
      window.removeEventListener('mousemove', handleActivity);
      window.removeEventListener('keydown', handleActivity);
      window.removeEventListener('click', handleActivity);
      
      if (idleTimerRef.current) {
        window.clearTimeout(idleTimerRef.current);
      }
    };
  }, [activeSessionId, selectedUserId, selectedTenantId]);

  // Fetch idle timeout from backend on mount
  useEffect(() => {
    fetchIdleTimeout()
      .then(data => {
        IDLE_TIMEOUT_MS = data.idle_timeout_seconds * 1000;
        console.log(`⏰ Idle timeout set to ${data.idle_timeout_seconds}s (${IDLE_TIMEOUT_MS}ms)`);
      })
      .catch(err => {
        console.warn("Failed to fetch idle timeout, using default 5min:", err);
      });
  }, []);

  // Load users when tenant changes
  useEffect(() => {
    if (selectedTenantId) {
      fetchUsers(selectedTenantId)
        .then((data) => {
          setUsers(data);
          
          // Try to restore last selected user for this tenant
          const savedUserId = localStorage.getItem(STORAGE_KEYS.lastUserId(selectedTenantId));
          
          if (savedUserId) {
            const savedUserIdNum = Number(savedUserId);
            const userExists = data.find(u => u.user_id === savedUserIdNum);
            if (userExists) {
              // Restore saved user for this tenant
              handleUserChange(savedUserIdNum);
              return;
            }
          }
          
          // If no saved user or user doesn't exist, auto-select first user
          if (data.length > 0) {
            handleUserChange(data[0].user_id);
          } else {
            // No users for this tenant
            setSelectedUserId(null);
            setMessages([]);
          }
        })
        .catch((err) => {
          console.error("Failed to load users:", err);
          setError("Failed to load users for selected tenant.");
          setUsers([]);
        });
    }
  }, [selectedTenantId]);

  // Handle user change
  const handleUserChange = async (userId: number) => {
    setSelectedUserId(userId);
    
    // Save this user selection for the current tenant
    if (selectedTenantId) {
      localStorage.setItem(STORAGE_KEYS.lastUserId(selectedTenantId), userId.toString());
    }
    
    const storedSessionId = localStorage.getItem(STORAGE_KEYS.sessionId(userId));
    let sessionIdToUse: string;
    if (!storedSessionId) {
      sessionIdToUse = uuidv4();
      localStorage.setItem(STORAGE_KEYS.sessionId(userId), sessionIdToUse);
    } else {
      sessionIdToUse = storedSessionId;
    }
    setSessionId(sessionIdToUse);
    setError(null);

    // === EAGER CACHE WARMUP (Performance Optimization) ===
    // Pre-load tenant, user, and system prompt caches BEFORE first message
    // Eliminates 800-1200ms cold start latency on first chat request
    if (selectedTenantId) {
      console.log(`🔥 Warming up caches for user ${userId}...`);
      warmupCaches(selectedTenantId, userId)
        .then(result => {
          if (result.success) {
            const wasCold = !result.tenant_cached || !result.user_cached || !result.system_prompt_cached;
            if (wasCold) {
              console.log(`✅ Cache warmup: ${result.total_time_ms}ms (${result.cache_source}) - First message will be FAST!`);
            } else {
              console.log(`✅ Cache warmup: ${result.total_time_ms}ms (all cached) - Already warm`);
            }
          }
        })
        .catch(err => {
          console.warn('Cache warmup failed (non-blocking):', err);
        });
    }

    // Load previous messages if session exists
    if (storedSessionId) {
      try {
        const previousMessages = await fetchSessionMessages(storedSessionId, userId);
        setMessages(previousMessages);
      } catch (err) {
        console.error("Failed to load previous messages:", err);
        setMessages([]);
      }
    } else {
      setMessages([]);
    }

    // Focus input after user change
    setTimeout(() => {
      chatInputRef.current?.focus();
    }, 0);
  };

  // Handle new chat creation
  const handleNewChat = async () => {
    if (!selectedUserId) return;
    
    // Consolidate previous session (non-blocking, fire-and-forget)
    // Only consolidate if there are messages (don't try to consolidate empty sessions)
    if (activeSessionId && selectedTenantId && messages.length > 0) {
      consolidateCurrentSession(); // No await - background consolidation
    }
    
    const newSessionId = uuidv4();
    localStorage.setItem(STORAGE_KEYS.activeSessionId(selectedUserId), newSessionId);
    setActiveSessionId(newSessionId);
    setSessionId(newSessionId);
    setMessages([]);
    setError(null);
    
    // Reset idle timer for new session
    resetIdleTimer();
    
    // Focus input
    setTimeout(() => {
      chatInputRef.current?.focus();
    }, 0);
  };

  // Handle session selection
  const handleSessionSelect = async (selectedSessionId: string) => {
    if (!selectedUserId) return;
    
    // Consolidate previous session (non-blocking, fire-and-forget)
    // Only consolidate if switching sessions AND there are messages (don't consolidate empty sessions)
    if (activeSessionId && activeSessionId !== selectedSessionId && selectedTenantId && messages.length > 0) {
      consolidateCurrentSession(); // No await - background consolidation
    }
    
    // Optimistic UI: Switch immediately, load messages in background
    localStorage.setItem(STORAGE_KEYS.activeSessionId(selectedUserId), selectedSessionId);
    setActiveSessionId(selectedSessionId);
    setSessionId(selectedSessionId);
    setMessages([]); // Clear immediately for instant switch
    setError(null);
    setIsLoadingMessages(true);
    
    // Reset idle timer for new session
    resetIdleTimer();
    
    // Load messages in background (non-blocking UI)
    fetchSessionMessages(selectedSessionId, selectedUserId!)
      .then(previousMessages => {
        setMessages(previousMessages);
        setIsLoadingMessages(false);
      })
      .catch(err => {
        console.error("Failed to load session messages:", err);
        setError("Failed to load session history");
        setIsLoadingMessages(false);
      });
  };

  // Handle session deletion
  const handleSessionDelete = (deletedSessionId: string) => {
    // If deleted session was active, clear messages
    if (deletedSessionId === activeSessionId) {
      setMessages([]);
      setActiveSessionId(null);
      setSessionId("");
    }
  };

  // Handle session rename (just update local state if needed)
  const handleSessionRename = (renamedSessionId: string, newTitle: string) => {
    // Could update UI if showing session title in header
    console.log(`Session ${renamedSessionId} renamed to: ${newTitle}`);
  };

  // Restore active session on user change
  useEffect(() => {
    if (selectedUserId) {
      const savedActiveSessionId = localStorage.getItem(`activeSessionId_user_${selectedUserId}`);
      if (savedActiveSessionId) {
        setActiveSessionId(savedActiveSessionId);
        setSessionId(savedActiveSessionId);
        // Load messages
        fetchSessionMessages(savedActiveSessionId, selectedUserId)
          .then(setMessages)
          .catch(() => setMessages([]));
      } else {
        // Create new session
        handleNewChat();
      }
    }
  }, [selectedUserId]);

  // Handle sending a message
  const handleSendMessage = async (messageContent: string) => {
    if (!selectedUserId || !sessionId || !selectedTenantId) return;

    // Add user message to UI
    const userMessage: Message = {
      role: "user",
      content: messageContent,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);
    
    // Start timer
    const startTime = Date.now();

    try {
      const response = await sendChatMessage({
        user_id: selectedUserId,
        tenant_id: selectedTenantId,
        session_id: sessionId,
        message: messageContent,
      });
      
      // Calculate response time
      const endTime = Date.now();
      const responseTimeMs = endTime - startTime;

      // Add assistant message to UI
      const assistantMessage: Message = {
        role: "assistant",
        content: response.answer,
        timestamp: new Date().toISOString(),
        sources: response.sources,
        responseTime: responseTimeMs,
        ragParams: response.rag_params,
        promptDetails: response.prompt_details,
        metadata: {
          execution_id: response.execution_id,
        },
      };
      setMessages((prev) => [...prev, assistantMessage]);
      
      // Store prompt details for Debug Modal
      console.log('📋 API Response prompt_details:', response.prompt_details);
      if (response.prompt_details) {
        console.log('📋 Setting promptDetails state:', response.prompt_details);
        console.log('📋 actual_llm_messages count:', response.prompt_details.actual_llm_messages?.length);
        setPromptDetails(response.prompt_details);
      } else {
        console.warn('⚠️ No prompt_details in API response!');
      }
      
      // Refresh sidebar to show updated session
      sidebarRef.current?.refreshSessions();
      
      // Focus the input after assistant response
      setTimeout(() => {
        chatInputRef.current?.focus();
      }, 100);
    } catch (err) {
      console.error("Failed to send message:", err);
      const errorMsg = err instanceof Error ? err.message : "Failed to send message";
      setError(errorMsg);
      
      // Add error message to chat
      const errorMessage: Message = {
        role: "assistant",
        content: `Error: ${errorMsg}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const selectedUser = users.find((u) => u.user_id === selectedUserId);
  const [appVersion, setAppVersion] = useState<string>("");

  // Fetch app version
  useEffect(() => {
    fetch(`/api/version`)
      .then(res => res.json())
      .then(data => {
        setAppVersion(data.version);
        document.title = `Knowledge Router ${data.version}`; // Update browser tab title
      })
      .catch(() => {
        setAppVersion("0.2.0");
        document.title = "Knowledge Router 0.2.0"; // Fallback title
      });
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>{appVersion ? `Knowledge Router ${appVersion}` : "Knowledge Router"}</h1>
        <div className="header-controls">
          <TenantDropdown
            selectedTenantId={selectedTenantId}
            onTenantChange={setSelectedTenantId}
          />
          <UserDropdown
            users={users}
            selectedUserId={selectedUserId}
            onUserChange={handleUserChange}
          />
        </div>
      </header>

      {selectedUserId && (
        <>
          <button 
            className="debug-button" 
            onClick={() => setIsDebugOpen(!isDebugOpen)}
            title="Debug információk"
          >
            🐛 Debug
          </button>
        </>
      )}

      {error && <div className="error-banner">{error}</div>}

      {selectedUser && (
        <div className="user-info">
          Chatting as: <strong>{selectedUser.firstname} {selectedUser.lastname}</strong> 
          ({selectedUser.role})
        </div>
      )}

      <div className="app-main">
        <div className="page-wrapper">
          <main className="chat-section">
            {/* Sidebar with session list */}
            {selectedUserId && (
              <Sidebar
                ref={sidebarRef}
                userId={selectedUserId}
                activeSessionId={activeSessionId}
                onSessionSelect={handleSessionSelect}
                onNewChat={handleNewChat}
                onSessionDelete={handleSessionDelete}
                onSessionRename={handleSessionRename}
              />
            )}

            <div className="chat-container">
              <ChatWindow 
                messages={messages} 
                isLoading={isLoading || isLoadingMessages}
                onWorkflowClick={handleWorkflowClick}
              />
              
              <footer className="app-footer">
                <ChatInput
                  ref={chatInputRef}
                  onSendMessage={handleSendMessage}
                  disabled={!selectedUserId}
                  isLoading={isLoading}
                  hasDocumentManagement={!!selectedUserId && !!selectedTenantId}
                  onDocumentManagementClick={() => setIsDocumentManagementOpen(true)}
                />
              </footer>
            </div>
          </main>

          {selectedUserId && selectedTenantId && isDebugOpen && (
            <aside className="sidebar-right">
              <DebugModal
                userId={selectedUserId}
                tenantId={selectedTenantId}
                sessionId={activeSessionId}
                isOpen={isDebugOpen}
                onClose={() => setIsDebugOpen(false)}
                onConversationsDeleted={() => setMessages([])}
                promptDetails={promptDetails}
              />
            </aside>
          )}
        </div>
      </div>

      {/* Document Management Modal */}
      {selectedUserId && selectedTenantId && (
        <DocumentManagement
          tenantId={selectedTenantId}
          userId={selectedUserId}
          isOpen={isDocumentManagementOpen}
          onClose={() => setIsDocumentManagementOpen(false)}
        />
      )}

      {/* Workflow Visualizer Modal */}
      <WorkflowModal
        executionId={selectedExecutionId}
        isOpen={isWorkflowOpen}
        onClose={handleCloseWorkflow}
      />
    </div>
  );
}

export default App;
