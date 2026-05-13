import React, { useEffect, useRef } from 'react';
import { Virtuoso } from 'react-virtuoso';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import rehypeRaw from 'rehype-raw';
import { highlightMechanics } from '../utils/formatting';

function MessageRow({ index, messages, hoverId, setHoverId, onEditMessage, onDeleteMessage, onRetryMessage, isStreaming, editStartIndex }) {
  const msg = messages[index];
  const canEdit = index >= editStartIndex && msg.sender !== 'system';

  if (msg.sender === 'system') {
    return (<div className={`system-message`} style={{ padding: '8px 12px', borderBottom: '1px solid #eee' }}>{msg.text}</div>);
  }

  const highlightedText = highlightMechanics(msg.text);
  return (
    <div className={`message ${msg.sender === 'user' ? 'user' : 'assistant'}`}
      style={{ padding: '8px 12px', borderBottom: '1px solid #eee' }}
      onMouseEnter={() => setHoverId(index)} onMouseLeave={() => setHoverId(null)}>
      <div className="message-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
        <strong>{msg.sender === 'user' ? 'Вы' : 'Мастер'}</strong>
        {hoverId === index && !isStreaming && canEdit && (
          <div className="message-actions">
            {msg.sender === 'user' ? (
              <><button onClick={() => onEditMessage(index)} style={{ marginRight: '4px' }}>✎</button><button onClick={() => onDeleteMessage(index)}>✕</button></>
            ) : (
              <>{index === messages.length - 1 && <button onClick={onRetryMessage} style={{ marginRight: '4px' }}>↻</button>}<button onClick={() => onDeleteMessage(index)}>✕</button></>
            )}
          </div>
        )}
      </div>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} rehypePlugins={[rehypeRaw]}>{highlightedText}</ReactMarkdown>
    </div>
  );
}

function VirtualizedChatWindow({ messages, onDeleteMessage, onEditMessage, onRetryMessage, isStreaming, editStartIndex = 0 }) {
  const [hoverId, setHoverId] = React.useState(null);
  const listRef = useRef(null);
  
  useEffect(() => {
    if (listRef.current && messages.length > 0) {
      listRef.current.scrollToIndex({ index: messages.length - 1, align: 'end', behavior: 'smooth' });
    }
  }, [messages]);
  
  return (
    <Virtuoso
      ref={listRef}
      style={{ height: '500px', width: '100%' }}
      totalCount={messages.length}
      renderItem={(index) => (
        <MessageRow 
          index={index} 
          messages={messages}
          hoverId={hoverId}
          setHoverId={setHoverId}
          onEditMessage={onEditMessage}
          onDeleteMessage={onDeleteMessage}
          onRetryMessage={onRetryMessage}
          isStreaming={isStreaming}
          editStartIndex={editStartIndex}
        />
      )}
    />
  );
}

export default VirtualizedChatWindow;
