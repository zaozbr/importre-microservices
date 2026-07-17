import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Table, Progress, Tag, Statistic, Row, Col, Card, Input, Space, Empty } from 'antd';
import { DownloadOutlined, LinkOutlined } from '@ant-design/icons';
import ItemActions from './ItemActions.jsx';
import ItemDetailsDrawer from './ItemDetailsDrawer.jsx';
import { useItemActions } from '../hooks/useItemActions.js';

const fmtSpeed = (bps) => {
  if (!bps || bps === 0) return '-';
  const mbps = bps / 1048576;
  if (mbps >= 1) return `${mbps.toFixed(2)} MB/s`;
  return `${(bps / 1024).toFixed(0)} KB/s`;
};

const fmtSize = (bytes) => {
  if (!bytes) return '-';
  const mb = bytes / 1048576;
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
  return `${mb.toFixed(1)} MB`;
};

const fmtEta = (remainingBytes, bps) => {
  if (!bps || bps === 0 || !remainingBytes) return '-';
  const sec = remainingBytes / bps;
  if (sec < 60) return `${sec.toFixed(0)}s`;
  if (sec < 3600) return `${(sec / 60).toFixed(1)}m`;
  return `${(sec / 3600).toFixed(1)}h`;
};

export default function DownloadsPanel() {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState({});
  const [globalStat, setGlobalStat] = useState(null);
  const [aria2Active, setAria2Active] = useState([]);
  const [filter, setFilter] = useState('');
  const [drawerSerial, setDrawerSerial] = useState(null);
  const timerRef = useRef();

  const refresh = useCallback(() => {
    const fetchData = async () => {
      try {
        const qRes = await fetch('/api/queue');
        const qData = await qRes.json();
        const dl = (qData.queue || []).filter(i => ['downloading', 'ready', 'cooldown'].includes(i.status));
        setItems(dl);

        const sRes = await fetch('/api/status');
        const sData = await sRes.json();
        setStats(sData.download || {});

        const aRes = await fetch('/aria2', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ jsonrpc: '2.0', method: 'aria2.getGlobalStat', id: 'd', params: ['token:devin'] }),
        });
        const aData = await aRes.json();
        if (aData.result) setGlobalStat(aData.result);

        const actRes = await fetch('/aria2', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ jsonrpc: '2.0', method: 'aria2.tellActive', id: 'd', params: ['token:devin'] }),
        });
        const actData = await actRes.json();
        if (actData.result) setAria2Active(actData.result);
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

  // Merge queue items com aria2 tasks para ter dados completos
  const mergedItems = items.map(item => {
    const aria2Task = aria2Active.find(t => {
      const f = t.files?.[0];
      return f && (f.path?.includes(item.serial) || f.uris?.[0]?.uri?.includes(item.serial));
    });
    return { ...item, aria2: aria2Task };
  });

  const filtered = filter
    ? mergedItems.filter(i => (i.serial || '').toLowerCase().includes(filter.toLowerCase()) ||
                         (i.title || '').toLowerCase().includes(filter.toLowerCase()))
    : mergedItems;

  const totalSpeed = globalStat ? parseInt(globalStat.downloadSpeed) : 0;
  const totalUpload = globalStat ? parseInt(globalStat.uploadSpeed) : 0;

  const columns = [
    { title: 'Serial', dataIndex: 'serial', key: 'serial', width: 130,
      sorter: (a, b) => a.serial.localeCompare(b.serial),
      render: (s) => <a onClick={() => setDrawerSerial(s)} style={{ fontFamily: 'monospace', fontSize: 11 }}>{s}</a> },
    { title: 'Jogo', dataIndex: 'title', key: 'title', ellipsis: true,
      sorter: (a, b) => (a.title || '').localeCompare(b.title || ''),
      render: (t, r) => t || r.serial },
    { title: 'Status', dataIndex: 'status', key: 'status', width: 90,
      sorter: (a, b) => a.status.localeCompare(b.status),
      render: (s) => {
        const colors = { downloading: 'processing', ready: 'success', cooldown: 'warning' };
        return <Tag color={colors[s] || 'default'}>{s}</Tag>;
      }},
    { title: 'Fontes', key: 'sources', width: 70,
      sorter: (a, b) => (a.sources?.length || 0) - (b.sources?.length || 0),
      render: (_, r) => {
        const srcs = r.sources || [];
        if (srcs.length > 1) return <Tag color="purple"><LinkOutlined /> {srcs.length}</Tag>;
        if (srcs.length === 1) return <Tag color="blue">{srcs[0].site}</Tag>;
        return '-';
      }},
    { title: 'Progresso', key: 'progress', width: 150,
      sorter: (a, b) => (a.progress?.percent || 0) - (b.progress?.percent || 0),
      render: (_, r) => {
        const p = r.progress || {};
        const pct = p.percent || (r.aria2 ? Math.round((parseInt(r.aria2.completedLength) / parseInt(r.aria2.totalLength)) * 100) : 0);
        return <Progress percent={pct} size="small" status={pct === 100 ? 'success' : 'active'} />;
      }},
    { title: 'Download', key: 'dl', width: 90,
      render: (_, r) => {
        const speed = r.aria2 ? parseInt(r.aria2.downloadSpeed) : (r.progress?.bps || 0);
        return <span style={{ color: '#1677ff', fontWeight: 700 }}>{fmtSpeed(speed)}</span>;
      }},
    { title: 'Upload', key: 'ul', width: 80,
      render: (_, r) => r.aria2 ? fmtSpeed(parseInt(r.aria2.uploadSpeed)) : '-' },
    { title: 'ETA', key: 'eta', width: 60,
      render: (_, r) => {
        if (!r.aria2) return '-';
        const remaining = parseInt(r.aria2.totalLength) - parseInt(r.aria2.completedLength);
        return fmtEta(remaining, parseInt(r.aria2.downloadSpeed));
      }},
    { title: 'Size', key: 'size', width: 75,
      render: (_, r) => fmtSize(r.aria2 ? parseInt(r.aria2.totalLength) : r.sources?.[0]?.size) },
    { title: 'Conn', key: 'conn', width: 45,
      render: (_, r) => r.aria2?.connections || '-' },
    { title: 'Peers', key: 'peers', width: 45,
      render: (_, r) => r.aria2?.bittorrent ? (r.aria2.numPeers || 0) : '-' },
    { title: 'Retry', dataIndex: 'retry_count', key: 'retry', width: 45,
      render: (n) => n ? <Tag color={n > 2 ? 'error' : 'warning'}>{n}</Tag> : '-' },
    { title: 'Ações', key: 'actions', width: 50, fixed: 'right',
      render: (_, r) => <ItemActions serial={r.serial} status={r.status} onAction={(key, s) => handleAction[key]?.(s)} /> },
  ];

  return (
    <div>
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col><Card size="small"><Statistic title="Ativos" value={stats.active || 0} valueStyle={{ color: '#722ed1', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Download" value={fmtSpeed(totalSpeed)} valueStyle={{ color: '#1677ff', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Upload" value={fmtSpeed(totalUpload)} valueStyle={{ color: '#faad14', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Completados" value={stats.completed || 0} valueStyle={{ color: '#52c41a', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Falhas" value={stats.failed || 0} valueStyle={{ color: '#ff4d4f', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="aria2 Ativos" value={globalStat?.numActive || '-'} valueStyle={{ fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="aria2 Espera" value={globalStat?.numWaiting || '-'} valueStyle={{ fontSize: 20 }} /></Card></Col>
      </Row>
      <Space style={{ marginBottom: 8 }}>
        <Input.Search placeholder="Filtrar por serial ou título..." size="small" style={{ width: 300 }}
          onChange={(e) => setFilter(e.target.value)} allowClear />
      </Space>
      <Table dataSource={filtered} columns={columns} rowKey="serial" size="small"
        pagination={false} scroll={{ x: 1100, y: 400 }}
        locale={{ emptyText: <Empty description="Nenhum download ativo" /> }} />
      <ItemDetailsDrawer serial={drawerSerial} open={!!drawerSerial} onClose={() => setDrawerSerial(null)}
        onAction={(key, s) => handleAction[key]?.(s)} />
    </div>
  );
}
