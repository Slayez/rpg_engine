import { create } from 'zustand';
import { getWorld, sendActionStream, undoAction, retryAction, editAction } from '../api';

export const useGameStore = create((set, get) => ({
  slotId: null, messages: [], worldState: {}, loading: false, error: null, streaming: false, streamedText: '', initialHistoryLen: 0,
  setSlotId: (slotId) => set({ slotId }),
  loadWorld: async (slotId) => {
    set({ loading: true, error: null });
    try {
      const data = await getWorld(slotId);
      const msgs = (data.chat_history || []).map(m => ({ sender: m.sender, text: m.text }));
      set({ worldState: data.world_state, messages: msgs.length ? msgs : [{ sender: 'assistant', text: data.narration }], initialHistoryLen: msgs.length, loading: false });
    } catch (e) { set({ error: e.message, loading: false }); }
  },
  streamAction: (action, onChunk, onSystemMessage, onDone, onError) => {
    const { slotId } = get();
    set(prev => ({ messages: [...prev.messages, { sender: 'user', text: action }], streaming: true, streamedText: '' }));
    return sendActionStream(slotId, action,
      (text) => { set(prev => ({ streamedText: prev.streamedText + text })); if (onChunk) onChunk(text); },
      (data) => { set(prev => ({ messages: [...prev.messages, { sender: 'assistant', text: data.narration }], worldState: data.world_state, streaming: false, streamedText: '' })); if (onDone) onDone(data); },
      (msg) => { set(prev => ({ messages: [...prev.messages, { sender: 'system', text: `❌ ${msg}` }], error: msg, streaming: false, streamedText: '' })); if (onError) onError(msg); },
      (text, type) => { set(prev => ({ messages: [...prev.messages, { sender: 'system', text, type }] })); if (onSystemMessage) onSystemMessage(text, type); }
    );
  },
  handleUndo: async () => { const { slotId } = get(); try { const res = await undoAction(slotId); set({ worldState: res.world_state, messages: (res.chat_history || []).map(m => ({ sender: m.sender, text: m.text })) }); } catch (e) { set({ error: e.message }); } },
  handleRetry: async () => { const { slotId } = get(); try { const res = await retryAction(slotId); set({ worldState: res.world_state, messages: (res.chat_history || []).map(m => ({ sender: m.sender, text: m.text })) }); } catch (e) { set({ error: e.message }); } },
  handleEdit: async (newAction) => { const { slotId } = get(); try { const res = await editAction(slotId, newAction); set({ worldState: res.world_state, messages: (res.chat_history || []).map(m => ({ sender: m.sender, text: m.text })) }); } catch (e) { set({ error: e.message }); } },
  addSystemMessage: (text, type = '') => set(prev => ({ messages: [...prev.messages, { sender: 'system', text, type }] }))
}));
