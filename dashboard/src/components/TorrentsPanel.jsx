import React, { useState, useEffect, useRef } from 'react';
import { Table, Tag, Statistic, Row, Col, Card, Progress, Empty, Button, Space, message } from 'antd';
import { CloudOutlined, DeleteOutlined, PauseOutlined, CaretRightOutlined } from '@ant-design/icons';

const fmtSpeed = (bps) => {
  if (!bps) return '-';
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

const fmtEta = (remaining, bps) => {
  if (!bps || bps === 0) return '-';
  const sec = remaining / bps;
  if (sec < 60) return `${sec.toFixed(0)}s`;
  if (sec < 3600) return `${(sec / 60).toFixed(1)}m`;
  return `${(sec / 3600).toFixed(1)}h`;
};

export default function TorrentsPanel() {
  const [active, setActive] = useState([]);
  const [waiting, setWaiting] = useState([]);
  const [stopped, setStopped] = useState([]);
  const [globalStat, setGlobalStat] = useState(null);
  const timerRef = useRef();

  const aria2Call = async (method, params = []) => {
    const res = await fetch('/aria2', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', method: `aria2.${method}`, id: 't', params: ['token:devin', ...params] }),
    });
    const json = await res.json();
    return json.result;
  };

  const fetchData = async () => {
    try {
      const [a, w, s, g] = await Promise.all([
        aria2Call('tellActive'),
        aria2Call('tellWaiting', [0, 50]),
        aria2Call('tellStopped', [0, 50]),
        aria2Call('getGlobalStat'),
      ]);
      setActive(a || []);
      setWaiting(w || []);
      setStopped(s || []);
      setGlobalStat(g);
    } catch {}
  };

  useEffect(() => {
    fetchData();
    timerRef.current = setInterval(fetchData, 4000);
    return () => clearInterval(timerRef.current);
  }, []);

  const removeTask = async (gid) => {
    try { await aria2Call('removeResult', [gid]); message.success('Task removida'); fetchData(); }
    catch (e) { message.error(e.message); }
  };

  const pauseTask = async (gid) => {
    try { await aria2Call('pause', [gid]); message.success('Pausado'); fetchData(); }
    catch (e) { message.error(e.message); }
  };

  const unpauseTask = async (gid) => {
    try { await aria2Call('unpause', [gid]); message.success('Resumido'); fetchData(); }
    catch (e) { message.error(e.message); }
  };

  const allTasks = [...active, ...waiting, ...stopped];
  const btTasks = allTasks.filter(t => t.bittorrent);
  const httpTasks = allTasks.filter(t => !t.bittorrent);

  const columns = [
    { title: 'GID', dataIndex: 'gid', key: 'gid', width: 70,
      render: (g) => <span style={{ fontFamily: 'monospace', fontSize: 10 }}>{g?.substring(0, 10)}</span> },
    { title: 'Tipo', key: 'type', width: 55,
      render: (_, r) => r.bittorrent ? <Tag color="blue">BT</Tag> : <Tag color="green">HTTP</Tag> },
    { title: 'Nome', key: 'name', ellipsis: true,
      sorter: (a, b) => {
        const na = a.bittorrent?.info?.name || a.files?.[0]?.path || '';
        const nb = b.bittorrent?.info?.name || b.files?.[0]?.path || '';
        return na.localeCompare(nb);
      },
      render: (_, r) => {
        if (r.bittorrent?.info?.name) return r.bittorrent.info.name;
        const f = r.files?.[0];
        if (f?.path) return f.path.replace(/\\/g, '/').split('/').pop();
        if (r.files?.[0]?.uris?.[0]?.uri) return r.files[0].uris[0].uri.substring(0, 60);
        return '-';
      }},
    { title: 'Status', dataIndex: 'status', key: 'status', width: 85,
      render: (s) => {
        const colors = { active: 'processing', waiting: 'warning', paused: 'default', complete: 'success', error: 'error', removed: 'default' };
        return <Tag color={colors[s] || 'default'}>{s}</Tag>;
      }},
    { title: 'Progresso', key: 'progress', width: 140,
      sorter: (a, b) => {
        const pa = a.totalLength > 0 ? a.completedLength / a.totalLength : 0;
        const pb = b.totalLength > 0 ? b.completedLength / b.totalLength : 0;
        return pa - pb;
      },
      render: (_, r) => {
        const total = parseInt(r.totalLength || 0);
        const completed = parseInt(r.completedLength || 0);
        const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
        return <Progress percent={pct} size="small" status={pct === 100 ? 'success' : 'active'} />;
      }},
    { title: 'Download', key: 'dl', width: 90,
      sorter: (a, b) => parseInt(a.downloadSpeed) - parseInt(b.downloadSpeed),
      render: (_, r) => <span style={{ color: '#1677ff', fontWeight: 700 }}>{fmtSpeed(parseInt(r.downloadSpeed))}</span> },
    { title: 'Upload', key: 'ul', width: 80,
      render: (_, r) => <span style={{ color: '#faad14' }}>{fmtSpeed(parseInt(r.uploadSpeed))}</span> },
    { title: 'ETA', key: 'eta', width: 55,
      render: (_, r) => {
        const remaining = parseInt(r.totalLength) - parseInt(r.completedLength);
        return fmtEta(remaining, parseInt(r.downloadSpeed));
      }},
    { title: 'Size', key: 'size', width: 75,
      sorter: (a, b) => parseInt(a.totalLength) - parseInt(b.totalLength),
      render: (_, r) => fmtSize(parseInt(r.totalLength)) },
    { title: 'Conn', dataIndex: 'connections', key: 'conn', width: 45 },
    { title: 'Peers', key: 'peers', width: 45,
      render: (_, r) => r.bittorrent ? (r.numPeers || 0) : '-' },
    { title: 'Seeders', key: 'seeders', width: 50,
      render: (_, r) => r.bittorrent ? (r.numSeeders || 0) : '-' },
    { title: 'Ratio', key: 'ratio', width: 50,
      render: (_, r) => {
        if (!r.bittorrent || !r.totalLength) return '-';
        const ratio = parseInt(r.uploadLength) / parseInt(r.totalLength);
        return ratio.toFixed(2);
      }},
    { title: 'Ações', key: 'actions', width: 80, fixed: 'right',
      render: (_, r) => (
        <Space size="small">
          {r.status === 'active' && <Button size="small" type="text" icon={<PauseOutlined />} onClick={() => pauseTask(r.gid)} />}
          {r.status === 'paused' && <Button size="small" type="text" icon={<CaretRightOutlined />} onClick={() => unpauseTask(r.gid)} />}
          {(r.status === 'complete' || r.status === 'error') &&
            <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => removeTask(r.gid)} />}
        </Space>
      )},
  ];

  return (
    <div>
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col><Card size="small"><Statistic title="BT Ativos" value={btTasks.filter(t => t.status === 'active').length} valueStyle={{ color: '#1677ff', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="HTTP Ativos" value={httpTasks.filter(t => t.status === 'active').length} valueStyle={{ color: '#52c41a', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Download" value={fmtSpeed(parseInt(globalStat?.downloadSpeed || 0))} valueStyle={{ color: '#1677ff', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Upload" value={fmtSpeed(parseInt(globalStat?.uploadSpeed || 0))} valueStyle={{ color: '#faad14', fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Esperando" value={globalStat?.numWaiting || 0} valueStyle={{ fontSize: 20 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Parados" value={globalStat?.numStopped || 0} valueStyle={{ fontSize: 20 }} /></Card></Col>
      </Row>
      <Table dataSource={allTasks} columns={columns} rowKey="gid" size="small"
        pagination={{ pageSize: 20, size: 'small', showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }}
        scroll={{ x: 1200, y: 400 }}
        locale={{ emptyText: <Empty description="Nenhum torrent ou download no aria2" /> }} />
    </div>
  );
}
