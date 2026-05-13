import { useState } from 'react';

export function useSystemMessages() {
  const [chatBorderAnim, setChatBorderAnim] = useState('');
  const applyBorderAnimation = (sysMsgs) => {
    if (!sysMsgs.length) return;
    const priority = ['level-up','hp-damage','hp-heal','exp-gain','mp-heal','mp-damage','item-appear','skill-appear'];
    for (const type of priority) {
      if (sysMsgs.some(m => m.type === type)) {
        setChatBorderAnim(`glow-${type}`);
        setTimeout(() => setChatBorderAnim(''), 2000);
        break;
      }
    }
  };
  return { chatBorderAnim, applyBorderAnimation };
}