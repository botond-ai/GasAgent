import { useEffect, useRef } from "react";
import { Message } from "../../types";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";

interface ChatWindowProps {
  messages: Message[];
  isLoading?: boolean;
  onWorkflowClick?: (executionId: string) => void; // NEW: Workflow visualization callback
}

export const ChatWindow = ({ messages, isLoading = false, onWorkflowClick }: ChatWindowProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  return (
    <div className="chat-window">
      {messages.length === 0 ? (
        <div className="empty-state">
          <p>No messages yet. Start a conversation!</p>
        </div>
      ) : (
        <>
          {messages.map((message, index) => (
            <MessageBubble 
              key={index} 
              message={message} 
              onWorkflowClick={onWorkflowClick}
            />
          ))}
          {isLoading && <TypingIndicator />}
        </>
      )}
      <div ref={messagesEndRef} />
    </div>
  );
};
