const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const RACES = [
  { id: 'human', name: 'Человек', description: 'Сбалансированные характеристики.', bonuses: {} },
  { id: 'elf', name: 'Эльф', description: 'Ловкость и магия.', bonuses: { dexterity: 2, wisdom: 2, magic_defense: 1, speed: 1 } },
  { id: 'beastkin', name: 'Зверолюд', description: 'Сила и выносливость.', bonuses: { strength: 2, vitality: 2, defense: 2 } },
  { id: 'slime', name: 'Слайм', description: 'Уникальные способности.', bonuses: { wisdom: 3, luck: 2, evasion: 5 } }
];

export const getSaves = async () => {
  const res = await fetch('/saves');
  if (!res.ok) throw new Error('Ошибка загрузки сохранений');
  return res.json();
};

export const createWorld = async (name, raceId) => {
  const res = await fetch('/saves', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, race_id: raceId })
  });
  if (!res.ok) throw new Error('Ошибка создания мира');
  return res.json();
};

export const deleteWorld = async (slotId) => {
  const res = await fetch(`/saves/${slotId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Ошибка удаления');
};

export const getWorld = async (slotId) => {
  const res = await fetch(`/world?slot_id=${slotId}`);
  if (!res.ok) throw new Error('Мир не найден');
  return res.json();
};

export const sendAction = async (slotId, action) => {
  const res = await fetch('/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slot_id: slotId, action })
  });
  if (!res.ok) throw new Error('Ошибка действия');
  return res.json();
};

export const sendActionStream = (slotId, action, onChunk, onDone, onError, onSystemMessage) => {
  const controller = new AbortController();
  fetch('/action/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slot_id: slotId, action }),
    signal: controller.signal
  })
    .then(response => {
      if (!response.ok) throw new Error('Ошибка сети');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      const read = () => {
        reader.read().then(({ done, value }) => {
          if (done) return;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === 'text') {
                  onChunk(data.content);
                } else if (data.type === 'system_message') {
                  if (onSystemMessage) onSystemMessage(data.text, data.msg_type);
                } else if (data.type === 'done') {
                  onDone(data);
                  return;
                } else if (data.type === 'error') {
                  onError(data.message);
                  return;
                }
              } catch (e) {}
            }
          }
          read();
        });
      };
      read();
    })
    .catch(err => onError(err.message));
  return controller;
};

export const undoAction = async (slotId) => {
  const res = await fetch('/action/undo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slot_id: slotId, action: '' })
  });
  if (!res.ok) throw new Error('Ошибка отмены');
  return res.json();
};

export const retryAction = async (slotId) => {
  const res = await fetch('/action/retry', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slot_id: slotId, action: '' })
  });
  if (!res.ok) throw new Error('Ошибка перегенерации');
  return res.json();
};

export const editAction = async (slotId, newAction) => {
  const res = await fetch('/action/edit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slot_id: slotId, action: newAction })
  });
  if (!res.ok) throw new Error('Ошибка редактирования');
  return res.json();
};

export const fetchMemory = async (slotId, n = 10) => {
  const res = await fetch(`/memory?slot_id=${slotId}&n_results=${n}`);
  if (!res.ok) throw new Error('Ошибка загрузки памяти');
  return res.json();
};

export const generateStartSkills = async (name, raceId) => {
  const res = await fetch('/generate-start-skills', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ name, race_id: raceId })
  });
  if (!res.ok) throw new Error('Ошибка генерации навыков');
  return res.json();
};

export const chooseStartSkills = async (slotId, skills) => {
  const res = await fetch('/choose-start-skills', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ slot_id: slotId, skills })
  });
  if (!res.ok) throw new Error('Ошибка выбора навыков');
  return res.json();
};