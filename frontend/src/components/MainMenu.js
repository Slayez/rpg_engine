import React, { useState, useEffect } from 'react';
import { getSaves, deleteWorld } from '../api';
import './MainMenu.css';

function MainMenu({ onNewGame, onLoadWorld }) {
  const [saves, setSaves] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchSaves = async () => {
    setLoading(true);
    try { setSaves(await getSaves() || []); } catch { setSaves([]); }
    setLoading(false);
  };
  useEffect(() => { fetchSaves(); }, []);

  const handleDelete = async (slotId) => {
    if (!window.confirm('Удалить мир безвозвратно?')) return;
    try { await deleteWorld(slotId); fetchSaves(); } catch { alert('Ошибка удаления'); }
  };

  return (
    <div className="app-container">
      <div className="card-panel text-center">
        <h1 className="menu-title">📖 Narrative Engine</h1>
        <p className="text-muted mb-4">Текстовая RPG с искусственным интеллектом</p>
        <button className="btn-primary mb-4" onClick={onNewGame}>➕ Новая игра</button>
        <hr style={{ borderColor: 'var(--border)' }} />
        <h5 className="mb-3">Сохранения</h5>
        {loading ? <p className="text-muted">Загрузка...</p>
          : saves.length === 0 ? <p className="text-muted">Нет сохранений</p>
          : saves.map(save => (
              <div key={save.slot_id} className="save-card">
                <div>
                  <div style={{ fontWeight: 600 }}>{save.player_name}</div>
                  <small className="text-muted">{save.race} · Уровень {save.level} · {save.location}</small>
                </div>
                <div className="d-flex gap-2">
                  <button className="btn-outline" onClick={() => onLoadWorld(save.slot_id)}>Загрузить</button>
                  <button className="btn-outline" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}
                    onClick={() => handleDelete(save.slot_id)}>✕</button>
                </div>
              </div>
            ))
        }
      </div>
    </div>
  );
}

export default MainMenu;