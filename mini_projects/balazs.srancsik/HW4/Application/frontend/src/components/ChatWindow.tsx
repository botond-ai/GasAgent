/**
 * ChatWindow component - Displays the conversation history.
 */
import React, { useEffect, useRef } from 'react';
import { ChatMessage } from '../types';
import { MessageBubble } from './MessageBubble';

interface ChatWindowProps {
  messages: ChatMessage[];
  isLoading: boolean;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isLoading }) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  return (
    <div className="chat-window">
      {messages.length === 0 ? (
        <div className="welcome-message">
          <h2>Welcome to SupportAI</h2>
          <p>Please share your issue with us and we will help you resolve it.</p>
          <div className="example-prompts">
            <div className="prompt-label">I will:</div>
            <div className="prompt-item">❓ Understand your issue</div>
            <div className="prompt-item">😊 Run a sentiment analysis on your message</div>
            <div className="prompt-item">🌐 I will respond to your question in your own language</div>
            <div className="prompt-item">📖 Provide you with information based on the available knowledge base</div>
            <div className="prompt-item">🏷️ Classify the urgency of your request</div>
            <div className="prompt-item">⏰ Commit deadline till when your issue will get solved</div>
            <div className="prompt-item">💰 Calculate the cost involved and convert to other currencies</div>
            <div className="prompt-item">🏗️ Structure the conversation data</div>
            <div className="prompt-item">💾 Store the chat history and shared documents</div>
            <div className="prompt-item">📧 Forward your issue to the right team</div>
            <div className="prompt-item">📊 Create dashboard to report the saved tickets</div>
          </div>
        </div>
      ) : (
        <>
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {isLoading && (
            <div className="message-container assistant">
              <div className="message-bubble assistant-bubble loading">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </>
      )}
    </div>
  );
};
