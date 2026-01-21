import React, { useState } from 'react';

interface ActualLLMMessage {
  type: string;
  content: string;
  annotation?: string;  // NEW: Message annotation (e.g., "lean_system_prompt", "chat_intent_hint")
  metadata?: Record<string, any>;  // NEW: Additional context (iteration, source, etc.)
}

interface PromptDetails {
  system_prompt?: string;
  chat_history?: any[];
  current_query?: string;
  cache_source?: string;
  user_firstname?: string;
  user_lastname?: string;
  chat_history_count?: number;
  actions_taken?: string[];
  short_term_memory_messages?: number;
  short_term_memory_scope?: string;
  actual_llm_messages?: ActualLLMMessage[];
  llm_cache_info?: {
    prompt_tokens: number;
    cached_tokens: number;
    uncached_tokens: number;
    cache_hit_rate: number;
    completion_tokens: number;
  };
}

interface PromptInspectorProps {
  promptDetails: PromptDetails | null;
  isOpen: boolean;
  onToggle: () => void;
}

export const DebugPromptInspector: React.FC<PromptInspectorProps> = ({ promptDetails, isOpen, onToggle }) => {
  const [systemPromptOpen, setSystemPromptOpen] = useState(false);
  const [dynamicPromptOpen, setDynamicPromptOpen] = useState(false);

  const estimateTokens = (text: string) => {
    if (!text) return 0;
    return Math.ceil(text.length / 4);
  };

  const formatCounts = (text: string) => {
    const chars = text.length;
    const tokens = estimateTokens(text);
    return `${chars} Char / ${tokens} Tok`;
  };

  const splitStaticDynamic = (text: string) => {
    const marker = "\n\nCURRENT CONTEXT:";
    const idx = text.indexOf(marker);
    if (idx === -1) {
      return { staticText: text, dynamicText: "" };
    }
    return {
      staticText: text.slice(0, idx),
      dynamicText: text.slice(idx)
    };
  };

  return (
    <section className="debug-section">
      <div 
        className="debug-accordion-header"
        onClick={onToggle}
        style={{ cursor: 'pointer', userSelect: 'none' }}
      >
        <h3>
          {isOpen ? '▼' : '▶'} 🔍 Prompt Inspector (Last Response)
        </h3>
      </div>
      {isOpen && (
        <div style={{ marginTop: '10px' }}>
          {!promptDetails || !promptDetails.actual_llm_messages || promptDetails.actual_llm_messages.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#64748b', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
              <p>No LLM messages yet. Send a message to see the prompt details.</p>
            </div>
          ) : (
            <>
              {/* Header Info */}
              <div style={{ 
                padding: '12px 16px', 
                backgroundColor: '#f8fafc', 
                borderRadius: '6px', 
                marginBottom: '12px',
                display: 'flex',
                gap: '16px',
                flexWrap: 'wrap',
                fontSize: '13px',
                color: '#334155',
                border: '1px solid #e2e8f0'
              }}>
                {/* OpenAI Prompt Cache Indicator */}
                {promptDetails.llm_cache_info && promptDetails.llm_cache_info.prompt_tokens > 0 && (
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 10px',
                    borderRadius: '9999px',
                    fontSize: '12px',
                    fontWeight: '600',
                    backgroundColor: promptDetails.llm_cache_info.cache_hit_rate > 50 ? '#d1fae5' : '#fef3c7',
                    color: promptDetails.llm_cache_info.cache_hit_rate > 50 ? '#065f46' : '#78350f'
                  }}>
                    <span style={{
                      display: 'inline-block',
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: promptDetails.llm_cache_info.cache_hit_rate > 50 ? '#10b981' : '#f59e0b'
                    }}></span>
                    Cache: {promptDetails.llm_cache_info.cache_hit_rate.toFixed(1)}%
                    <span style={{ fontSize: '11px', opacity: 0.8 }}>
                      ({promptDetails.llm_cache_info.cached_tokens}/{promptDetails.llm_cache_info.prompt_tokens} tokens)
                    </span>
                  </span>
                )}
                
                {promptDetails.cache_source && (
                  <span>
                    <strong>Cache:</strong> {promptDetails.cache_source === 'memory' ? '🟢 Memory' : promptDetails.cache_source === 'database' ? '🟡 Database' : '🔵 Fresh'}
                  </span>
                )}
                {promptDetails.user_firstname && (
                  <span>
                    <strong>User:</strong> {promptDetails.user_firstname} {promptDetails.user_lastname}
                  </span>
                )}
                {promptDetails.chat_history_count !== undefined && (
                  <span>
                    <strong>History:</strong> {promptDetails.chat_history_count} messages
                  </span>
                )}
                {promptDetails.short_term_memory_messages !== undefined && (
                  <span>
                    📦 <strong>SHORT_TERM_MEMORY_MESSAGES</strong> = {promptDetails.short_term_memory_messages}
                  </span>
                )}
                {promptDetails.short_term_memory_scope && (
                  <span>
                    🎯 <strong>SHORT_TERM_MEMORY_SCOPE</strong> = {promptDetails.short_term_memory_scope}
                  </span>
                )}
              </div>

              {/* System Prompt Section */}
              {(() => {
                const systemMessages = promptDetails.actual_llm_messages.filter(msg => msg.type === 'SystemMessage');
                if (systemMessages.length === 0) return null;

                const staticParts: string[] = [];
                const dynamicParts: string[] = [];
                systemMessages.forEach((msg) => {
                  const split = splitStaticDynamic(msg.content || "");
                  if (split.staticText) staticParts.push(split.staticText);
                  if (split.dynamicText) dynamicParts.push(split.dynamicText);
                });

                const staticPrompt = staticParts.join("\n\n").trim();

                const primarySystemMessage = systemMessages[0];

                return (
                  <div style={{ 
                    backgroundColor: '#ffffff', 
                    borderRadius: '6px', 
                    border: '1px solid #e2e8f0',
                    marginBottom: '12px',
                    overflow: 'hidden'
                  }}>
                    <div 
                      style={{ 
                        padding: '12px 16px', 
                        borderBottom: systemPromptOpen ? '1px solid #e2e8f0' : 'none',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        userSelect: 'none',
                        backgroundColor: '#fefce8'
                      }}
                      onClick={() => setSystemPromptOpen(!systemPromptOpen)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ color: '#854d0e', fontWeight: '600', fontSize: '14px' }}>
                          {systemPromptOpen ? '▼' : '▶'} ⚙️ System Prompt (static) ({formatCounts(staticPrompt)})
                        </span>
                        {primarySystemMessage.annotation && (
                          <span style={{
                            display: 'inline-block',
                            padding: '4px 10px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: '600',
                            backgroundColor: '#fef3c7',
                            color: '#78350f',
                            fontFamily: 'monospace'
                          }}>
                            🏷️ {primarySystemMessage.annotation}
                          </span>
                        )}
                      </div>
                    </div>
                    {systemPromptOpen && (
                      <div style={{ padding: '16px', backgroundColor: '#fffbeb' }}>
                        {/* Metadata section */}
                        {primarySystemMessage.metadata && (
                          <details style={{ 
                            marginBottom: '16px', 
                            padding: '12px',
                            backgroundColor: '#ffffff',
                            borderRadius: '6px',
                            border: '1px solid #e7e5e4'
                          }}>
                            <summary style={{ 
                              cursor: 'pointer', 
                              fontWeight: '600',
                              color: '#854d0e',
                              fontSize: '13px',
                              marginBottom: '8px'
                            }}>
                              📋 Metadata
                            </summary>
                            <pre style={{ 
                              marginTop: '8px',
                              padding: '12px', 
                              backgroundColor: '#f8fafc', 
                              borderRadius: '4px',
                              overflow: 'auto',
                              fontSize: '11px',
                              color: '#334155',
                              fontFamily: 'monospace',
                              lineHeight: '1.5'
                            }}>
                              {JSON.stringify(primarySystemMessage.metadata, null, 2)}
                            </pre>
                          </details>
                        )}
                        
                        {/* Prompt content */}
                        <div style={{
                          color: '#292524',
                          fontFamily: 'monospace',
                          fontSize: '12px',
                          lineHeight: '1.6',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          maxHeight: '400px',
                          overflowY: 'auto',
                          backgroundColor: '#ffffff',
                          padding: '12px',
                          borderRadius: '4px',
                          border: '1px solid #e7e5e4'
                        }}>
                          {staticPrompt || 'Nincs statikus prompt rész'}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Dynamic Prompt Section */}
              {(() => {
                const systemMessages = promptDetails.actual_llm_messages.filter(msg => msg.type === 'SystemMessage');
                if (systemMessages.length === 0) return null;

                const dynamicParts: string[] = [];
                systemMessages.forEach((msg) => {
                  const split = splitStaticDynamic(msg.content || "");
                  if (split.dynamicText) dynamicParts.push(split.dynamicText);
                });

                const dynamicPrompt = dynamicParts.join("\n\n").trim();

                return (
                  <div style={{ 
                    backgroundColor: '#ffffff', 
                    borderRadius: '6px', 
                    border: '1px solid #e2e8f0',
                    marginBottom: '12px',
                    overflow: 'hidden'
                  }}>
                    <div 
                      style={{ 
                        padding: '12px 16px', 
                        borderBottom: dynamicPromptOpen ? '1px solid #e2e8f0' : 'none',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        userSelect: 'none',
                        backgroundColor: '#eff6ff'
                      }}
                      onClick={() => setDynamicPromptOpen(!dynamicPromptOpen)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ color: '#1e3a8a', fontWeight: '600', fontSize: '14px' }}>
                          {dynamicPromptOpen ? '▼' : '▶'} 🧩 Dynamic Prompt (non-chat) ({formatCounts(dynamicPrompt)})
                        </span>
                      </div>
                    </div>
                    {dynamicPromptOpen && (
                      <div style={{ padding: '16px', backgroundColor: '#f8fafc' }}>
                        <div style={{
                          color: '#0f172a',
                          fontFamily: 'monospace',
                          fontSize: '12px',
                          lineHeight: '1.6',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          maxHeight: '400px',
                          overflowY: 'auto',
                          backgroundColor: '#ffffff',
                          padding: '12px',
                          borderRadius: '4px',
                          border: '1px solid #e2e8f0'
                        }}>
                          {dynamicPrompt || 'Nincs dinamikus prompt rész'}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Chat History Table */}
              {(() => {
                const chatMessages = promptDetails.actual_llm_messages.filter(msg => msg.type !== 'SystemMessage');
                const chatText = chatMessages.map(msg => msg.content).join("\n");
                return (
                  <div style={{ 
                    backgroundColor: '#ffffff', 
                    borderRadius: '6px', 
                    border: '1px solid #e2e8f0',
                    overflow: 'hidden'
                  }}>
                    <div style={{ 
                      padding: '12px 16px', 
                      borderBottom: '1px solid #e2e8f0',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      justifyContent: 'space-between',
                      backgroundColor: '#f8fafc'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ color: '#0f172a', fontWeight: '600', fontSize: '14px' }}>💬 Chat History</span>
                        <span style={{ color: '#64748b', fontSize: '13px' }}>{chatMessages.length} messages</span>
                      </div>
                      <span style={{ color: '#64748b', fontSize: '12px', fontFamily: 'monospace' }}>
                        {formatCounts(chatText)}
                      </span>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse' }}>
                        <thead style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                          <tr>
                            <th style={{ padding: '12px 16px', textAlign: 'left', color: '#475569', fontWeight: '600', width: '60px' }}>#</th>
                            <th style={{ padding: '12px 16px', textAlign: 'left', color: '#475569', fontWeight: '600', width: '90px' }}>Type</th>
                            <th style={{ padding: '12px 16px', textAlign: 'left', color: '#475569', fontWeight: '600', width: '150px' }}>🏷️ Annotation</th>
                            <th style={{ padding: '12px 16px', textAlign: 'left', color: '#475569', fontWeight: '600' }}>Content</th>
                            <th style={{ padding: '12px 16px', textAlign: 'right', color: '#475569', fontWeight: '600', width: '80px' }}>Length</th>
                          </tr>
                        </thead>
                        <tbody style={{ color: '#1e293b' }}>
                          {chatMessages.map((msg, idx) => (
                            <tr 
                              key={idx} 
                              style={{ 
                                backgroundColor: msg.type === 'HumanMessage' ? '#faf5ff' : '#f0fdf4',
                                borderBottom: idx < chatMessages.length - 1 ? '1px solid #e2e8f0' : 'none',
                                transition: 'background-color 0.15s'
                              }}
                              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f1f5f9'}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = msg.type === 'HumanMessage' ? '#faf5ff' : '#f0fdf4';
                              }}
                            >
                              <td style={{ padding: '12px 16px', color: '#64748b', fontFamily: 'monospace' }}>#{idx + 1}</td>
                              <td style={{ padding: '12px 16px' }}>
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '6px',
                                  padding: '4px 10px',
                                  borderRadius: '9999px',
                                  fontSize: '12px',
                                  fontWeight: '600',
                                  backgroundColor: msg.type === 'HumanMessage' ? '#e9d5ff' : '#bbf7d0',
                                  color: msg.type === 'HumanMessage' ? '#6b21a8' : '#166534'
                                }}>
                                  {msg.type === 'HumanMessage' ? '👤 User' : '🤖 Assistant'}
                                </span>
                              </td>
                              <td style={{ padding: '12px 16px' }}>
                                {msg.annotation ? (
                                  <div>
                                    <span style={{
                                      display: 'inline-block',
                                      padding: '4px 8px',
                                      borderRadius: '4px',
                                      fontSize: '11px',
                                      fontWeight: '600',
                                      backgroundColor: '#fef3c7',
                                      color: '#78350f',
                                      fontFamily: 'monospace',
                                      marginBottom: '4px'
                                    }}>
                                      {msg.annotation}
                                    </span>
                                    {msg.metadata && (
                                      <details style={{ marginTop: '6px', fontSize: '11px', color: '#64748b' }}>
                                        <summary style={{ cursor: 'pointer', fontWeight: '600' }}>metadata</summary>
                                        <pre style={{ 
                                          marginTop: '6px', 
                                          padding: '8px', 
                                          backgroundColor: '#f8fafc', 
                                          borderRadius: '4px',
                                          overflow: 'auto',
                                          maxWidth: '300px'
                                        }}>
                                          {JSON.stringify(msg.metadata, null, 2)}
                                        </pre>
                                      </details>
                                    )}
                                  </div>
                                ) : (
                                  <span style={{ color: '#94a3b8', fontSize: '11px', fontStyle: 'italic' }}>—</span>
                                )}
                              </td>
                              <td style={{ padding: '12px 16px' }}>
                                <div>
                                  <div style={{
                                    color: '#1e293b',
                                    fontFamily: 'monospace',
                                    fontSize: '12px',
                                    lineHeight: '1.6',
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word',
                                    maxHeight: '120px',
                                    overflowY: 'auto'
                                  }}>
                                    {msg.content}
                                  </div>
                                </div>
                              </td>
                              <td style={{ padding: '12px 16px', textAlign: 'right', color: '#64748b', fontFamily: 'monospace', fontSize: '12px' }}>
                                {msg.content.length}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })()}
            </>
          )}
        </div>
      )}
    </section>
  );
};
