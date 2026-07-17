import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, theme } from 'antd';
import ptBR from 'antd/locale/pt_BR';
import App from './App.jsx';
import './index.css';

const lightTheme = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#1677ff',
    colorBgBase: '#f5f5f5',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBorder: '#d9d9d9',
    colorBorderSecondary: '#f0f0f0',
    colorText: '#333333',
    colorTextSecondary: '#666666',
    colorTextTertiary: '#999999',
    colorError: '#ff4d4f',
    colorSuccess: '#52c41a',
    colorWarning: '#faad14',
    colorInfo: '#1677ff',
    borderRadius: 6,
    fontSize: 12,
    controlHeight: 28,
  },
  components: {
    Table: {
      headerBg: '#fafafa',
      headerColor: '#333',
      rowHoverBg: '#f5f5f5',
      borderColor: '#f0f0f0',
    },
    Card: {
      headerBg: '#fafafa',
      headerFontSize: 13,
    },
    Layout: {
      headerBg: '#ffffff',
      headerHeight: 56,
      bodyBg: '#f5f5f5',
    },
    Tabs: {
      itemColor: '#666',
      itemSelectedColor: '#1677ff',
      inkBarColor: '#1677ff',
    },
    Tag: {
      defaultBg: '#f5f5f5',
    },
  },
};

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ConfigProvider locale={ptBR} theme={lightTheme}>
      <App />
    </ConfigProvider>
  </React.StrictMode>
);
