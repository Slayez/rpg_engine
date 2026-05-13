// frontend/src/hooks/useGameState.js
import { useState, useCallback, useEffect, useRef } from 'react';
import { getWorld, sendActionStream, undoAction, retryAction, editAction } from '../api';

export function useGameState(slotId) {
  const [messages, setMessages] = useState([]);
  const [worldState, setWorldState] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  const initialHistoryLen = useRef(0);

  const addMessage = useCallback((sender, text) => {
    setMessages(prev => [...prev, { sender, text }]);
  }, []);

  useEffect(() => {
    setLoading(true);
    getWorld(slotId).then(data => {
      setWorldState(data.world_state);
      let msgs = (data.chat_history || []).map(m => ({
        sender: m.sender,
        text: m.text
      }));
      if (msgs.length === 0 && data.narration) {
        msgs.push({ sender: 'assistant', text: data.narration });
      }
      setMessages(msgs);
      initialHistoryLen.current = msgs.length;
    }).catch(err => setError(err.message))
    .finally(() => setLoading(false));
  }, [slotId]);

  const handleUndo = async () => {
    try {
      const res = await undoAction(slotId);
      applyFullResponse(res);
    } catch(e) { setError(e.message); }
  };

  const handleRetry = async () => {
    try {
      const res = await retryAction(slotId);
      applyFullResponse(res);
    } catch(e) { setError(e.message); }
  };

  const handleEdit = async (newAction) => {
    try {
      const res = await editAction(slotId, newAction);
      applyFullResponse(res);
    } catch(e) { setError(e.message); }
  };

  const applyFullResponse = (res) => {
    setWorldState(res.world_state);
    const msgs = (res.chat_history || []).map(m => ({ sender: m.sender, text: m.text }));
    setMessages(msgs);
  };

  const streamAction = useCallback((action) => {
    addMessage('user', action);
    setStreaming(true);
    setStreamedText('');

    const onChunk = (text) => {
      setStreamedText(prev => prev + text);
    };

    const onSystemMessage = (text, msgType) => {
      addMessage('system', text);
    };

    const onDone = (data) => {
      addMessage('assistant', data.narration);
      // Остальные системные сообщения, если ещё не добавлены (обычно они приходят до done)
      for (const sm of data.system_messages || []) {
        if (!messages.some(m => m.sender === 'system' && m.text === sm.text)) {
          addMessage('system', sm.text);
        }
      }
      setWorldState(data.world_state);
      setStreaming(false);
      setStreamedText('');
    };

    const onError = (msg) => {
      addMessage('system', `❌ ${msg}`);
      setError(msg);
      setStreaming(false);
      setStreamedText('');
    };

    const controller = sendActionStream(slotId, action, onChunk, onDone, onError, onSystemMessage);
    return controller;
  }, [slotId, addMessage, messages]);

  return {
    messages, worldState, loading, error, streaming, streamedText, initialHistoryLen: initialHistoryLen.current,
    streamAction, handleUndo, handleRetry, handleEdit
  };
}