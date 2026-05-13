import React from 'react';
import { Toaster, toast } from 'react-hot-toast';

export const ToastProvider = ({ children }) => (
  <>
    <Toaster position="top-right" gutter={8} />
    {children}
  </>
);

export const notify = {
  success: (msg) => toast.success(msg),
  error: (msg) => toast.error(msg),
  loading: (msg) => toast.loading(msg),
  info: (msg) => toast(msg, { icon: 'ℹ️' }),
  networkError: () => toast.error('⚠️ Ошибка сети. Проверьте соединение.'),
  saveSuccess: () => toast.success('💾 Игра сохранена'),
  saveError: (e) => toast.error(`Ошибка сохранения: ${e}`)
};

export default ToastProvider;
