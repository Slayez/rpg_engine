import React, { useState, useEffect, useCallback } from 'react';
import MainMenu from './components/MainMenu';
import CharacterCreation from './components/CharacterCreation';
import GameScreen from './components/GameScreen';
import './styles/skillAnimations.css';
// Глобальные стили уже импортированы в index.js

function App() {
  const [screen, setScreen] = useState('menu');
  const [slotId, setSlotId] = useState(null);
  const [theme, setTheme] = useState('dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-bs-theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');

  const handleLoadWorld = useCallback((id) => {
    setSlotId(id);
    setScreen('game');
  }, []);

  const handleWorldCreated = useCallback((id) => {
    setSlotId(id);
    setScreen('game');
  }, []);

  const handleBackToMenu = useCallback(() => {
    setScreen('menu');
    setSlotId(null);
  }, []);

  return (
    <div className="App">
      <div className="theme-toggle-container">
        <button className="btn-outline" onClick={toggleTheme}>
          {theme === 'dark' ? '☀️ Светлая тема' : '🌙 Тёмная тема'}
        </button>
      </div>
      {screen === 'menu' && (
        <MainMenu onNewGame={() => setScreen('create')} onLoadWorld={handleLoadWorld} />
      )}
      {screen === 'create' && (
        <CharacterCreation onCreated={handleWorldCreated} onCancel={() => setScreen('menu')} />
      )}
      {screen === 'game' && slotId && (
        <GameScreen slotId={slotId} onBack={handleBackToMenu} />
      )}
    </div>
  );
}

export default App;