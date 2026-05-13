import React, { useEffect, useRef } from 'react';

function InputBox({ text, onTextChange, history, historyIndex, onHistoryIndexChange, onSend, disabled }) {
  const inputRef = useRef(null);

  useEffect(() => {
    if (!disabled) inputRef.current?.focus();
  }, [disabled]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!text.trim() || disabled) return;
    onSend(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (history.length === 0) return;
      const newIndex = historyIndex + 1;
      if (newIndex < history.length) {
        onHistoryIndexChange(newIndex);
        onTextChange(history[newIndex]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        onHistoryIndexChange(newIndex);
        onTextChange(history[newIndex]);
      } else {
        onHistoryIndexChange(-1);
        onTextChange('');
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} className="d-flex mt-2">
      <input
        ref={inputRef}
        type="text"
        className="modal-input flex-grow-1"
        placeholder={disabled ? "Идёт генерация..." : "Введите действие..."}
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <button type="submit" className="btn-primary ms-2" disabled={disabled || !text.trim()}>
        {disabled ? '⏳' : '➤'}
      </button>
    </form>
  );
}

export default InputBox;