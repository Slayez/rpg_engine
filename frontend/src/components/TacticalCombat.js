// frontend/src/components/TacticalCombat.js
// Тактический интерфейс боя - сетка 10x10, перемещение, зоны атаки

import React, { useState, useCallback, useMemo } from 'react';
import './TacticalCombat.css';

/**
 * TacticalCombat - Пошаговый тактический бой на сетке
 * 
 * Props:
 * - units: массив юнитов [{ id, type, name, x, y, hp, maxHp, icon, team }]
 * - gridSize: размер сетки (по умолчанию 10)
 * - cellSize: размер ячейки в пикселях (по умолчанию 50)
 * - selectedUnitId: ID выбранного юнита
 * - onUnitSelect: callback при выборе юнита
 * - onMoveUnit: callback при перемещении (unitId, newX, newY)
 * - onAttack: callback при атаке (attackerId, targetId, skill?)
 * - onSkillUse: callback при использовании навыка (unitId, skill, targetX, targetY)
 * - visibleCells: массив видимых ячеек для текущего юнита
 * - attackZone: массив ячеек в зоне атаки
 */
function TacticalCombat({
  units = [],
  gridSize = 10,
  cellSize = 50,
  selectedUnitId = null,
  onUnitSelect,
  onMoveUnit,
  onAttack,
  onSkillUse,
  visibleCells = [],
  attackZone = [],
  showGrid = true,
  turn = 1,
  currentTurnUnitId = null
}) {
  const [hoveredCell, setHoveredCell] = useState(null);
  const [draggedUnit, setDraggedUnit] = useState(null);

  // Получить юнита по координатам
  const getUnitAt = useCallback((x, y) => {
    return units.find(u => u.x === x && u.y === y);
  }, [units]);

  // Проверка, является ли ячейка видимой
  const isVisible = useCallback((x, y) => {
    if (visibleCells.length === 0) return true; // Если не задано, считаем все видимыми
    return visibleCells.some(cell => cell.x === x && cell.y === y);
  }, [visibleCells]);

  // Проверка, входит ли ячейка в зону атаки
  const isAttackZone = useCallback((x, y) => {
    return attackZone.some(cell => cell.x === x && cell.y === y);
  }, [attackZone]);

  // Обработка клика по ячейке
  const handleCellClick = useCallback((x, y) => {
    const unit = getUnitAt(x, y);
    
    if (unit) {
      // Клик по юниту
      if (selectedUnitId && unit.id !== selectedUnitId) {
        // Атака врага
        const attacker = units.find(u => u.id === selectedUnitId);
        if (attacker && unit.team !== attacker.team) {
          onAttack?.(selectedUnitId, unit.id);
        } else {
          onUnitSelect?.(unit.id);
        }
      } else {
        onUnitSelect?.(unit.id);
      }
    } else if (selectedUnitId && isAttackZone(x, y)) {
      // Использование навыка в область
      onSkillUse?.(selectedUnitId, null, x, y);
    } else if (selectedUnitId && isVisible(x, y)) {
      // Перемещение
      onMoveUnit?.(selectedUnitId, x, y);
    }
  }, [getUnitAt, selectedUnitId, isAttackZone, isVisible, onAttack, onUnitSelect, onMoveUnit, onSkillUse, units]);

  // Drag-and-drop handlers
  const handleDragStart = (e, unit) => {
    if (unit.id !== currentTurnUnitId) {
      e.preventDefault();
      return;
    }
    setDraggedUnit(unit);
    e.dataTransfer.setData('unitId', unit.id);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e, x, y) => {
    e.preventDefault();
    const unit = getUnitAt(x, y);
    if (!unit && isVisible(x, y)) {
      e.dataTransfer.dropEffect = 'move';
    } else {
      e.dataTransfer.dropEffect = 'none';
    }
  };

  const handleDrop = (e, x, y) => {
    e.preventDefault();
    const unitId = e.dataTransfer.getData('unitId');
    if (unitId && !getUnitAt(x, y) && isVisible(x, y)) {
      onMoveUnit?.(unitId, x, y);
    }
    setDraggedUnit(null);
  };

  // Инициатива таймлайн
  const initiativeOrder = useMemo(() => {
    return [...units].sort((a, b) => {
      const aInit = a.initiative || 0;
      const bInit = b.initiative || 0;
      return bInit - aInit;
    });
  }, [units]);

  return (
    <div className="tactical-combat">
      {/* Таймлайн инициативы */}
      <div className="initiative-timeline">
        <div className="timeline-label">Инициатива (Ход {turn})</div>
        <div className="timeline-units">
          {initiativeOrder.map((unit, idx) => (
            <div
              key={unit.id}
              className={`timeline-unit ${unit.id === currentTurnUnitId ? 'active' : ''}`}
            >
              <span className="unit-icon">{unit.icon}</span>
              <span className="unit-name">{unit.name}</span>
              {unit.id === currentTurnUnitId && <span className="turn-indicator">➤</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Боевая сетка */}
      <div 
        className="tactical-grid-container"
        style={{ 
          width: gridSize * cellSize, 
          height: gridSize * cellSize 
        }}
      >
        <div className="tactical-grid">
          {Array.from({ length: gridSize }).map((_, y) =>
            Array.from({ length: gridSize }).map((_, x) => {
              const unit = getUnitAt(x, y);
              const isHighlighted = hoveredCell?.x === x && hoveredCell?.y === y;
              const inAttackZone = isAttackZone(x, y);
              const canMoveTo = selectedUnitId && !unit && isVisible(x, y);
              
              return (
                <div
                  key={`${x}-${y}`}
                  className={`grid-cell 
                    ${isHighlighted ? 'highlighted' : ''}
                    ${inAttackZone ? 'attack-zone' : ''}
                    ${canMoveTo ? 'movable' : ''}
                    ${!isVisible(x, y) ? 'hidden' : ''}
                  `}
                  style={{ width: cellSize, height: cellSize }}
                  onClick={() => handleCellClick(x, y)}
                  onMouseEnter={() => setHoveredCell({ x, y })}
                  onMouseLeave={() => setHoveredCell(null)}
                  onDragOver={(e) => handleDragOver(e, x, y)}
                  onDrop={(e) => handleDrop(e, x, y)}
                >
                  {showGrid && <span className="cell-coords">{x},{y}</span>}
                  
                  {unit && (
                    <div
                      className={`game-unit ${unit.team} ${selectedUnitId === unit.id ? 'selected' : ''}`}
                      draggable={unit.id === currentTurnUnitId}
                      onDragStart={(e) => handleDragStart(e, unit)}
                    >
                      <span className="unit-icon">{unit.icon}</span>
                      <div className="unit-hp-bar">
                        <div 
                          className="hp-fill" 
                          style={{ width: `${(unit.hp / unit.maxHp) * 100}%` }}
                        />
                      </div>
                      {unit.name && (
                        <span className="unit-name-tag">{unit.name}</span>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Эффекты на сетке */}
        <div className="combat-effects-layer">
          {/* Сюда будут добавляться временные эффекты атак */}
        </div>
      </div>

      {/* Информация о выбранном юните */}
      {selectedUnitId && (
        <div className="selected-unit-info">
          {(() => {
            const unit = units.find(u => u.id === selectedUnitId);
            if (!unit) return null;
            return (
              <>
                <h4>{unit.icon} {unit.name}</h4>
                <div className="unit-stats">
                  <div>❤️ HP: {unit.hp}/{unit.maxHp}</div>
                  {unit.mp !== undefined && <div>💧 MP: {unit.mp}/{unit.maxMp}</div>}
                  {unit.damage !== undefined && <div>⚔️ Урон: {unit.damage}</div>}
                  {unit.defense !== undefined && <div>🛡️ Защита: {unit.defense}</div>}
                </div>
                {unit.skills && unit.skills.length > 0 && (
                  <div className="unit-skills">
                    <small>Навыки:</small>
                    <div className="skills-list">
                      {unit.skills.map((skill, idx) => (
                        <button
                          key={idx}
                          className="skill-btn"
                          onClick={() => onSkillUse?.(unit.id, skill)}
                          disabled={currentTurnUnitId !== unit.id}
                        >
                          {skill.name} ({skill.cost_mp} MP)
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}

export default TacticalCombat;
