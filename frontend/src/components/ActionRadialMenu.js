// frontend/src/components/ActionRadialMenu.js

import React, { useState, useEffect } from 'react';
import './ActionRadialMenu.css';

/**
 * ActionRadialMenu - Круговое меню для быстрых действий
 * 
 * Props:
 * - actions: массив действий [{ id, icon, label, color }]
 * - onSelect: callback при выборе действия
 * - isOpen: состояние открытия меню
 * - onClose: callback при закрытии
 * - position: { x, y } позиция центра меню
 */
function ActionRadialMenu({ 
  actions = [], 
  onSelect, 
  isOpen, 
  onClose,
  position = { x: 0, y: 0 }
}) {
  const [rotation, setRotation] = useState(0);

  // Анимация появления
  useEffect(() => {
    if (isOpen) {
      setRotation(0);
      const timer = setTimeout(() => setRotation(1), 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Закрытие по ESC
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  if (!isOpen || !actions.length) return null;

  const radius = 80; // Радиус меню в пикселях
  const angleStep = (2 * Math.PI) / actions.length;

  return (
    <div className="radial-menu-overlay" onClick={onClose}>
      <div 
        className="radial-menu-container"
        style={{ left: position.x, top: position.y }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Центральный круг */}
        <div className="radial-menu-center">
          <span>⚡</span>
        </div>
        
        {/* Слоты действий */}
        {actions.map((action, index) => {
          const angle = index * angleStep - Math.PI / 2; // Начинаем сверху
          const x = Math.cos(angle) * radius;
          const y = Math.sin(angle) * radius;
          
          return (
            <button
              key={action.id}
              className="radial-menu-item"
              style={{
                transform: `translate(${x}px, ${y}px)`,
                backgroundColor: action.color || 'var(--bg-secondary)',
                animationDelay: `${index * 0.05}s`
              }}
              onClick={() => {
                onSelect(action);
                onClose();
              }}
              title={action.label}
            >
              <span className="radial-menu-icon">{action.icon}</span>
              <span className="radial-menu-label">{action.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * RadialMenuTrigger - Компонент-триггер для открытия радиального меню
 * 
 * Props:
 * - actions: массив действий
 * - onSelect: callback при выборе
 * - children: элемент, который открывает меню (обычно кнопка)
 */
function RadialMenuTrigger({ actions, onSelect, children }) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  const handleOpen = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const rect = e.currentTarget.getBoundingClientRect();
    setPosition({
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2
    });
    setIsOpen(true);
  };

  return (
    <>
      {React.cloneElement(children, {
        onClick: handleOpen
      })}
      <ActionRadialMenu
        actions={actions}
        onSelect={onSelect}
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        position={position}
      />
    </>
  );
}

export default ActionRadialMenu;
export { RadialMenuTrigger };
