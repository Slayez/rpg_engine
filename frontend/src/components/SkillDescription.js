// frontend/src/components/SkillDescription.js

import React from 'react';

const TYPE_ICONS = {
  fire: '🔥',
  water: '💧',
  earth: '🌍',
  air: '🌪️',
  magical: '✨',
  physical: '⚔️',
  heal: '💚',
  none: '',
};

function SkillDescription({ skill, selected = false }) {
  if (!skill) return null;

  const {
    name,
    level = 1,
    description,
    category,
    effect,
    cost_mp = 0,
    cast_time = 0,
    cooldown = 0,
    range = '',
    duration = '',
    damage = '0',
    damage_type = 'none',
    requirements = '',
    passive = false,
  } = skill;

  const typeIcon = TYPE_ICONS[damage_type] || '';
  const isHeal = damage_type === 'heal';
  const damageColor = isHeal ? 'var(--success)' : 'var(--danger)';

  const castStr = cast_time > 0 ? `${cast_time} сек` : 'мгн.';
  const cdStr = cooldown > 0 ? `${cooldown} сек` : '0 сек';
  const rangeStr = range || 'на себя';
  const durationStr = duration || '—';
  const mpStr = cost_mp > 0 ? `${cost_mp}` : '0';

  const cardClassName = `skill-card${selected ? ' selected' : ''}`;

  return (
    <div className={cardClassName} data-category={category}>
      <div className="skill-aa-header">
        <span className="skill-aa-name">{name}</span>
        <span className={`skill-aa-badge ${passive ? 'passive' : 'active'}`}>
          {passive ? 'Пассивный' : 'Активный'}
        </span>        
      </div>
      <span className="skill-aa-level">Ур. {level}</span>
      <div className="skill-aa-flavor">{description || effect}</div>

      <div className="skill-aa-stats">
        <div className="stat-row">
          <span className="stat-label">MP</span>
          <span className="stat-value">{mpStr}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Каст</span>
          <span className="stat-value">{castStr}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">КД</span>
          <span className="stat-value">{cdStr}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Дальность</span>
          <span className="stat-value">{rangeStr}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Длит.</span>
          <span className="stat-value">{durationStr}</span>
        </div>
      </div>

      {damage && damage !== '0' && damage !== 'N/A' && damage.toLowerCase() !== 'none' && (
        <div className="skill-aa-damage" style={{ color: damageColor }}>
          {typeIcon} {isHeal ? 'Лечение' : 'Урон'}: {damage}
        </div>
      )}

      {effect && <div className="skill-aa-effect">{effect}</div>}

      {requirements && (
        <div className="skill-aa-requirements">
          <span>🔒 {requirements}</span>
        </div>
      )}
    </div>
  );
}

export default SkillDescription;