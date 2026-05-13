// frontend/src/components/InventoryGrid.js
// Drag-and-drop инвентарь с Grid-раскладкой (как в Diablo)

import React, { useState, useCallback } from 'react';
import './InventoryGrid.css';

/**
 * InventoryGrid - Grid-инвентарь с drag-and-drop
 * 
 * Props:
 * - inventory: массив предметов [{ id, name, type, icon, size: [w,h], equipped }]
 * - equipment: объект экипировки { head: item, chest: item, weapon: item, ... }
 * - gridSize: [width, height] сетки инвентаря (по умолчанию [4, 8])
 * - onEquip: callback при экипировке (itemId)
 * - onUnequip: callback при снятии (itemId)
 * - onMoveItem: callback при перемещении (itemId, newSlot)
 * - onItemClick: callback при клике на предмет
 */
function InventoryGrid({
  inventory = [],
  equipment = {},
  gridSize = [4, 8],
  onEquip,
  onUnequip,
  onMoveItem,
  onItemClick
}) {
  const [draggedItem, setDraggedItem] = useState(null);
  const [hoveredSlot, setHoveredSlot] = useState(null);
  const [tooltipItem, setTooltipItem] = useState(null);

  // Слоты экипировки
  const equipmentSlots = [
    { id: 'head', label: 'Голова', icon: '🪖' },
    { id: 'chest', label: 'Тело', icon: '👕' },
    { id: 'legs', label: 'Ноги', icon: '👖' },
    { id: 'feet', label: 'Ступни', icon: '👢' },
    { id: 'hands', label: 'Руки', icon: '🧤' },
    { id: 'mainHand', label: 'Правая рука', icon: '⚔️' },
    { id: 'offHand', label: 'Левая рука', icon: '🛡️' },
    { id: 'accessory1', label: 'Кольцо 1', icon: '💍' },
    { id: 'accessory2', label: 'Кольцо 2', icon: '💍' },
    { id: 'neck', label: 'Шея', icon: '📿' }
  ];

  // Создание пустой сетки инвентаря
  const createEmptyGrid = () => {
    const grid = [];
    for (let y = 0; y < gridSize[1]; y++) {
      grid[y] = [];
      for (let x = 0; x < gridSize[0]; x++) {
        grid[y][x] = null;
      }
    }
    return grid;
  };

  // Размещение предметов в сетке
  const fillGridWithItems = useCallback(() => {
    const grid = createEmptyGrid();
    
    inventory.forEach((item, index) => {
      if (!item.equipped && item.slot) {
        const [x, y] = item.slot;
        const size = item.size || [1, 1];
        
        // Проверка выхода за границы
        if (x + size[0] <= gridSize[0] && y + size[1] <= gridSize[1]) {
          // Заполняем ячейки предмета
          for (let dy = 0; dy < size[1]; dy++) {
            for (let dx = 0; dx < size[0]; dx++) {
              if (grid[y + dy] && grid[y + dy][x + dx] === null) {
                grid[y + dy][x + dx] = index;
              }
            }
          }
        }
      }
    });
    
    return grid;
  }, [inventory, gridSize]);

  const inventoryGrid = fillGridWithItems();

  // Drag handlers
  const handleDragStart = (e, item, index, isEquipment = false) => {
    setDraggedItem({ item, index, isEquipment });
    e.dataTransfer.setData('text/plain', JSON.stringify({ index, isEquipment }));
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e, slotX, slotY, targetSlotId = null) => {
    e.preventDefault();
    setHoveredSlot({ x: slotX, y: slotY, slotId: targetSlotId });
  };

  const handleDrop = (e, slotX, slotY, targetSlotId = null) => {
    e.preventDefault();
    
    if (!draggedItem) return;
    
    const { item, index, isEquipment } = draggedItem;
    
    if (targetSlotId) {
      // Drop на слот экипировки
      if (!isEquipment && onEquip) {
        onEquip(item.id || index);
      } else if (isEquipment && onUnequip) {
        onUnequip(equipment[targetSlotId].id || targetSlotId);
      }
    } else {
      // Drop в сетку инвентаря
      if (onMoveItem) {
        onMoveItem(item.id || index, [slotX, slotY]);
      }
    }
    
    setDraggedItem(null);
    setHoveredSlot(null);
  };

  const handleDragEnd = () => {
    setDraggedItem(null);
    setHoveredSlot(null);
  };

  // Сравнение предметов для tooltip
  const getItemStats = (item) => {
    const stats = [];
    if (item.damage) stats.push(`⚔️ Урон: ${item.damage}`);
    if (item.defense) stats.push(`🛡️ Защита: ${item.defense}`);
    if (item.stat_bonuses) {
      Object.entries(item.stat_bonuses).forEach(([stat, val]) => {
        stats.push(`${stat}: ${val > 0 ? '+' : ''}${val}`);
      });
    }
    if (item.weight) stats.push(`⚖️ Вес: ${item.weight} кг`);
    return stats;
  };

  return (
    <div className="inventory-grid-container">
      {/* Экипировка */}
      <div className="equipment-section">
        <h6 className="section-title">Экипировка</h6>
        <div className="equipment-layout">
          {equipmentSlots.map(slot => {
            const item = equipment[slot.id];
            const isHighlighted = hoveredSlot?.slotId === slot.id;
            
            return (
              <div
                key={slot.id}
                className={`equipment-slot ${item ? 'occupied' : 'empty'} ${isHighlighted ? 'highlighted' : ''}`}
                onDragOver={(e) => handleDragOver(e, 0, 0, slot.id)}
                onDrop={(e) => handleDrop(e, 0, 0, slot.id)}
                onClick={() => item && onUnequip?.(item.id || slot.id)}
              >
                {item ? (
                  <div
                    className="item"
                    draggable
                    onDragStart={(e) => handleDragStart(e, item, slot.id, true)}
                    onDragEnd={handleDragEnd}
                    onMouseEnter={() => setTooltipItem(item)}
                    onMouseLeave={() => setTooltipItem(null)}
                    onClick={(e) => {
                      e.stopPropagation();
                      onItemClick?.(item);
                    }}
                  >
                    <span className="item-icon">{item.icon || '📦'}</span>
                    {item.size && item.size.length === 2 && (
                      <span className="item-size">{item.size[0]}x{item.size[1]}</span>
                    )}
                  </div>
                ) : (
                  <span className="slot-placeholder">{slot.icon}</span>
                )}
                <span className="slot-label">{slot.label}</span>
              </div>
            );
          })}
          
          {/* Аватар персонажа в центре */}
          <div className="character-avatar">
            <div className="avatar-silhouette">🧙</div>
          </div>
        </div>
      </div>

      {/* Сетка инвентаря */}
      <div className="inventory-section">
        <h6 className="section-title">
          Инвентарь ({inventory.filter(i => !i.equipped).length}/{gridSize[0] * gridSize[1]})
        </h6>
        <div 
          className="inventory-grid"
          style={{ 
            gridTemplateColumns: `repeat(${gridSize[0]}, 50px)`,
            gridTemplateRows: `repeat(${gridSize[1]}, 50px)`
          }}
        >
          {inventoryGrid.map((row, y) =>
            row.map((itemIndex, x) => {
              const isOccupied = itemIndex !== null;
              const isFirstCell = isOccupied && (
                x === 0 || inventoryGrid[y][x - 1] !== itemIndex
              ) || (y === 0 || inventoryGrid[y - 1]?.[x] !== itemIndex);
              
              const item = isOccupied ? inventory[itemIndex] : null;
              const isMainCell = isOccupied && isFirstCell && item && !item.equipped;
              const isHighlighted = hoveredSlot?.x === x && hoveredSlot?.y === y;
              
              if (isOccupied && !isFirstCell) {
                return (
                  <div key={`${x}-${y}`} className="grid-cell occupied" />
                );
              }
              
              return (
                <div
                  key={`${x}-${y}`}
                  className={`grid-cell ${isHighlighted ? 'highlighted' : ''}`}
                  onDragOver={(e) => handleDragOver(e, x, y)}
                  onDrop={(e) => handleDrop(e, x, y)}
                >
                  {isMainCell && (
                    <div
                      className="item"
                      draggable
                      style={{
                        gridColumn: `span ${item.size?.[0] || 1}`,
                        gridRow: `span ${item.size?.[1] || 1}`
                      }}
                      onDragStart={(e) => handleDragStart(e, item, itemIndex)}
                      onDragEnd={handleDragEnd}
                      onMouseEnter={() => setTooltipItem(item)}
                      onMouseLeave={() => setTooltipItem(null)}
                      onClick={() => onItemClick?.(item)}
                    >
                      <span className="item-icon">{item.icon || '📦'}</span>
                      {item.size && item.size.length === 2 && (
                        <span className="item-size">{item.size[0]}x{item.size[1]}</span>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Tooltip предмета */}
      {tooltipItem && (
        <ItemTooltip 
          item={tooltipItem} 
          stats={getItemStats(tooltipItem)}
          onClose={() => setTooltipItem(null)}
        />
      )}
    </div>
  );
}

/**
 * ItemTooltip - Всплывающая подсказка для предмета
 */
function ItemTooltip({ item, stats, onClose }) {
  return (
    <div className="item-tooltip">
      <div className="tooltip-header">
        <span className="tooltip-name">{item.name}</span>
        <button className="tooltip-close" onClick={onClose}>×</button>
      </div>
      <div className="tooltip-body">
        <p className="tooltip-description">{item.description}</p>
        {stats.length > 0 && (
          <div className="tooltip-stats">
            {stats.map((stat, idx) => (
              <div key={idx} className="tooltip-stat">{stat}</div>
            ))}
          </div>
        )}
        {item.type && (
          <div className="tooltip-type">Тип: {item.type}</div>
        )}
      </div>
    </div>
  );
}

export default InventoryGrid;
