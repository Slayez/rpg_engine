// frontend/src/components/InteractiveScene.js

import React, { useState, useRef, useEffect } from 'react';
import './InteractiveScene.css';

/**
 * InteractiveScene - Визуальное отображение локации с интерактивными объектами
 * 
 * Props:
 * - scene: объект сцены { type, width, height, objects[], player }
 * - onObjectClick: callback при клике на объект
 * - onObjectRightClick: callback при правом клике
 * - onMove: callback при перемещении игрока
 * - showGrid: показать сетку
 */
function InteractiveScene({ 
  scene, 
  onObjectClick, 
  onObjectRightClick, 
  onMove,
  showGrid = false 
}) {
  const [hoveredObject, setHoveredObject] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [isMoving, setIsMoving] = useState(false);
  const containerRef = useRef(null);

  // Обработка клика по объекту
  const handleObjectClick = (obj, e) => {
    e.stopPropagation();
    if (onObjectClick) {
      onObjectClick({
        action_type: 'interact',
        target_id: obj.id,
        interaction: obj.interactions?.[0] || 'inspect'
      });
    }
  };

  // Обработка правого клика (контекстное меню)
  const handleObjectRightClick = (obj, e) => {
    e.preventDefault();
    e.stopPropagation();
    if (onObjectRightClick) {
      const menu = {
        x: e.clientX,
        y: e.clientY,
        objectId: obj.id,
        actions: obj.interactions || ['inspect']
      };
      setContextMenu(menu);
      onObjectRightClick(menu);
    }
  };

  // Клик по фону сцены - перемещение
  const handleBackgroundClick = (e) => {
    if (!containerRef.current || !onMove) return;
    
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Нормализация координат относительно размера сцены
    const normalizedX = Math.round((x / rect.width) * scene.width);
    const normalizedY = Math.round((y / rect.height) * scene.height);
    
    setIsMoving(true);
    onMove({
      action_type: 'move',
      target_x: normalizedX,
      target_y: normalizedY
    });
    
    setTimeout(() => setIsMoving(false), 500);
  };

  // Закрытие контекстного меню
  useEffect(() => {
    const handleClick = () => setContextMenu(null);
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, []);

  // Определение стиля фона в зависимости от типа локации
  const getBackgroundStyle = () => {
    if (!scene) return {};
    
    switch (scene.type) {
      case 'room':
        return { 
          background: 'linear-gradient(180deg, #2a2e3b 0%, #1a1d26 100%)',
          border: '3px solid #4a4e5b'
        };
      case 'outdoor':
        return { 
          background: 'linear-gradient(180deg, #1a472a 0%, #2d5a3d 100%)',
          border: 'none'
        };
      case 'dungeon':
        return { 
          background: 'linear-gradient(180deg, #1a1a1a 0%, #2a2a2a 100%)',
          border: '3px solid #3a3a3a'
        };
      default:
        return { background: 'var(--bg-secondary)' };
    }
  };

  if (!scene) {
    return (
      <div className="scene-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span className="text-muted">Сцена не загружена</span>
      </div>
    );
  }

  return (
    <div className="scene-container" ref={containerRef}>
      {/* Фон сцены */}
      <div 
        className="scene-background" 
        style={getBackgroundStyle()}
        onClick={handleBackgroundClick}
      >
        {/* Сетка (опционально) */}
        {showGrid && <div className="scene-grid" />}
        
        {/* Объекты сцены */}
        {scene.objects?.map(obj => (
          <SceneObject
            key={obj.id}
            object={obj}
            onClick={handleObjectClick}
            onRightClick={handleObjectRightClick}
            onHover={setHoveredObject}
          />
        ))}
        
        {/* Игрок */}
        {scene.player && (
          <PlayerAvatar
            position={scene.player}
            isMoving={isMoving}
            sceneWidth={scene.width}
            sceneHeight={scene.height}
          />
        )}
      </div>
      
      {/* Tooltip при наведении */}
      {hoveredObject && (
        <ObjectTooltip 
          object={hoveredObject} 
          onClose={() => setHoveredObject(null)} 
        />
      )}
      
      {/* Контекстное меню */}
      {contextMenu && (
        <ContextMenu 
          menu={contextMenu}
          onSelect={(action) => {
            if (onObjectRightClick) {
              onObjectRightClick({ ...contextMenu, selectedAction: action });
            }
            setContextMenu(null);
          }}
        />
      )}
    </div>
  );
}

/**
 * SceneObject - Отдельный объект сцены (NPC, враг, сундук и т.д.)
 */
function SceneObject({ object, onClick, onRightClick, onHover }) {
  const getTypeClass = () => {
    switch (object.type) {
      case 'enemy': return 'enemy';
      case 'npc': return 'npc';
      case 'chest': return 'chest';
      case 'door': return 'door';
      case 'interactive': return 'interactive';
      default: return '';
    }
  };

  return (
    <div
      className={`scene-object ${getTypeClass()}`}
      style={{
        left: `${(object.x / 800) * 100}%`,
        top: `${(object.y / 600) * 100}%`,
        transform: 'translate(-50%, -50%)'
      }}
      onClick={(e) => onClick(object, e)}
      onContextMenu={(e) => onRightClick(object, e)}
      onMouseEnter={() => onHover(object)}
      onMouseLeave={() => onHover(null)}
      title={object.name}
    >
      <span className="object-icon">{object.icon}</span>
      {object.hp !== undefined && object.max_hp && (
        <div className="hp-bar">
          <div 
            className="hp-fill" 
            style={{ width: `${(object.hp / object.max_hp) * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}

/**
 * PlayerAvatar - Аватар игрока с анимацией перемещения
 */
function PlayerAvatar({ position, isMoving, sceneWidth, sceneHeight }) {
  return (
    <div
      className={`player-avatar ${isMoving ? 'moving' : ''}`}
      style={{
        left: `${(position.x / sceneWidth) * 100}%`,
        top: `${(position.y / sceneHeight) * 100}%`,
        transform: `translate(-50%, -50%) scaleX(${position.facing === 'left' ? -1 : 1})`
      }}
    >
      <span className="avatar-icon">{position.icon || '🧙'}</span>
      {isMoving && <div className="movement-dust" />}
    </div>
  );
}

/**
 * ObjectTooltip - Всплывающая подсказка при наведении
 */
function ObjectTooltip({ object, onClose }) {
  return (
    <div className="object-tooltip">
      <div className="tooltip-header">
        <span className="tooltip-icon">{object.icon}</span>
        <span className="tooltip-name">{object.name}</span>
        <button className="tooltip-close" onClick={onClose}>×</button>
      </div>
      <div className="tooltip-body">
        {object.type === 'enemy' && (
          <div className="tooltip-stats">
            <div>❤️ HP: {object.hp}/{object.max_hp}</div>
            {object.damage && <div>⚔️ Урон: {object.damage}</div>}
          </div>
        )}
        {object.description && (
          <p className="tooltip-description">{object.description}</p>
        )}
        {object.interactions && (
          <div className="tooltip-actions">
            <small>Действия:</small>
            <div className="action-tags">
              {object.interactions.map(action => (
                <span key={action} className="action-tag">{action}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * ContextMenu - Контекстное меню для объектов
 */
function ContextMenu({ menu, onSelect }) {
  return (
    <div 
      className="context-menu"
      style={{ left: menu.x, top: menu.y }}
    >
      <div className="context-menu-header">
        {menu.objectId}
      </div>
      <div className="context-menu-items">
        {menu.actions.map((action, idx) => (
          <button
            key={idx}
            className="context-menu-item"
            onClick={(e) => {
              e.stopPropagation();
              onSelect(action);
            }}
          >
            {action}
          </button>
        ))}
      </div>
    </div>
  );
}

export default InteractiveScene;
