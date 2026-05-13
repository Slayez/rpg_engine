import React, { useState, useEffect } from 'react';
import ChatWindow from './ChatWindow';
import VirtualizedChatWindow from './VirtualizedChatWindow';
import InputBox from './InputBox';
import CharacterPanel from './CharacterPanel';
import QuestPanel from './QuestPanel';
import InteractiveScene from './InteractiveScene';
import { useGameState } from '../hooks/useGameState';
import { useSystemMessages } from '../hooks/useSystemMessages';
import { fetchMemory, getScene, movePlayer, interactWithObject } from '../api';
import './GameScreen.css';
import LocationInfo from './LocationInfo';

function GameScreen({ slotId, onBack }) {
  const {
    messages, worldState, loading, error, streaming, streamedText,
    initialHistoryLen, streamAction, handleUndo, handleRetry, handleEdit
  } = useGameState(slotId);

  const { chatBorderAnim, applyBorderAnimation } = useSystemMessages();
  const [activeTab, setActiveTab] = useState('chat');
  const [memoryEntries, setMemoryEntries] = useState([]);
  const [editModal, setEditModal] = useState({ show: false, index: null, originalText: '' });
  const [useVirtualization, setUseVirtualization] = useState(false);
  
  // Visual mode state
  const [visualMode, setVisualMode] = useState(false);
  const [sceneData, setSceneData] = useState(null);

  // Включаем виртуализацию при 100+ сообщениях
  useEffect(() => {
    if (messages.length >= 100 && !useVirtualization) {
      setUseVirtualization(true);
    } else if (messages.length < 50 && useVirtualization) {
      setUseVirtualization(false);
    }
  }, [messages.length]);

  // Загрузка сцены при переключении в визуальный режим
  useEffect(() => {
    if (visualMode && slotId) {
      loadScene();
    }
  }, [visualMode, slotId, worldState?.location]);

  const loadScene = async () => {
    try {
      const data = await getScene(slotId);
      if (data.scene) {
        setSceneData(data.scene);
      }
    } catch (e) {
      console.error('Failed to load scene:', e);
    }
  };

  // Обработка клика по объекту сцены
  const handleSceneObjectClick = async (actionData) => {
    try {
      const result = await interactWithObject(slotId, actionData.target_id, actionData.interaction);
      if (result.success) {
        // Отправка действия в игровой движок
        const actionText = `${actionData.interaction} ${actionData.target_id}`;
        const sysMsgs = await streamAction(actionText);
        if (sysMsgs) applyBorderAnimation(sysMsgs);
        
        // Перезагрузка сцены после действия
        setTimeout(loadScene, 500);
      }
    } catch (e) {
      console.error('Scene interaction error:', e);
    }
  };

  // Обработка правого клика (контекстное меню)
  const handleSceneRightClick = (menuData) => {
    console.log('Context menu:', menuData);
  };

  // Обработка перемещения игрока
  const handleSceneMove = async (moveData) => {
    try {
      await movePlayer(slotId, moveData.target_x, moveData.target_y);
      // Обновление позиции в сцене
      setTimeout(loadScene, 300);
    } catch (e) {
      console.error('Move error:', e);
    }
  };

  // Состояние поля ввода (живёт здесь, не теряется при смене вкладки)
  const [inputText, setInputText] = useState('');
  const [inputHistory, setInputHistory] = useState([]);
  const [inputHistoryIndex, setInputHistoryIndex] = useState(-1);

  const loadMemory = async () => {
    try {
      const data = await fetchMemory(slotId, 20);
      setMemoryEntries(data.memories || []);
    } catch (e) { console.error(e); }
  };
  useEffect(() => { loadMemory(); }, [slotId]);

  const handleSend = async (action) => {
    if (streaming) return;
    setInputText('');
    setInputHistory(prev => [action, ...prev].slice(0, 50));
    setInputHistoryIndex(-1);

    const sysMsgs = await streamAction(action);
    if (sysMsgs) applyBorderAnimation(sysMsgs);
    loadMemory();
    
    // Если в визуальном режиме - обновить сцену
    if (visualMode) {
      setTimeout(loadScene, 500);
    }
  };

  const openEditModal = (index) => setEditModal({ show: true, index, originalText: messages[index].text });
  const submitEdit = async () => {
    const newText = editModal.newText || editModal.originalText;
    if (newText !== editModal.originalText) await handleEdit(newText);
    setEditModal({ show: false });
  };

  const displayMessages = [...messages];
  if (streaming && streamedText) displayMessages.push({ sender: 'assistant', text: streamedText + '▌' });

  const ChatComponent = useVirtualization ? VirtualizedChatWindow : ChatWindow;

  return (
    <div className="app-container">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <button className="btn-outline" onClick={onBack}>← В меню</button>
        <ul className="nav nav-tabs">
          <li className="nav-item"><button className={`nav-link ${activeTab==='chat'?'active':''}`} onClick={()=>setActiveTab('chat')}>💬 Чат</button></li>
          <li className="nav-item"><button className={`nav-link ${activeTab==='character'?'active':''}`} onClick={()=>setActiveTab('character')}>👤 Персонаж</button></li>
          <li className="nav-item"><button className={`nav-link ${activeTab==='quests'?'active':''}`} onClick={()=>setActiveTab('quests')}>📜 Задания</button></li>
          <li className="nav-item"><button className={`nav-link ${activeTab==='memory'?'active':''}`} onClick={()=>{setActiveTab('memory');loadMemory();}}>🧠 Память</button></li>
        </ul>
        <button 
          className={`btn-outline ${visualMode ? 'active' : ''}`}
          onClick={() => setVisualMode(!visualMode)}
          title="Переключить визуальный режим"
        >
          {visualMode ? '🎨 Визуальный' : '📝 Текст'}
        </button>
      </div>

      {activeTab === 'chat' && (
        <div className={`chat-panel-wrapper ${chatBorderAnim}`}>
          {visualMode && sceneData ? (
            // Визуальный режим с интерактивной сценой
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <InteractiveScene
                scene={sceneData}
                onObjectClick={handleSceneObjectClick}
                onObjectRightClick={handleSceneRightClick}
                onMove={handleSceneMove}
                showGrid={false}
              />
              <div className="card-panel" style={{ flex: 1, height: '40vh', display: 'flex', flexDirection: 'column' }}>
                <div className="chat-container" style={{ flex: 1 }}>
                  <ChatComponent
                    messages={displayMessages.slice(-20)}
                    onDeleteMessage={() => handleUndo()}
                    onEditMessage={openEditModal}
                    onRetryMessage={handleRetry}
                    isStreaming={streaming}
                    editStartIndex={initialHistoryLen}
                  />
                </div>
                <InputBox
                  text={inputText}
                  onTextChange={setInputText}
                  history={inputHistory}
                  historyIndex={inputHistoryIndex}
                  onHistoryIndexChange={setInputHistoryIndex}
                  onSend={handleSend}
                  disabled={streaming}
                />
              </div>
            </div>
          ) : (
            // Текстовый режим
            <div style={{ display: 'flex', alignItems: 'flex-start' }}>
              <LocationInfo worldState={worldState} />
              <div className="card-panel" style={{ flex: 1, height: '70vh', display: 'flex', flexDirection: 'column' }}>
                <div className="chat-container">
                  <ChatComponent
                    messages={displayMessages}
                    onDeleteMessage={() => handleUndo()}
                    onEditMessage={openEditModal}
                    onRetryMessage={handleRetry}
                    isStreaming={streaming}
                    editStartIndex={initialHistoryLen}
                  />
                </div>
                <InputBox
                  text={inputText}
                  onTextChange={setInputText}
                  history={inputHistory}
                  historyIndex={inputHistoryIndex}
                  onHistoryIndexChange={setInputHistoryIndex}
                  onSend={handleSend}
                  disabled={streaming}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'character' && <CharacterPanel worldState={worldState} prevWorldState={{}} />}
      {activeTab === 'quests' && <QuestPanel worldState={worldState} />}
      {activeTab === 'memory' && (
        <div className="card-panel memory-panel">
          <h5>Память</h5>
          {memoryEntries.map((e,i) => (
            <div key={i} className="alert alert-secondary">
              <small>{new Date(e.metadata?.timestamp*1000).toLocaleString()}</small>
              <p className="mb-0">{e.text}</p>
            </div>
          ))}
        </div>
      )}

      {editModal.show && (
        <div className="modal-overlay" onClick={()=>setEditModal({show:false})}>
          <div className="modal-content" onClick={e=>e.stopPropagation()}>
            <h5>Редактирование</h5>
            <textarea className="modal-input" rows={4} value={editModal.newText||editModal.originalText}
              onChange={e=>setEditModal({...editModal, newText:e.target.value})} />
            <div className="d-flex justify-content-end gap-2 mt-2">
              <button className="btn-outline" onClick={()=>setEditModal({show:false})}>Отмена</button>
              <button className="btn-primary" onClick={submitEdit}>Сохранить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default GameScreen;