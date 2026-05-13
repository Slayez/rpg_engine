import random
import re
from typing import Tuple

def roll_dice(formula: str) -> Tuple[int, str]:
    """
    Бросает кубы по формуле вида '2d6', '3d8+2', '120%', '5'.
    Возвращает (итоговое_число, комментарий_для_нарратива).
    """
    formula = formula.strip().lower()
    match = re.fullmatch(r'(\d+)d(\d+)([+-]\d+)?', formula)
    if match:
        count = int(match.group(1))
        sides = int(match.group(2))
        bonus = int(match.group(3)) if match.group(3) else 0
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + bonus
        comment = f"{' + '.join(map(str, rolls))}" + (f" {bonus:+d}" if bonus else "")
        return total, comment
    try:
        return int(formula), formula
    except ValueError:
        return 0, formula

def calculate_damage(damage_str: str, attacker_stats: dict) -> Tuple[int, str, str]:
    """
    Вычисляет урон, поддерживая формулы:
    - '2d6', '3d8+2'
    - '120% магической атаки' (процент от intelligence)
    Возвращает (урон, комментарий, тип_урона).
    """
    damage_str = damage_str.strip()
    percent_match = re.match(r'(\d+)%\s*(.+)', damage_str)
    if percent_match:
        percent = int(percent_match.group(1))
        stat_name = percent_match.group(2).strip().lower()
        stat_map = {
            'маг. атаки': 'intelligence',
            'силы': 'strength',
            'ловкости': 'dexterity',
            'intelligence': 'intelligence',
            'strength': 'strength',
            'dexterity': 'dexterity',
        }
        stat = stat_map.get(stat_name, 'intelligence')
        base = attacker_stats.get(stat, 10)
        dmg = int(base * percent / 100)
        return dmg, f"{percent}% от {stat_name} = {dmg}", "magical"
    dmg, comment = roll_dice(damage_str)
    return dmg, comment, "physical"