import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import rehypeRaw from 'rehype-raw';
import { highlightMechanics } from '../utils/formatting';

// Иконки для типов системных сообщений
const SYSTEM_MESSAGE_ICONS = {
  'enemy-damage': '⚔️',
  'mp-spent': '💙',
  'enemy-reaction': '🐺',
  'enemy-defeated': '💀',
  'skill-use': '✨',
  'hp-heal': '❤️',
  'hp-damage': '💔',
  'mp-heal': '💎',
  'exp-gain': '✨',
  'level-up': '⭐',
  'item-appear': '🆕',
  'item-removed': '❌',
  'enemy-action': '🐺',
  'enemy-attack': '🐺'
};

function ChatWindow({ messages, onDeleteMessage, onEditMessage, onRetryMessage, isStreaming, editStartIndex = 0 }) {
  const bottomRef = useRef(null);
  const [hoverId, setHoverId] = useState(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div>
      {messages.map((msg, idx) => {
        const canEdit = idx >= editStartIndex && msg.sender !== 'system';
        if (msg.sender === 'system') {
          const icon = SYSTEM_MESSAGE_ICONS[msg.type] || 'ℹ️';
          const animClass = msg.type || 'fadeInUp';
          return (
            <div key={idx} className={`system-message ${animClass}`}>
              <span className="system-message-icon">{icon}</span>
              <span className="system-message-text">{msg.text}</span>
            </div>
          );
        }

        // Применяем подсветку к тексту сообщения (возвращает HTML-строку)
        const highlightedText = highlightMechanics(msg.text);

        return (
          <div
            key={idx}
            className={`message ${msg.sender === 'user' ? 'user' : 'assistant'}`}
            onMouseEnter={() => setHoverId(idx)}
            onMouseLeave={() => setHoverId(null)}
          >
            <div className="message-header">
              <strong>{msg.sender === 'user' ? 'Вы' : 'Мастер'}</strong>
              {hoverId === idx && !isStreaming && canEdit && (
                <div className="message-actions">
                  {msg.sender === 'user' ? (
                    <>
                      <button onClick={() => onEditMessage(idx)}>✎</button>
                      <button onClick={() => onDeleteMessage(idx)}>✕</button>
                    </>
                  ) : (
                    <>
                      {idx === messages.length - 1 && (
                        <button onClick={onRetryMessage}>↻</button>
                      )}
                      <button onClick={() => onDeleteMessage(idx)}>✕</button>
                    </>
                  )}
                </div>
              )}
            </div>
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              rehypePlugins={[rehypeRaw]}
            >
              {highlightedText}
            </ReactMarkdown>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}

export default ChatWindow;