import React, { useEffect, useMemo, useState } from "react";
import ChatPanel, { ChatMessage } from "./components/ChatPanel";
import DebugSidebar, { DebugInfo } from "./components/DebugSidebar";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
};

type StoredMessage = {
  id: string;
  conversation_id: string;
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  created_at: string;
  metadata?: Record<string, unknown>;
};

const uuidv4 = () =>
  (crypto?.randomUUID?.() ||
    "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    }));

const toChatMessages = (messages: StoredMessage[]): ChatMessage[] =>
  messages.map((msg) => ({
    role: msg.role === "tool" ? "assistant" : (msg.role as "user" | "assistant"),
    content: msg.content,
    timestamp: msg.created_at,
  }));

const STORAGE_KEYS = {
  conversations: "kr-conversations",
  messages: "kr-messages",
  activeConversation: "kr-active-conversation",
  userId: "kr-user",
};

const loadConversations = (): Conversation[] => {
  const raw = localStorage.getItem(STORAGE_KEYS.conversations);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as Conversation[];
  } catch {
    return [];
  }
};

const loadMessages = (): Record<string, StoredMessage[]> => {
  const raw = localStorage.getItem(STORAGE_KEYS.messages);
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, StoredMessage[]>;
  } catch {
    return {};
  }
};

const App: React.FC = () => {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [debugByConversation, setDebugByConversation] = useState<
    Record<string, DebugInfo | undefined>
  >({});

  const userId = useMemo(() => {
    const cached = localStorage.getItem(STORAGE_KEYS.userId);
    if (cached) return cached;
    const newId = `user-${uuidv4()}`;
    localStorage.setItem(STORAGE_KEYS.userId, newId);
    return newId;
  }, []);

  const [conversations, setConversations] = useState<Conversation[]>(() =>
    loadConversations()
  );
  const [messagesByConversation, setMessagesByConversation] = useState<
    Record<string, StoredMessage[]>
  >(() => loadMessages());
  const [activeConversationId, setActiveConversationId] = useState(() =>
    localStorage.getItem(STORAGE_KEYS.activeConversation)
  );

  const visibleConversations = useMemo(
    () => conversations.filter((c) => !c.deleted_at),
    [conversations]
  );

  const ensureActiveConversation = () => {
    if (activeConversationId && visibleConversations.some((c) => c.id === activeConversationId)) {
      return;
    }
    if (visibleConversations.length > 0) {
      setActiveConversationId(visibleConversations[0].id);
      return;
    }
    const now = new Date().toISOString();
    const newConversation: Conversation = {
      id: uuidv4(),
      title: "New Conversation",
      created_at: now,
      updated_at: now,
      deleted_at: null,
    };
    setConversations([newConversation]);
    setMessagesByConversation((prev) => ({ ...prev, [newConversation.id]: [] }));
    setActiveConversationId(newConversation.id);
  };

  useEffect(() => {
    ensureActiveConversation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleConversations.length]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.conversations, JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.messages, JSON.stringify(messagesByConversation));
  }, [messagesByConversation]);

  useEffect(() => {
    if (activeConversationId) {
      localStorage.setItem(STORAGE_KEYS.activeConversation, activeConversationId);
    }
  }, [activeConversationId]);

  const startNewConversation = () => {
    const now = new Date().toISOString();
    const newConversation: Conversation = {
      id: uuidv4(),
      title: "New Conversation",
      created_at: now,
      updated_at: now,
      deleted_at: null,
    };
    setConversations((prev) => [newConversation, ...prev]);
    setMessagesByConversation((prev) => ({ ...prev, [newConversation.id]: [] }));
    setActiveConversationId(newConversation.id);
    setInput("");
  };

  const deleteConversation = (conversationId: string) => {
    setConversations((prev) =>
      prev.map((conv) =>
        conv.id === conversationId
          ? { ...conv, deleted_at: new Date().toISOString() }
          : conv
      )
    );

    if (activeConversationId === conversationId) {
      const remaining = visibleConversations.filter((c) => c.id !== conversationId);
      if (remaining.length > 0) {
        setActiveConversationId(remaining[0].id);
      } else {
        startNewConversation();
      }
    }
  };

  const updateConversationMeta = (
    conversationId: string,
    updates: Partial<Conversation>
  ) => {
    setConversations((prev) =>
      prev
        .map((conv) =>
          conv.id === conversationId ? { ...conv, ...updates } : conv
        )
        .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
    );
  };

  const activeMessages = activeConversationId
    ? messagesByConversation[activeConversationId] || []
    : [];

  const submit = async () => {
    if (!input.trim() || !activeConversationId) return;

    const now = new Date().toISOString();
    const userMessage: StoredMessage = {
      id: uuidv4(),
      conversation_id: activeConversationId,
      role: "user",
      content: input.trim(),
      created_at: now,
    };

    setMessagesByConversation((prev) => ({
      ...prev,
      [activeConversationId]: [...(prev[activeConversationId] || []), userMessage],
    }));

    updateConversationMeta(activeConversationId, {
      title:
        activeMessages.length === 0
          ? input.trim().slice(0, 48)
          : conversations.find((c) => c.id === activeConversationId)?.title ||
            "Conversation",
      updated_at: now,
    });

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          session_id: activeConversationId,
          message: input.trim(),
          metadata: { client: "web" },
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      const mappedMessages: StoredMessage[] = (data.history || []).map(
        (item: any) => ({
          id: uuidv4(),
          conversation_id: activeConversationId,
          role: item.role,
          content: item.content,
          created_at: item.timestamp || new Date().toISOString(),
          metadata: item.metadata || {},
        })
      );

      setMessagesByConversation((prev) => ({
        ...prev,
        [activeConversationId]: mappedMessages,
      }));
      setDebugByConversation((prev) => ({
        ...prev,
        [activeConversationId]: data.debug,
      }));
      updateConversationMeta(activeConversationId, {
        updated_at: new Date().toISOString(),
      });
    } catch (error) {
      const errorMessage: StoredMessage = {
        id: uuidv4(),
        conversation_id: activeConversationId,
        role: "assistant",
        content:
          error instanceof Error
            ? error.message
            : "Unexpected error contacting the API.",
        created_at: new Date().toISOString(),
      };

      setMessagesByConversation((prev) => ({
        ...prev,
        [activeConversationId]: [
          ...(prev[activeConversationId] || []),
          errorMessage,
        ],
      }));
    } finally {
      setInput("");
      setLoading(false);
    }
  };

  const formatTimestamp = (iso?: string) => {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <header
        style={{
          padding: "1rem",
          borderBottom: "1px solid #e5e5e5",
          backgroundColor: "#fff",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h2 style={{ margin: 0 }}>KnowledgeRouter Chat</h2>
        <div className="uk-text-meta">User: {userId.slice(0, 12)}…</div>
      </header>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <div
          style={{
            flex: 1,
            backgroundColor: "#f8f9fa",
            padding: "1rem",
            borderRight: "1px solid #e5e5e5",
            overflow: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
          }}
        >
          <div>
            <div className="uk-flex uk-flex-between uk-flex-middle uk-margin-small-bottom">
              <h4 className="uk-text-bold uk-margin-remove">Conversations</h4>
              <button
                className="uk-button uk-button-primary uk-button-small"
                onClick={startNewConversation}
                disabled={loading}
              >
                + New Conversation
              </button>
            </div>
            <div className="uk-list uk-list-divider">
              {visibleConversations.length === 0 && (
                <div className="uk-text-meta">No conversations yet.</div>
              )}
              {visibleConversations.map((conv) => {
                const convMessages = messagesByConversation[conv.id] || [];
                const lastMessage = convMessages[convMessages.length - 1];
                const preview = lastMessage?.content?.slice(0, 60) || "";
                const isActive = conv.id === activeConversationId;
                return (
                  <div
                    key={conv.id}
                    className={`uk-card uk-card-small uk-card-default uk-margin-small ${
                      isActive ? "uk-card-primary" : ""
                    }`}
                    style={{ cursor: "pointer", padding: "0.5rem" }}
                    onClick={() => setActiveConversationId(conv.id)}
                  >
                    <div className="uk-flex uk-flex-between">
                      <div>
                        <div className="uk-text-bold">
                          {conv.title || "Conversation"}
                        </div>
                        <div className="uk-text-meta">
                          {formatTimestamp(conv.updated_at)}
                        </div>
                      </div>
                      <button
                        className="uk-button uk-button-text"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConversation(conv.id);
                        }}
                        title="Delete conversation"
                      >
                        🗑️
                      </button>
                    </div>
                    {preview && (
                      <div className="uk-text-small uk-text-muted">{preview}</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div
          style={{
            flex: 2,
            display: "flex",
            flexDirection: "column",
            backgroundColor: "#fff",
            overflow: "hidden",
          }}
        >
          <ChatPanel
            messages={toChatMessages(activeMessages)}
            input={input}
            loading={loading}
            onInputChange={setInput}
            onSend={submit}
          />
        </div>

        <div
          style={{
            flex: 1,
            backgroundColor: "#f8f9fa",
            borderLeft: "1px solid #e5e5e5",
            padding: "1rem",
            overflow: "auto",
          }}
        >
          <DebugSidebar debug={debugByConversation[activeConversationId || ""]} />
        </div>
      </div>
    </div>
  );
};

export default App;
