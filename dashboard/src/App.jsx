import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Layout, Tabs, Button, Space, Tag, Statistic, Row, Col, message, Tooltip, Modal } from 'antd';
import {
  PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined,
  PoweroffOutlined, WarningOutlined, ThunderboltOutlined,
  DownloadOutlined, SearchOutlined, HddOutlined, FileTextOutlined,
  CloudOutlined, GlobalOutlined, PlusOutlined, SettingOutlined,
  LineChartOutlined, BellOutlined,
} from '@ant-design/icons';
import { usePoll } from './hooks/useApi.js';
import { useItemActions } from './hooks/useItemActions.js';
import DownloadsPanel from './components/DownloadsPanel.jsx';
import TorrentsPanel from './components/TorrentsPanel.jsx';
import SearchPanel from './components/SearchPanel.jsx';
import QueuePanel from './components/QueuePanel.jsx';
import ChdPanel from './components/ChdPanel.jsx';
import LogPanel from './components/LogPanel.jsx';
import SpeedSparkline from './components/SpeedSparkline.jsx';
import SpeedChartModal from './components/SpeedChartModal.jsx';
import AddDownloadModal from './components/AddDownloadModal.jsx';
import Aria2SettingsModal from './components/Aria2SettingsModal.jsx';

const { Header, Content } = Layout;

export default function App() {
  const { data: status, refresh } = usePoll('/api/status', 3000);
  const [actionLoading, setActionLoading] = useState(false);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [chartOpen, setChartOpen] = useState(false);
  const [prevCompleted, setPrevCompleted] = useState(null);
  const [notifEnabled, setNotifEnabled] = useState(() => localStorage.getItem('notifEnabled') === 'true');

  const actions = useItemActions(refresh);

  const control = useCallback(async (action) => {
    setActionLoading(true);
    try {
      const timeout = action === 'stop' || action === 'restart' ? 60000 : 15000;
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), timeout);
      const res = await fetch(`/api/control/${action}`, { signal: controller.signal });
      clearTimeout(t);
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || `HTTP ${res.status}`);
      message.success(`${action.toUpperCase()} OK`);
      refresh();
    } catch (e) {
      message.error(`Falha: ${e.name === 'AbortError' ? 'timeout' : e.message}`);
    } finally {
      setActionLoading(false);
    }
  }, [refresh]);

  const reprocessFailures = useCallback(async () => {
    try {
      const res = await fetch('/api/reprocess-failures', { method: 'POST' });
      const d = await res.json();
      if (d.ok) message.success(`${d.moved} falhas reprocessadas`);
      else message.error(`Erro: ${d.error}`);
      refresh();
    } catch (e) {
      message.error(`Falha: ${e.message}`);
    }
  }, [refresh]);

  // Notificacoes browser quando download completa
  useEffect(() => {
    const completed = status?.queue?.completed || 0;
    if (prevCompleted !== null && completed > prevCompleted && notifEnabled) {
      const diff = completed - prevCompleted;
      if (Notification.permission === 'granted') {
        new Notification('Importre — Download Completo', {
          body: `${diff} novo(s) item(ns) completado(s). Total: ${completed}`,
        });
      }
    }
    setPrevCompleted(completed);
  }, [status?.queue?.completed, prevCompleted, notifEnabled]);

  const toggleNotifications = useCallback(() => {
    if (!notifEnabled) {
      Notification.requestPermission().then(p => {
        if (p === 'granted') {
          setNotifEnabled(true);
          localStorage.setItem('notifEnabled', 'true');
          message.success('Notificações ativadas');
        } else {
          message.warning('Permissão de notificações negada');
        }
      });
    } else {
      setNotifEnabled(false);
      localStorage.setItem('notifEnabled', 'false');
      message.info('Notificações desativadas');
    }
  }, [notifEnabled]);

  // Atalhos de teclado
  useEffect(() => {
    const handler = (e) => {
      if (e.ctrlKey && e.key === 'u') {
        e.preventDefault();
        setAddModalOpen(true);
      }
      if (e.key === '/' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        const search = document.querySelector('input[placeholder*="Filtrar"], input[placeholder*="Buscar"]');
        if (search) search.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const q = status?.queue || {};
  const dl = status?.download || {};
  const sr = status?.search || {};
  const chd = status?.chd || {};
  const ctrl = status?.control || 'running';
  const allOk = !q.error && !sr.error && !dl.error && !chd.error;

  const tabItems = [
    { key: 'downloads', label: <span><DownloadOutlined /> Downloads</span>, children: <DownloadsPanel /> },
    { key: 'torrents', label: <span><CloudOutlined /> Torrents</span>, children: <TorrentsPanel /> },
    { key: 'search', label: <span><SearchOutlined /> Buscas</span>, children: <SearchPanel /> },
    { key: 'queue', label: <span><HddOutlined /> Fila</span>, children: <QueuePanel /> },
    { key: 'chd', label: <span><ThunderboltOutlined /> CHD</span>, children: <ChdPanel /> },
    { key: 'log', label: <span><FileTextOutlined /> Log</span>, children: <LogPanel /> },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        background: '#fff', borderBottom: '2px solid #1677ff',
        padding: '0 24px', height: 'auto', lineHeight: 'normal', paddingBlock: 10,
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}>
        <span style={{ fontSize: 20, fontWeight: 800, color: '#1677ff', letterSpacing: 1 }}>
          IMPORTRE v5
        </span>
        <Tag color={allOk ? 'success' : 'error'}>{allOk ? 'SERVICES ONLINE' : 'SERVICES OFFLINE'}</Tag>
        <Tag color={ctrl === 'running' ? 'success' : ctrl === 'paused' ? 'warning' : 'error'}>
          {ctrl.toUpperCase()}
        </Tag>
        <Space>
          <Button type="primary" size="small" icon={<PlayCircleOutlined />} loading={actionLoading}
            onClick={() => control('resume')}>Play</Button>
          <Button size="small" icon={<PauseCircleOutlined />} loading={actionLoading}
            onClick={() => control('pause')}>Pause</Button>
          <Button size="small" icon={<ReloadOutlined />} loading={actionLoading}
            onClick={() => control('restart')}>Restart</Button>
          <Button danger size="small" icon={<PoweroffOutlined />} loading={actionLoading}
            onClick={() => control('stop')}>Stop</Button>
          <Button size="small" icon={<WarningOutlined />} onClick={reprocessFailures}>
            Reprocessar Falhas
          </Button>
          <Button size="small" icon={<PlusOutlined />} onClick={() => setAddModalOpen(true)}>
            Adicionar
          </Button>
          <Tooltip title="Configurações aria2">
            <Button size="small" icon={<SettingOutlined />} onClick={() => setSettingsOpen(true)} />
          </Tooltip>
          <Tooltip title={notifEnabled ? 'Notificações ativas' : 'Ativar notificações'}>
            <Button size="small" icon={<BellOutlined />}
              type={notifEnabled ? 'primary' : 'default'}
              onClick={toggleNotifications} />
          </Tooltip>
        </Space>
        <span style={{ flex: 1 }} />
        <Tooltip title="Gráfico de velocidade expandido">
          <span onClick={() => setChartOpen(true)} style={{ cursor: 'pointer' }}>
            <SpeedSparkline />
          </span>
        </Tooltip>
        <Row gutter={16} style={{ gap: 4 }}>
          <Col><Statistic title="Pendentes" value={q.pending || 0} valueStyle={{ fontSize: 16, color: '#666' }} /></Col>
          <Col><Statistic title="Buscando" value={q.searching || 0} valueStyle={{ fontSize: 16, color: '#1677ff' }} /></Col>
          <Col><Statistic title="Prontos" value={q.ready || 0} valueStyle={{ fontSize: 16, color: '#52c41a' }} /></Col>
          <Col><Statistic title="Downloads" value={q.downloading || 0} valueStyle={{ fontSize: 16, color: '#722ed1' }} /></Col>
          <Col><Statistic title="OK" value={q.completed || 0} valueStyle={{ fontSize: 16, color: '#52c41a' }} /></Col>
          <Col><Statistic title="Falhas" value={q.failed || 0} valueStyle={{ fontSize: 16, color: '#ff4d4f' }} /></Col>
        </Row>
      </Header>
      <Content style={{ padding: 16 }}>
        <Tabs defaultActiveKey="downloads" items={tabItems} size="small"
          style={{ background: '#fff', padding: 12, borderRadius: 8, border: '1px solid #f0f0f0' }} />
      </Content>
      <AddDownloadModal open={addModalOpen} onClose={() => setAddModalOpen(false)} onAdd={actions} />
      <Aria2SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} actions={actions} />
      <SpeedChartModal open={chartOpen} onClose={() => setChartOpen(false)} />
    </Layout>
  );
}
