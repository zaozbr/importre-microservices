import React, { useState, useEffect, useRef } from 'react';
import { Table, Tag, Card, Row, Col, Statistic, Progress, Empty } from 'antd';
import { ThunderboltOutlined, CheckCircleOutlined, SyncOutlined } from '@ant-design/icons';

export default function ChdPanel() {
  const [status, setStatus] = useState({});
  const timerRef = useRef();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        setStatus(data.chd || {});
      } catch {}
    };
    fetchData();
    timerRef.current = setInterval(fetchData, 5000);
    return () => clearInterval(timerRef.current);
  }, []);

  const converting = status.converting || [];
  const queue = status.queue || [];
  const completed = status.completed || 0;

  const columns = [
    { title: 'Serial', dataIndex: 'serial', key: 'serial', width: 130,
      render: (s) => <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{s}</span> },
    { title: 'Titulo', dataIndex: 'title', key: 'title', ellipsis: true },
    { title: 'Status', dataIndex: 'status', key: 'status', width: 100,
      render: (s) => {
        const colors = { converting: 'processing', queued: 'default', done: 'success', failed: 'error' };
        return <Tag color={colors[s] || 'default'}>{s}</Tag>;
      }},
    { title: 'Progresso', key: 'progress', width: 180,
      render: (_, r) => {
        const pct = r.progress || 0;
        return <Progress percent={pct} size="small" status={pct === 100 ? 'success' : 'active'} />;
      }},
    { title: 'Erro', dataIndex: 'error', key: 'error', ellipsis: true,
      render: (e) => e ? <Tag color="error">{e}</Tag> : '-' },
  ];

  const allItems = [...converting, ...queue];

  return (
    <div>
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col><Card size="small"><Statistic title="Convertendo" value={converting.length} valueStyle={{ color: '#722ed1', fontSize: 20 }} prefix={<SyncOutlined spin={converting.length > 0} />} /></Card></Col>
        <Col><Card size="small"><Statistic title="Fila CHD" value={queue.length} valueStyle={{ fontSize: 20 }} prefix={<ThunderboltOutlined />} /></Card></Col>
        <Col><Card size="small"><Statistic title="Completados" value={completed} valueStyle={{ color: '#52c41a', fontSize: 20 }} prefix={<CheckCircleOutlined />} /></Card></Col>
      </Row>
      <Table dataSource={allItems} columns={columns} rowKey="serial" size="small"
        pagination={{ pageSize: 20, size: 'small' }} scroll={{ y: 400 }}
        locale={{ emptyText: <Empty description="Nenhuma conversao CHD em andamento" /> }} />
    </div>
  );
}
