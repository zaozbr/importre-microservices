import React from 'react';
import { Dropdown, Button, Space, message } from 'antd';
import {
  SearchOutlined, ReloadOutlined, RetweetOutlined, LinkOutlined,
  StopOutlined, MoreOutlined, DownloadOutlined,
} from '@ant-design/icons';

// Menu de acoes por item, dependendo do status
export default function ItemActions({ serial, status, onAction, size = 'small' }) {
  const handle = (key) => async () => {
    if (onAction) await onAction(key, serial);
  };

  const items = [];

  // Acoes comuns a quase todos
  if (status !== 'completed' && status !== 'downloading') {
    items.push({ key: 'search', label: 'Procurar novamente', icon: <SearchOutlined /> });
  }
  if (status === 'failed' || status === 'cooldown' || status === 'completed') {
    items.push({ key: 'retry', label: 'Tentar novamente', icon: <ReloadOutlined /> });
  }
  if (status === 'ready' || status === 'searching' || status === 'cooldown') {
    items.push({ key: 'multisource', label: 'Multi-source forçado', icon: <LinkOutlined /> });
  }
  if (status === 'downloading' || status === 'ready') {
    items.push({ key: 'cancel', label: 'Cancelar download', icon: <StopOutlined />, danger: true });
  }
  if (status === 'downloading' || status === 'ready' || status === 'searching') {
    items.push({ key: 'requeue', label: 'Requeue (cooldown)', icon: <RetweetOutlined /> });
  }

  if (items.length === 0) return null;

  const menuProps = { items, onClick: ({ key }) => handle(key)() };

  return (
    <Dropdown menu={menuProps} trigger={['click']}>
      <Button size={size} type="text" icon={<MoreOutlined />} />
    </Dropdown>
  );
}
