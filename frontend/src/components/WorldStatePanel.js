import React from 'react';

function WorldStatePanel({ worldState }) {
  const renderState = (obj, depth = 0) => {
    if (typeof obj !== 'object' || obj === null) return String(obj);
    return (
      <ul className={`list-unstyled ${depth > 0 ? 'ms-3' : ''}`}>
        {Object.entries(obj).map(([key, value]) => (
          <li key={key}>
            <strong>{key}:</strong> {typeof value === 'object' ? renderState(value, depth + 1) : String(value)}
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="card">
      <div className="card-header bg-secondary text-white">Состояние мира</div>
      <div className="card-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
        {Object.keys(worldState).length === 0 ? (
          <p className="text-muted">Загрузка...</p>
        ) : (
          renderState(worldState)
        )}
      </div>
    </div>
  );
}

export default WorldStatePanel;