import React, { useState, useEffect, useRef } from 'react';
import { Card, Tag, Switch, Space, Typography } from 'antd';
import { PauseCircleOutlined, PlayCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;

const levelColors = {
  ERROR: '#ff4d4f',
  WARN: '#faad14',
  INFO: '#1677ff',
  DEBUG: '#999',
};

export default function LogPanel() {
  const [lines, setLines] = useState([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState('');
  const containerRef = useRef();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/log');
        const data = await res.json();
        if (data.lines) setLines(data.lines);
      } catch {}
    };
    fetchData();
    const t = setInterval(fetchData, 3000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [lines, autoScroll]);

  const filtered = filter
    ? lines.filter(l => l.toLowerCase().includes(filter.toLowerCase()))
    : lines;

  const renderLine = (line, i) => {
    // Parse: [timestamp] [LEVEL] [service] message
    const match = line.match(/\[([^\]]+)\]\s*\[(\w+)\]\s*\[([^\]]+)\]\s*(.*)/);
    if (match) {
      const [, ts, level, service, msg] = match;
      const color = levelColors[level] || '#333';
      return (
        <div key={i} style={{ padding: '1px 0', borderBottom: '1px solid #f0f0f0', fontSize: 11, fontFamily: 'Consolas, monospace' }}>
          <span style={{ color: '#999' }}>{ts} </span>
          <span style={{ color, fontWeight: 700 }}>[{level}]</span>
          <span style={{ color: '#1677ff' }}> [{service}]</span>
          <span style={{ color: '#333' }}> {msg}</span>
        </div>
      );
    }
    return <div key={i} style={{ fontSize: 11, fontFamily: 'Consolas, monospace', color: '#333', padding: '1px 0' }}>{line}</div>;
  };

  return (
    <Card size="small">
      <Space style={{ marginBottom: 8 }}>
        <Switch checkedChildren="Auto-scroll" unCheckedChildren="Manual"
          checked={autoScroll} onChange={setAutoScroll}
          checkedChildren={<PlayCircleOutlined />} unCheckedChildren={<PauseCircleOutlined />} />
        <input placeholder="Filtrar logs..." style={{ background: '#fff', border: '1px solid #d9d9d9', color: '#333', borderRadius: 4, padding: '4px 8px', fontSize: 12, width: 300 }}
          value={filter} onChange={(e) => setFilter(e.target.value)} />
        <Tag color="blue">{filtered.length} linhas</Tag>
      </Space>
      <div ref={containerRef} className="scroll-thin"
        style={{ height: 450, overflow: 'auto', background: '#fafafa', padding: 8, borderRadius: 6, border: '1px solid #f0f0f0' }}>
        {filtered.length > 0 ? filtered.map(renderLine) : <Text type="secondary">Sem logs</Text>}
      </div>
    </Card>
  );
}
