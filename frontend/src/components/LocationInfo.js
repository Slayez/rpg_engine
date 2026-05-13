import React from 'react';

const locationNames = {
  "forest": "Густой лес",
  "Густой лес": "Густой лес"
};

function LocationInfo({ worldState }) {
  const location = locationNames[worldState?.location] || worldState?.location || 'Неизвестно';
  const time = worldState?.time || 'Неизвестно';
  const description = worldState?.location_description || 'Описание отсутствует.';

  return (
    <div className="location-info">
      <div className="location-label">📍 Локация</div>
      <div className="location-value">{location}</div>
      <div className="location-label">🕐 Время</div>
      <div className="location-value">{time}</div>
      <div className="location-description">{description}</div>
    </div>
  );
}

export default LocationInfo;