/**
 * Typing indicator component ("AI is typing...").
 */
import './chat.css';

export function TypingIndicator() {
  return (
    <div className="message-bubble-wrapper assistant">
      <div className="message-bubble assistant typing-indicator">
        <div className="typing-dots">
          <span className="dot"></span>
          <span className="dot"></span>
          <span className="dot"></span>
        </div>
        <span className="typing-text">AI is thinking...</span>
      </div>
    </div>
  );
}
