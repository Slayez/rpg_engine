import React from 'react';
import './QuestPanel.css';

function QuestPanel({ worldState }) {
  const quests = worldState?.active_quests || [];
  // Гарантируем, что quests — массив (например, если пришёл объект)
  const questList = Array.isArray(quests) ? quests : [];

  return (
    <div className="card-panel">
      <h5>Активные задания</h5>
      {questList.length === 0 ? (
        <p className="text-muted">Нет активных заданий</p>
      ) : (
        questList.map(q => (
          <div key={q.id} className="quest-card">
            <h6>{q.name}</h6>
            <p>{q.description}</p>
            <ul>
              {(q.objectives || []).map((obj, i) => <li key={i}>{obj}</li>)}
            </ul>
            {q.completed && <span className="badge bg-success">Выполнено</span>}
          </div>
        ))
      )}
    </div>
  );
}

export default QuestPanel;