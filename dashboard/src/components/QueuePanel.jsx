import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Table, Tag, Progress, Card, Row, Col, Statistic, Input, Segmented, Space, Empty, Button, message } from 'antd';
import { ReloadOutlined, SearchOutlined, RetweetOutlined, DeleteOutlined } from '@ant-design/icons';
import ItemActions from './ItemActions.jsx';
import ItemDetailsDrawer from './ItemDetailsDrawer.jsx';
import { useItemActions } from '../hooks/useItemActions.js';

const statusColors = {
  pending: 'default', searching: 'blue', ready: 'success',
  downloading: 'processing', completed: 'success', failed: 'error', cooldown: 'warning',
};

const fmtSpeed = (bps) => {
  if (!bps) return '-';
  const mbps = bps / 1048576;
  if (mbps >= 1) return `${mbps.toFixed(2)} MB/s`;
  return `${(bps / 1024).toFixed(0)} KB/s`;
};

export default function QueuePanel() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [drawerSerial, setDrawerSerial] = useState(null);
  const timerRef = useRef();

  const refresh = useCallback(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/queue');
        const data = await res.json();
        setItems(data.queue || []);
      } catch {}
    };
    fetchData();
  }, []);

  useEffect(() => {
    refresh();
    timerRef.current = setInterval(refresh, 3000);
    return () => clearInterval(timerRef.current);
  }, [refresh]);

  const handleAction = useItemActions(refresh);

  const statusCounts = items.reduce((acc, i) => {
    acc[i.status] = (acc[i.status] || 0) + 1;
    return acc;
  }, {});

  const filtered = items.filter(i => {
    if (filter !== 'all' && i.status !== filter) return false;
    if (search) {
      const s = search.toLowerCase();
      return (i.serial || '').toLowerCase().includes(s) || (i.title || '').toLowerCase().includes(s);
    }
    return true;
  });

  // Acoes em lote
  const batchAction = async (action) => {
    if (selectedKeys.length === 0) {
      message.warning('Selecione itens primeiro');
      return;
    }
    let count = 0;
    for (const serial of selectedKeys) {
      const result = await handleAction[action]?.(serial);
      if (result) count++;
    }
    message.success(`${count} itens processados`);
    setSelectedKeys([]);
    refresh();
  };

  const columns = [
    { title: 'Serial', dataIndex: 'serial', key: 'serial', width: 130,
      sorter: (a, b) => a.serial.localeCompare(b.serial),
      render: (s) => <a onClick={() => setDrawerSerial(s)} style={{ fontFamily: 'monospace', fontSize: 11 }}>{s}</a> },
    { title: 'Título', dataIndex: 'title', key: 'title', ellipsis: true,
      sorter: (a, b) => (a.title || '').localeCompare(b.title || ''),
      render: (t, r) => t || r.serial },
    { title: 'Status', dataIndex: 'status', key: 'status', width: 100,
      sorter: (a, b) => a.status.localeCompare(b.status),
      render: (s) => <Tag color={statusColors[s] || 'default'}>{s}</Tag> },
    { title: 'Progresso', key: 'progress', width: 150,
      render: (_, r) => {
        const p = r.progress || {};
        const pct = p.percent || 0;
        if (r.status === 'downloading') return <Progress percent={pct} size="small" status="active" />;
        if (r.status === 'completed') return <Progress percent={100} size="small" status="success" />;
        return '-';
      }},
    { title: 'Download', key: 'dl', width: 85,
      render: (_, r) => r.status === 'downloading' ? <span style={{ color: '#1677ff' }}>{fmtSpeed(r.progress?.bps)}</span> : '-' },
    { title: 'Fontes', key: 'sources', width: 60,
      sorter: (a, b) => (a.sources?.length || 0) - (b.sources?.length || 0),
      render: (_, r) => (r.sources || []).length || '-' },
    { title: 'Sites', key: 'sites', ellipsis: true, width: 150,
      render: (_, r) => (r.sources || []).map((s, i) => <Tag key={i} style={{ fontSize: 10 }}>{s.site}</Tag>) },
    { title: 'Retry', dataIndex: 'retry_count', key: 'retry', width: 45,
      sorter: (a, b) => (a.retry_count || 0) - (b.retry_count || 0),
      render: (n) => n ? <Tag color={n > 2 ? 'error' : 'warning'}>{n}</Tag> : '-' },
    { title: 'Ações', key: 'actions', width: 50, fixed: 'right',
      render: (_, r) => <ItemActions serial={r.serial} status={r.status} onAction={(key, s) => handleAction[key]?.(s)} /> },
  ];

  const filters = ['all', 'pending', 'searching', 'ready', 'downloading', 'cooldown', 'completed', 'failed'];

  return (
    <div>
      <Row gutter={8} style={{ marginBottom: 12 }}>
        {filters.slice(1).map(f => (
          <Col key={f}><Card size="small"><Statistic title={f} value={statusCounts[f] || 0} valueStyle={{ fontSize: 18, color: f === 'completed' ? '#52c41a' : f === 'failed' ? '#ff4d4f' : '#333' }} /></Card></Col>
        ))}
      </Row>
      <Space style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Segmented options={filters.map(f => ({ label: f, value: f }))} value={filter}
            onChange={(v) => setFilter(v)} size="small" />
          <Input.Search placeholder="Buscar..." size="small" style={{ width: 250 }}
            onChange={(e) => setSearch(e.target.value)} allowClear />
        </Space>
        {selectedKeys.length > 0 && (
          <Space>
            <span style={{ fontSize: 12, color: '#666' }}>{selectedKeys.length} selecionados</span>
            <Button size="small" icon={<SearchOutlined />} onClick={() => batchAction('search')}>Procurar</Button>
            <Button size="small" icon={<ReloadOutlined />} onClick={() => batchAction('retry')}>Retry</Button>
            <Button size="small" icon={<RetweetOutlined />} onClick={() => batchAction('requeue')}>Requeue</Button>
            <Button size="small" type="text" icon={<DeleteOutlined />} onClick={() => setSelectedKeys([])} />
          </Space>
        )}
      </Space>
      <Table dataSource={filtered} columns={columns} rowKey="serial" size="small"
        rowSelection={{ selectedRowKeys: selectedKeys, onChange: setSelectedKeys }}
        pagination={{ pageSize: 50, size: 'small', showSizeChanger: true, pageSizeOptions: ['20', '50', '100'] }}
        scroll={{ x: 1000, y: 400 }} locale={{ emptyText: <Empty description="Fila vazia" /> }} />
      <ItemDetailsDrawer serial={drawerSerial} open={!!drawerSerial} onClose={() => setDrawerSerial(null)}
        onAction={(key, s) => handleAction[key]?.(s)} />
    </div>
  );
}
