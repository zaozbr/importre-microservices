import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Table, Tag, Card, Row, Col, Statistic, Input, Button, Space, message, Empty, Tooltip } from 'antd';
import { SearchOutlined, GlobalOutlined, CloudOutlined, GithubOutlined, ReloadOutlined } from '@ant-design/icons';
import ItemActions from './ItemActions.jsx';
import { useItemActions } from '../hooks/useItemActions.js';

const siteIcons = {
  'itch.io': <CloudOutlined />,
  'github': <GithubOutlined />,
  'google': <GlobalOutlined />,
  'archive.org': <CloudOutlined />,
};

const siteColors = {
  'itch.io': 'purple',
  'github': 'default',
  'google': 'blue',
  'archive.org': 'green',
  'archive.org-jp': 'green',
  'coolrom': 'cyan',
  'vimm': 'geekblue',
  'retrostic': 'orange',
  'romspedia': 'gold',
};

export default function SearchPanel() {
  const [plugins, setPlugins] = useState([]);
  const [queueItems, setQueueItems] = useState([]);
  const [filter, setFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const timerRef = useRef();

  const refresh = useCallback(() => {
    const fetchData = async () => {
      try {
        const sRes = await fetch('/api/status');
        const sData = await sRes.json();
        if (sData.search?.plugins) setPlugins(sData.search.plugins);

        const qRes = await fetch('/api/queue');
        const qData = await qRes.json();
        const searchingItems = (qData.queue || []).filter(i => i.status === 'searching');
        setQueueItems(searchingItems);
      } catch {}
    };
    fetchData();
  }, []);

  useEffect(() => {
    refresh();
    timerRef.current = setInterval(refresh, 5000);
    return () => clearInterval(timerRef.current);
  }, [refresh]);

  const handleAction = useItemActions(refresh);

  const doSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchResults(null);
    try {
      const qRes = await fetch('/api/queue');
      const qData = await qRes.json();
      const matches = (qData.queue || []).filter(i =>
        (i.serial || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (i.title || '').toLowerCase().includes(searchQuery.toLowerCase())
      );
      setSearchResults({ matches, total: matches.length });
    } catch (e) {
      message.error(`Busca falhou: ${e.message}`);
    } finally {
      setSearching(false);
    }
  };

  const filteredPlugins = filter
    ? plugins.filter(p => p.name.toLowerCase().includes(filter.toLowerCase()))
    : plugins;

  const pluginColumns = [
    { title: 'Plugin', dataIndex: 'name', key: 'name', width: 160,
      render: (n) => <Space><span>{siteIcons[n] || <SearchOutlined />}</span><span style={{ fontWeight: 600 }}>{n}</span></Space> },
    { title: 'Match Type', dataIndex: 'matchType', key: 'matchType', width: 100,
      render: (t) => <Tag>{t}</Tag> },
    { title: 'Prioridade', dataIndex: 'priority', key: 'priority', width: 80,
      render: (p) => <span>{p}</span> },
    { title: 'Multi-Chunk', dataIndex: 'needsMultiChunk', key: 'multiChunk', width: 90,
      render: (n) => n ? <Tag color="blue">sim</Tag> : '-' },
    { title: 'Status', dataIndex: 'enabled', key: 'enabled', width: 80,
      render: (e) => e ? <Tag color="success">ativo</Tag> : <Tag color="error">off</Tag> },
  ];

  const searchingColumns = [
    { title: 'Serial', dataIndex: 'serial', key: 'serial', width: 130,
      render: (s) => <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{s}</span> },
    { title: 'Título', dataIndex: 'title', key: 'title', ellipsis: true },
    { title: 'Tentativas', dataIndex: 'retry_count', key: 'retry', width: 80,
      render: (n) => n ? <Tag color={n > 2 ? 'error' : 'warning'}>{n}</Tag> : '-' },
    { title: 'Fontes', key: 'sources', width: 100,
      render: (_, r) => {
        const srcs = r.sources || [];
        if (srcs.length === 0) return <Tag color="warning">0 fontes</Tag>;
        return <Tag color="success">{srcs.length} fontes</Tag>;
      }},
    { title: 'Sites', key: 'sites', ellipsis: true,
      render: (_, r) => (r.sources || []).map((s, i) => <Tag key={i} color={siteColors[s.site] || 'default'} style={{ fontSize: 10 }}>{s.site}</Tag>) },
    { title: 'Ações', key: 'actions', width: 50,
      render: (_, r) => <ItemActions serial={r.serial} status={r.status} onAction={(key, s) => handleAction[key]?.(s)} /> },
  ];

  // Estatisticas por plugin
  const enabledPlugins = plugins.filter(p => p.enabled);
  const itchPlugins = plugins.filter(p => p.name.includes('itch'));
  const googlePlugins = plugins.filter(p => p.name.includes('google'));
  const archivePlugins = plugins.filter(p => p.name.includes('archive'));
  const itemsWithSources = queueItems.filter(i => (i.sources || []).length > 0);
  const itemsNoSources = queueItems.filter(i => (i.sources || []).length === 0);
  const successRate = queueItems.length > 0 ? ((itemsWithSources.length / queueItems.length) * 100).toFixed(0) : 0;

  return (
    <div>
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col><Card size="small"><Statistic title="Plugins Ativos" value={enabledPlugins.length} valueStyle={{ color: '#52c41a', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Total Plugins" value={plugins.length} valueStyle={{ fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Buscando" value={queueItems.length} valueStyle={{ color: '#1677ff', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="itch.io" value={itchPlugins.length} valueStyle={{ color: '#722ed1', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Google" value={googlePlugins.length} valueStyle={{ color: '#1677ff', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Archive.org" value={archivePlugins.length} valueStyle={{ color: '#52c41a', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Taxa Sucesso" value={`${successRate}%`} valueStyle={{ color: successRate > 50 ? '#52c41a' : '#faad14', fontSize: 20 }} /></Card></Col>
      </Row>

      <Card title="Buscar na fila" size="small" style={{ marginBottom: 12 }}>
        <Space>
          <Input.Search placeholder="Serial ou título..." size="small" style={{ width: 350 }}
            value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            onSearch={doSearch} loading={searching} enterButton />
          {searchResults && (
            <Tag color={searchResults.total > 0 ? 'success' : 'warning'}>
              {searchResults.total} resultado(s)
            </Tag>
          )}
        </Space>
        {searchResults?.matches?.length > 0 && (
          <Table dataSource={searchResults.matches} columns={searchingColumns} rowKey="serial"
            size="small" pagination={{ pageSize: 10 }} style={{ marginTop: 8 }} />
        )}
      </Card>

      <Card title="Itens Buscando Agora" size="small" style={{ marginBottom: 12 }}>
        <Table dataSource={queueItems} columns={searchingColumns} rowKey="serial"
          size="small" pagination={{ pageSize: 10 }} scroll={{ y: 200 }}
          locale={{ emptyText: <Empty description="Nenhum item buscando" /> }} />
      </Card>

      <Card title="Plugins de Busca" size="small"
        extra={<Input placeholder="Filtrar plugins..." size="small" style={{ width: 200 }}
          onChange={(e) => setFilter(e.target.value)} allowClear />}>
        <Table dataSource={filteredPlugins} columns={pluginColumns} rowKey="name"
          size="small" pagination={false} scroll={{ y: 300 }} />
      </Card>
    </div>
  );
}
