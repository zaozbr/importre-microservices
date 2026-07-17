import React, { useState, useEffect, useRef } from 'react';
import { Tooltip } from 'antd';

// Sparkline inline mostrando velocidade global dos ultimos 60s
export default function SpeedSparkline() {
  const [speeds, setSpeeds] = useState([]);
  const timerRef = useRef();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/aria2', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ jsonrpc: '2.0', method: 'aria2.getGlobalStat', id: 'sp', params: ['token:devin'] }),
        });
        const json = await res.json();
        if (json.result?.downloadSpeed) {
          const bps = parseInt(json.result.downloadSpeed);
          setSpeeds(prev => {
            const next = [...prev, bps];
            if (next.length > 30) next.shift(); // 30 pontos x 2s = 60s
            return next;
          });
        }
      } catch {}
    };
    fetchData();
    timerRef.current = setInterval(fetchData, 2000);
    return () => clearInterval(timerRef.current);
  }, []);

  if (speeds.length < 2) return null;

  const max = Math.max(...speeds, 1);
  const w = 100, h = 28;
  const step = w / (speeds.length - 1);

  const points = speeds.map((s, i) => `${i * step},${h - (s / max) * h}`).join(' ');
  const areaPoints = `0,${h} ${points} ${w},${h}`;

  const currentMbps = (speeds[speeds.length - 1] / 1048576).toFixed(2);
  const avgMbps = (speeds.reduce((a, b) => a + b, 0) / speeds.length / 1048576).toFixed(2);

  return (
    <Tooltip title={`Atual: ${currentMbps} MB/s | Media 60s: ${avgMbps} MB/s`}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <svg width={w} height={h} className="sparkline" style={{ display: 'block' }}>
          <polygon points={areaPoints} fill="#1677ff" opacity={0.15} />
          <polyline points={points} fill="none" stroke="#1677ff" strokeWidth={1.5} />
        </svg>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#1677ff' }}>{currentMbps} MB/s</span>
      </div>
    </Tooltip>
  );
}
