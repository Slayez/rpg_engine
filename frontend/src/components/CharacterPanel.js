import React from 'react';
import { RACES } from '../api';
import SkillDescription from './SkillDescription';
import InventoryGrid from './InventoryGrid';
import './CharacterPanel.css';
import { STAT_LABELS } from '../utils/statLabels';

const RACE_NAMES = Object.fromEntries(RACES.map(r => [r.id, r.name]));

function CharacterPanel({ worldState }) {
  const player = worldState?.characters?.player || {};
  const stats = player?.stats || {};
  const skills = player?.skills || [];
  const inventory = player?.inventory || [];
  const equipped = inventory.filter(item => item.equipped);
  const unequipped = inventory.filter(item => !item.equipped);

  // Функция для получения иконки по типу предмета
  const getIconByType = (type) => {
    const icons = {
      weapon: "⚔️",
      armor: "🛡️",
      helmet: "🪖",
      chest: "👕",
      legs: "👖",
      boots: "👢",
      gloves: "🧤",
      shield: "🛡️",
      potion: "🧪",
      ring: "💍",
      amulet: "📿",
      accessory: "💎",
      misc: "📦"
    };
    return icons[type] || "📦";
  };

  // Бонусы только от экипировки
  const bonuses = equipped.reduce((acc, item) => {
    if (item.stat_bonuses) {
      Object.entries(item.stat_bonuses).forEach(([stat, val]) => {
        acc[stat] = (acc[stat] || 0) + val;
      });
    }
    return acc;
  }, {});
  const totalDefense = equipped.reduce((sum, item) => sum + (item.defense || 0), 0);

  const nextLevelExp = Math.floor(100 * (stats.level || 1) * 1.5);
  const hpPerc = Math.min(100, (player.health / stats.hp) * 100) || 0;
  const mpPerc = Math.min(100, (player.mp / stats.mp) * 100) || 0;
  const expPerc = Math.min(100, ((stats.exp || 0) / nextLevelExp) * 100) || 0;

  // Группировка навыков по категориям для красивого отображения
  const groupedSkills = skills.reduce((acc, skill) => {
    const cat = skill.category || 'Без категории';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(skill);
    return acc;
  }, {});

  return (
    <div className="card-panel char-panel">
      <div className="char-header">
        <h5>{player.name}</h5>
        <span className="badge bg-accent">{RACE_NAMES[player.race] || player.race}</span>
      </div>
      <div className="resources">
        <div>❤️ HP: {player.health}/{stats.hp} <div className="progress"><div className="progress-bar bg-danger" style={{width: hpPerc+'%'}} /></div></div>
        <div>💙 MP: {player.mp}/{stats.mp} <div className="progress"><div className="progress-bar bg-primary" style={{width: mpPerc+'%'}} /></div></div>
        <div>⭐ Ур. {stats.level} | ✨ Опыт: {stats.exp}/{nextLevelExp} <div className="progress"><div className="progress-bar bg-warning" style={{width: expPerc+'%'}} /></div></div>
      </div>
      <div className="stats-grid">
        {Object.entries(stats).filter(([k]) => !['level','exp','hp','mp'].includes(k)).map(([stat, value]) => {
          const bonus = bonuses[stat] || 0;
          return (
            <div key={stat} className="stat-item">
              <span>{STAT_LABELS[stat] || stat}</span>
              <span>{value}{bonus !== 0 && <span style={{color: bonus>0?'var(--success)':'var(--danger)'}}> ({bonus>0?'+'+bonus:bonus})</span>}</span>
            </div>
          );
        })}
        {totalDefense > 0 && <div className="stat-item"><span>🛡️ Общая защита</span><span>{totalDefense}</span></div>}
      </div>
      
      {/* Grid-инвентарь с drag-and-drop */}
      <InventoryGrid
        inventory={inventory}
        equipment={{}}
        onEquip={(itemId) => console.log('Equip:', itemId)}
        onUnequip={(itemId) => console.log('Unequip:', itemId)}
        onMoveItem={(itemId, slot) => console.log('Move:', itemId, slot)}
        onItemClick={(item) => console.log('Item click:', item)}
      />
      
      {equipped.length > 0 && (
        <div className="mt-3">
          <h6>Экипировка</h6>
          {equipped.map((item,i) => (
            <div key={i} className="equip-item">
              <strong>{item.icon || getIconByType(item.type)} {item.name}</strong>
              <span className="item-desc">{item.description}</span>
            </div>
          ))}
        </div>
      )}
      {unequipped.length > 0 && (
        <div className="mt-3">
          <h6>Инвентарь</h6>
          {unequipped.map((item,i) => (
            <div key={i} className="inventory-item-row">
              <span>{item.icon || getIconByType(item.type)} {item.name}</span>
              <span className="item-desc">{item.description}</span>
            </div>
          ))}
        </div>
      )}
      <div className="mt-3">
        <h6>Навыки</h6>
        {Object.entries(groupedSkills).length === 0 && <span className="text-muted">нет</span>}
        {Object.entries(groupedSkills).map(([category, skillsArr]) => (
          <div key={category} className="skill-category">
            <h4 className="category-title" style={{ fontSize: '1.1rem', marginTop: '16px' }}>
              {category}
            </h4>
            <div className="skill-grid">
              {skillsArr.map((skill, idx) => (
                <SkillDescription key={idx} skill={skill} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default CharacterPanel;