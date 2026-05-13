// Функция подсветки игровых механик в тексте
// Возвращает строку с HTML-тегами <span> для чисел, костей, стихий, ключевых слов
export function highlightMechanics(text) {
  if (!text) return '';
  return text
    .replace(
      /(\d+[\.,]?\d*\s?(HP|MP|ОП|урона|раунд|минут|секунд|ходов|футов|метров))/gi,
      (match) => `<span class="mech-value">${match}</span>`
    )
    .replace(
      /(\d+d\d+)/gi,
      (match) => `<span class="mech-dice">${match}</span>`
    )
    .replace(
      /(\d+%)/g,
      (match) => `<span class="mech-value">${match}</span>`
    )
    .replace(
      /\b(Огонь|Вода|Земля|Воздух|Стихия|Иллюзия|Тень|Свет|Магия|Природа|Лёд|Молния|Яд|Кислота)\b/gi,
      (match) => `<span class="mech-type">${match}</span>`
    )
    .replace(
      /\b(бонус|штраф|преимущество|помеха|раунд|ход|минут|секунд|футов|метров|радиус|дальность|длительность)\b/gi,
      (match) => `<span class="mech-keyword">${match}</span>`
    );
}