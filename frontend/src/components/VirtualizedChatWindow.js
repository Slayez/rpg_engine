import React, { useEffect, useRef } from 'react';
import { FixedSizeList as List } from 'react-window';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import rehypeRaw from 'rehype-raw';
import { highlightMechanics } from '../utils/formatting';

function MessageRow({ index, style, data }) {
  const { messages, hoverId, setHoverId, onEditMessage, onDeleteMessage, onRetryMessage, isStreaming, editStartIndex } = data;
  const msg = messages[index];
  const canEdit = index >= editStartIndex && msg.sender !== 'system';

  if (msg.sender === 'system') {
    return (<div style={style} className={`system-message`}>{msg.text}</div>);
  }

  const highlightedText = highlightMechanics(msg.text);
  return (
    <div style={style} className={`message ${msg.sender === 'user' ? 'user' : 'assistant'}`}
      onMouseEnter={() => setHoverId(index)} onMouseLeave={() => setHoverId(null)}>
      <div className="message-header">
        <strong>{msg.sender === 'user' ? 'Вы' : 'Мастер'}</strong>
        {hoverId === index && !isStreaming && canEdit && (
          <div className="message-actions">
            {msg.sender === 'user' ? (
              <><button onClick={() => onEditMessage(index)}>✎</button><button onClick={() => onDeleteMessage(index)}>✕</button></>
            ) : (
              <>{index === messages.length - 1 && <button onClick={onRetryMessage}>↻</button>}<button onClick={() => onDeleteMessage(index)}>✕</button></>
            )}
          </div>
        )}
      </div>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} rehypePlugins={[rehypeRaw]}>{highlightedText}</ReactMarkdown>
    </div>
  );
}

function VirtualizedChatWindow({ messages, onDeleteMessage, onEditMessage, onRetryMessage, isStreaming, editStartIndex = 0 }) {
  const outerRef = useRef(null);
  const [hoverId, setHoverId] = React.useState(null);
  useEffect(() => { if (outerRef.current) outerRef.current.scrollTop = outerRef.current.scrollHeight; }, [messages]);
  const itemData = { messages, hoverId, setHoverId, onEditMessage, onDeleteMessage, onRetryMessage, isStreaming, editStartIndex };
  return (
    <List height={500} itemCount={messages.length} itemSize={120} itemData={itemData} outerRef={outerRef} width="100%">
      {MessageRow}
    </List>
  );
}

export default VirtualizedChatWindow;
