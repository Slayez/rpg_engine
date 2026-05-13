import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import ToastProvider from './components/ToastNotifications';
import './styles/global.css';
import './styles/mobile.css';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <ToastProvider>
    <App />
  </ToastProvider>
);