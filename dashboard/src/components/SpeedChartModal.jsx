import React, { useState, useEffect, useRef } from 'react';
import { Modal, Row, Col, Statistic, Card } from 'antd';

const fmtSpeed = (bps) => {
  if (!bps) return '-';
  const mbps = bps / 1048576;
  if (mbps >= 1) return `${mbps.toFixed(2)} MB/s`;
  return `${(bps / 1024).toFixed(0)} KB/s`;
};

export default function SpeedChartModal({ open, onClose }) {
  const [speeds, setSpeeds] = useState([]);
  const [uploads, setUploads] = useState([]);
  const [globalStat, setGlobalStat] = useState(null);
  const timerRef = useRef();

  useEffect(() => {
    if (!open) return;
    const fetchData = async () => {
      try {
        const res = await fetch('/aria2', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ jsonrpc: '2.0', method: 'aria2.getGlobalStat', id: 'chart', params: ['token:devin'] }),
        });
        const json = await res.json();
        if (json.result) {
          setGlobalStat(json.result);
          setSpeeds(prev => {
            const next = [...prev, parseInt(json.result.downloadSpeed)];
            if (next.length > 60) next.shift();
            return next;
          });
          setUploads(prev => {
            const next = [...prev, parseInt(json.result.uploadSpeed)];
            if (next.length > 60) next.shift();
            return next;
          });
        }
      } catch {}
    };
    fetchData();
    timerRef.current = setInterval(fetchData, 1000);
    return () => clearInterval(timerRef.current);
  }, [open]);

  const renderChart = (data, color, label) => {
    if (data.length < 2) return null;
    const max = Math.max(...data, 1);
    const w = 600, h = 200;
    const step = w / (data.length - 1);
    const points = data.map((s, i) => `${i * step},${h - (s / max) * h}`).join(' ');
    const areaPoints = `0,${h} ${points} ${w},${h}`;
    return (
      <svg width={w} height={h} style={{ display: 'block', background: '#fafafa', borderRadius: 6, border: '1px solid #f0f0f0' }}>
        <polygon points={areaPoints} fill={color} opacity={0.15} />
        <polyline points={points} fill="none" stroke={color} strokeWidth={2} />
        {data.map((s, i) => i % 10 === 0 && (
          <text key={i} x={i * step} y={h - 4} fontSize={9} fill="#999">
            {fmtSpeed(s)}
          </text>
        ))}
      </svg>
    );
  };

  const currentDl = speeds.length > 0 ? speeds[speeds.length - 1] : 0;
  const currentUl = uploads.length > 0 ? uploads[uploads.length - 1] : 0;
  const avgDl = speeds.length > 0 ? speeds.reduce((a, b) => a + b, 0) / speeds.length : 0;
  const maxDl = speeds.length > 0 ? Math.max(...speeds) : 0;

  return (
    <Modal title="Gráfico de Velocidade" open={open} onCancel={onClose}
      footer={null} width={700}>
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col><Card size="small"><Statistic title="Download Atual" value={fmtSpeed(currentDl)} valueStyle={{ color: '#1677ff', fontSize: 18 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Upload Atual" value={fmtSpeed(currentUl)} valueStyle={{ color: '#faad14', fontSize: 18 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Média Download" value={fmtSpeed(avgDl)} valueStyle={{ fontSize: 18 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Pico Download" value={fmtSpeed(maxDl)} valueStyle={{ color: '#52c41a', fontSize: 18 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Ativos" value={globalStat?.numActive || '-'} valueStyle={{ fontSize: 18 }} /></Card></Col>
        <Col><Card size="small"><Statistic title="Esperando" value={globalStat?.numWaiting || '-'} valueStyle={{ fontSize: 18 }} /></Card></Col>
      </Row>
      <div style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 8 }}>Download Speed</h4>
        {renderChart(speeds, '#1677ff', 'Download')}
      </div>
      <div>
        <h4 style={{ marginBottom: 8 }}>Upload Speed</h4>
        {renderChart(uploads, '#faad14', 'Upload')}
      </div>
    </Modal>
  );
}
