/**
 * Main App component.
 */
import { useState } from 'react';
import { ChatWindow } from './components/ChatWindow';
import { ChatInput } from './components/ChatInput';
import { DebugPanel } from './components/DebugPanel';
import { api } from './api';
import { getUserId, getSessionId, resetSessionId } from './utils';
import { ChatMessage, ToolUsed, MemorySnapshot } from './types';
import './App.css';

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [lastToolsUsed, setLastToolsUsed] = useState<ToolUsed[]>([]);
  const [memorySnapshot, setMemorySnapshot] = useState<MemorySnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  const userId = getUserId();
  const sessionId = getSessionId();

  const handleResetContext = async () => {
    if (!confirm('Are you sure you want to reset the conversation history? This will clear all messages.')) {
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await api.sendMessage({
        user_id: userId,
        message: 'reset context',
        session_id: sessionId,
      });
      
      // Clear local messages
      setMessages([]);
      setLastToolsUsed([]);
      resetSessionId();
      
      // Add confirmation message
      const confirmMessage: ChatMessage = {
        id: `msg_${Date.now()}_system`,
        role: 'assistant',
        content: response.final_answer,
        timestamp: new Date(),
      };
      setMessages([confirmMessage]);
    } catch (err: any) {
      console.error('Error resetting context:', err);
      setError(err.message || 'Failed to reset context');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (messageText: string, files?: File[]) => {
    setError(null);
    
    // Check if this is a reset context command
    const isReset = messageText.toLowerCase() === 'reset context';
    
    // Add user message to UI (include file names if any)
    const fileInfo = files && files.length > 0 
      ? ` [📎 ${files.map(f => f.name).join(', ')}]` 
      : '';
    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}_user`,
      role: 'user',
      content: messageText + fileInfo,
      timestamp: new Date(),
    };
    
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Use file upload endpoint if files are attached
      const response = files && files.length > 0
        ? await api.sendMessageWithFiles(userId, messageText, sessionId, files)
        : await api.sendMessage({
            user_id: userId,
            message: messageText,
            session_id: sessionId,
          });

      // If reset context, clear local messages
      if (isReset) {
        setMessages([]);
        resetSessionId();
      }

      // Add assistant message to UI
      console.log('Tools used from response:', response.tools_used);
      const assistantMessage: ChatMessage = {
        id: `msg_${Date.now()}_assistant`,
        role: 'assistant',
        content: response.final_answer,
        timestamp: new Date(),
        toolsUsed: response.tools_used,
      };
      console.log('Assistant message with tools:', assistantMessage);

      setMessages((prev) => (isReset ? [assistantMessage] : [...prev, assistantMessage]));
      setLastToolsUsed(response.tools_used);
      setMemorySnapshot(response.memory_snapshot);
    } catch (err: any) {
      console.error('Error sending message:', err);
      setError(err.response?.data?.detail || err.message || 'An error occurred');
      
      // Add error message
      const errorMessage: ChatMessage = {
        id: `msg_${Date.now()}_error`,
        role: 'assistant',
        content: `Sorry, an error occurred: ${err.response?.data?.detail || err.message}`,
        timestamp: new Date(),
      };
      
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>SupportAI <span style={{color: '#717379'}}>(AI Support Triage & Answer Drafting Agent)</span></h1>
        <div className="header-info">
          <span className="user-id">User: {userId.substring(0, 20)}...</span>
          <button 
            className="view-tickets-button"
            onClick={() => window.open('/tickets', '_blank')}
            title="View all tickets"
          >
            📋 View Tickets
          </button>
          <button 
            className="reset-button"
            onClick={handleResetContext}
            disabled={isLoading}
            title="Reset conversation history"
          >
            🔄 Reset Context
          </button>
          <button 
            className="debug-toggle-header"
            onClick={() => setDebugOpen(!debugOpen)}
            title="Toggle debug panel"
          >
            {debugOpen ? '✕ Close Debug' : '🔧 Debug'}
          </button>
        </div>
      </header>

      <main className="app-main">
        <div className="chat-container">
          <ChatWindow messages={messages} isLoading={isLoading} />
          <ChatInput onSend={handleSendMessage} disabled={isLoading} />
          
          {error && (
            <div className="error-banner">
              <strong>Error:</strong> {error}
              <button onClick={() => setError(null)}>✕</button>
            </div>
          )}
        </div>

        <DebugPanel
          toolsUsed={lastToolsUsed}
          memorySnapshot={memorySnapshot}
          isOpen={debugOpen}
        />
      </main>
    </div>
  );
}

export default App;
