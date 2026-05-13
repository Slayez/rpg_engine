// frontend/src/components/CharacterCreation.js

import React, { useState } from 'react';
import { createWorld, generateStartSkills, chooseStartSkills, RACES } from '../api';
import { STAT_LABELS } from '../utils/statLabels';
import SkillDescription from './SkillDescription';
import './CharacterCreation.css';

// Получаем количество навыков из API (должно совпадать с backend config)
const MAX_START_SKILLS = 3;

const CATEGORY_ICONS = {
  "Магия огня": "🔥",
  "Магия воды": "💧",
  "Магия земли": "🌍",
  "Магия воздуха": "🌪️",
  "Магия пространства": "🌀",
  "Универсальная магия": "✨",
  "Дальний бой": "🏹",
  "Ближний бой": "⚔️",
  "Призыв": "🔮",
  "Защита": "🛡️",
  "Скрытность": "🌑",
  "Исцеление": "💚",
  "Бытовая магия": "🌿",
  "Знания": "📚",
  "Ловкость": "👟",
  "Сила": "💪"
};

function CharacterCreation({ onCreated, onCancel }) {
  const [step, setStep] = useState(0);
  const [name, setName] = useState('');
  const [raceId, setRaceId] = useState(RACES[0]?.id || '');
  const [generatedSkills, setGeneratedSkills] = useState([]);
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleNameRaceSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) { setError('Введите имя'); return; }
    setLoading(true);
    setError('');
    try {
      const res = await generateStartSkills(name.trim(), raceId);
      setGeneratedSkills(res.skills);
      setStep(1);
    } catch (err) {
      setError('Ошибка генерации навыков: ' + err.message);
    }
    setLoading(false);
  };

  const toggleSkill = (skill) => {
    setSelectedSkills(prev => {
      const exists = prev.find(s => s.name === skill.name);
      if (exists) return prev.filter(s => s.name !== skill.name);
      if (prev.length >= MAX_START_SKILLS) return prev;
      return [...prev, skill];
    });
  };

  const handleFinalCreate = async () => {
  if (selectedSkills.length !== MAX_START_SKILLS) { setError(`Выберите ровно ${MAX_START_SKILLS} навыка`); return; }
    setLoading(true);
    setError('');
    try {
      const { slot_id } = await createWorld(name.trim(), raceId);
      await chooseStartSkills(slot_id, selectedSkills);
      onCreated(slot_id);
    } catch (err) {
      setError('Ошибка создания мира: ' + err.message);
    }
    setLoading(false);
  };

  const groupedSkills = generatedSkills.reduce((acc, skill) => {
    const cat = skill.category || 'Без категории';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(skill);
    return acc;
  }, {});

  return (
    <div className="app-container">
      <div className="card-panel">
        <h2 className="text-center mb-4" style={{ color: 'var(--accent)' }}>Создание персонажа</h2>
        
        {step === 0 && (
          <form onSubmit={handleNameRaceSubmit}>
            <div className="mb-3">              
              <label className="form-label">Имя </label>              
              <input className="modal-input" placeholder="Введите имя..." value={name} onChange={e => setName(e.target.value)} maxLength={24} />
            </div>
            <div className="mb-4">
              <label className="form-label">Раса</label>
              <div className="row">
                {RACES.map(race => (
                  <div key={race.id} className="col-md-3 col-6 mb-2">
                    <div className={`race-card ${raceId === race.id ? 'selected' : ''}`}
                         onClick={() => setRaceId(race.id)}>
                      <div className="card-body">
                        <h6 style={{ fontWeight: 600 }}>{race.name}</h6>
                        <small className="text-muted">{race.description}</small>
                        {Object.keys(race.bonuses).length > 0 && (
                          <div className="mt-1">
                            {Object.entries(race.bonuses).map(([k,v]) => (
                              <span key={k} className="badge bg-accent me-1">+{v} {STAT_LABELS[k] || k}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            {error && <div className="alert alert-danger">{error}</div>}
            <div className="d-flex justify-content-between">
              <button type="button" className="btn-outline" onClick={onCancel}>Назад</button>
              <button type="submit" className="btn-primary" disabled={loading}>{loading ? 'Генерация...' : 'Далее'}</button>
            </div>
          </form>
        )}

        {step === 1 && (
          <div>
            <p className="text-muted">Выберите 3 стартовых навыка</p>
            {Object.entries(groupedSkills).map(([category, skills]) => (
              <div key={category} className="skill-category">
                <h4 className="category-title">
                  {CATEGORY_ICONS[category] || '📦'} {category}
                </h4>
                <div className="skill-grid">
                  {skills.map((skill, idx) => {
                    const isSelected = selectedSkills.some(s => s.name === skill.name);
                    return (
                    <div key={idx}
                      className="skill-card-enter"
                      style={{ animationDelay: `${idx * 50}ms` }}
                      onClick={() => toggleSkill(skill)}
                      onAnimationEnd={(e) => e.currentTarget.classList.remove('skill-card-enter')}
                    >
                      <SkillDescription skill={skill} selected={isSelected} />
                    </div>
                    );
                  })}
                </div>
              </div>
            ))}
            {error && <div className="alert alert-danger">{error}</div>}
            <div className="d-flex justify-content-between mt-3">
              <button className="btn-outline" onClick={() => { setStep(0); setSelectedSkills([]); }}>Назад</button>
              <button className="btn-primary" onClick={handleFinalCreate} disabled={loading || selectedSkills.length !== 3}>
                {loading ? 'Создание...' : 'Начать приключение'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default CharacterCreation;