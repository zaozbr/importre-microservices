import React, { useState, useEffect } from 'react';
import { Drawer, Descriptions, Tag, Table, Timeline, Space, Button, Empty, Divider, Typography, Tabs, InputNumber, Form, message } from 'antd';
import { SearchOutlined, ReloadOutlined, LinkOutlined, StopOutlined, RetweetOutlined, SettingOutlined } from '@ant-design/icons';

const { Text } = Typography;

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

const statusColors = {
  pending: 'default', searching: 'blue', ready: 'success',
  downloading: 'processing', completed: 'success', failed: 'error', cooldown: 'warning',
};

export default function ItemDetailsDrawer({ serial, open, onClose, onAction }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [peers, setPeers] = useState([]);
  const [files, setFiles] = useState([]);
  const [servers, setServers] = useState([]);
  const [taskOption, setTaskOption] = useState(null);
  const [activeTab, setActiveTab] = useState('info');

  useEffect(() => {
    if (!serial || !open) return;
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/item/${serial}/details`);
        const json = await res.json();
        setData(json);

        // Buscar dados aria2 estendidos para o primeiro task
        const gid = json.aria2Tasks?.[0]?.gid;
        if (gid) {
          try {
            const [peersRes, filesRes, serversRes, optRes] = await Promise.all([
              fetch(`/api/aria2/peers/${gid}`).then(r => r.json()),
              fetch(`/api/aria2/files/${gid}`).then(r => r.json()),
              fetch(`/api/aria2/servers/${gid}`).then(r => r.json()),
              fetch(`/api/aria2/option/${gid}`).then(r => r.json()),
            ]);
            setPeers(peersRes.peers || []);
            setFiles(filesRes.files || []);
            setServers(serversRes.servers || []);
            setTaskOption(optRes.option || null);
          } catch {}
        }
      } catch {}
      setLoading(false);
    };
    fetchData();
    const t = setInterval(fetchData, 5000);
    return () => clearInterval(t);
  }, [serial, open]);

  const item = data?.item;
  const aria2Tasks = data?.aria2Tasks || [];

  const handleAction = async (key) => {
    if (onAction) await onAction(key, serial);
    setTimeout(() => {
      const fetchData = async () => {
        try {
          const res = await fetch(`/api/item/${serial}/details`);
          const json = await res.json();
          setData(json);
        } catch {}
      };
      fetchData();
    }, 1000);
  };

  const sourceColumns = [
    { title: 'Site', dataIndex: 'site', key: 'site', width: 120,
      render: (s) => <Tag color="blue">{s}</Tag> },
    { title: 'URL', dataIndex: 'url', key: 'url', ellipsis: true,
      render: (u) => <Text copyable style={{ fontSize: 11 }}>{u}</Text> },
    { title: 'Size', dataIndex: 'size', key: 'size', width: 80,
      render: (s) => fmtSize(s) },
    { title: 'Type', dataIndex: 'type', key: 'type', width: 70,
      render: (t) => <Tag>{t || 'http'}</Tag> },
  ];

  const aria2Columns = [
    { title: 'GID', dataIndex: 'gid', key: 'gid', width: 80,
      render: (g) => <Text code style={{ fontSize: 10 }}>{g?.substring(0, 10)}</Text> },
    { title: 'Status', dataIndex: 'status', key: 'status', width: 90,
      render: (s) => <Tag color={s === 'active' ? 'processing' : s === 'complete' ? 'success' : 'default'}>{s}</Tag> },
    { title: 'Progresso', key: 'progress', width: 120,
      render: (_, r) => {
        const pct = r.totalLength > 0 ? Math.round((r.completedLength / r.totalLength) * 100) : 0;
        return `${pct}%`;
      }},
    { title: 'Download', key: 'dl', width: 90,
      render: (_, r) => fmtSpeed(parseInt(r.downloadSpeed)) },
    { title: 'Upload', key: 'ul', width: 90,
      render: (_, r) => fmtSpeed(parseInt(r.uploadSpeed)) },
    { title: 'Peers', key: 'peers', width: 50,
      render: (_, r) => r.bittorrent ? (r.numPeers || 0) : '-' },
    { title: 'Conexões', dataIndex: 'connections', key: 'conn', width: 70 },
  ];

  const peerColumns = [
    { title: 'IP', dataIndex: 'ip', key: 'ip', width: 140,
      render: (ip, r) => `${ip}:${r.port}` },
    { title: 'Client', dataIndex: 'peerId', key: 'client', ellipsis: true,
      render: (pid) => pid ? pid.substring(0, 20) : '-' },
    { title: 'Status', dataIndex: 'bitfield', key: 'status', width: 80,
      render: (bf) => bf ? <Tag color="success">ativo</Tag> : <Tag>conectado</Tag> },
    { title: 'Download', key: 'dl', width: 90,
      render: (_, r) => fmtSpeed(parseInt(r.downloadSpeed)) },
    { title: 'Upload', key: 'ul', width: 90,
      render: (_, r) => fmtSpeed(parseInt(r.uploadSpeed)) },
    { title: 'Seeder', dataIndex: 'seeder', key: 'seeder', width: 60,
      render: (s) => s ? <Tag color="green">sim</Tag> : '-' },
  ];

  const fileColumns = [
    { title: 'Index', dataIndex: 'index', key: 'index', width: 50 },
    { title: 'Caminho', dataIndex: 'path', key: 'path', ellipsis: true,
      render: (p) => p ? p.replace(/\\/g, '/').split('/').pop() : '-' },
    { title: 'Size', key: 'size', width: 80,
      render: (_, r) => fmtSize(parseInt(r.length)) },
    { title: 'Progresso', key: 'progress', width: 100,
      render: (_, r) => {
        const pct = r.length > 0 ? Math.round((r.completedLength / r.length) * 100) : 0;
        return `${pct}%`;
      }},
    { title: 'Selecionado', dataIndex: 'selected', key: 'selected', width: 80,
      render: (s) => s ? <Tag color="success">sim</Tag> : <Tag>não</Tag> },
  ];

  const serverColumns = [
    { title: 'Servidor', dataIndex: 'host', key: 'host', width: 140,
      render: (h, r) => `${h}:${r.port}` },
    { title: 'Status', dataIndex: 'currentStatus', key: 'status', width: 80,
      render: (s) => <Tag color={s === 'OK' ? 'success' : 'warning'}>{s}</Tag> },
    { title: 'Download', key: 'dl', width: 90,
      render: (_, r) => fmtSpeed(parseInt(r.downloadSpeed)) },
    { title: 'Conexões', key: 'conn', width: 70,
      render: (_, r) => r.currentUri || '-' },
  ];

  const tabItems = [
    {
      key: 'info',
      label: 'Informações',
      children: item && (
        <>
          <Space wrap style={{ marginBottom: 16 }}>
            <Tag color={statusColors[item.status]}>{item.status}</Tag>
            {item.force_multisource && <Tag color="purple">multi-source forçado</Tag>}
            {item.retry_count > 0 && <Tag color="orange">{item.retry_count} retries</Tag>}
          </Space>

          <Space wrap style={{ marginBottom: 16 }}>
            <Button size="small" icon={<SearchOutlined />} onClick={() => handleAction('search')}>Procurar novamente</Button>
            <Button size="small" icon={<ReloadOutlined />} onClick={() => handleAction('retry')}>Tentar novamente</Button>
            <Button size="small" icon={<LinkOutlined />} onClick={() => handleAction('multisource')}>Multi-source</Button>
            <Button size="small" icon={<RetweetOutlined />} onClick={() => handleAction('requeue')}>Requeue</Button>
            {(item.status === 'downloading' || item.status === 'ready') && (
              <Button size="small" danger icon={<StopOutlined />} onClick={() => handleAction('cancel')}>Cancelar</Button>
            )}
          </Space>

          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="Serial">{item.serial}</Descriptions.Item>
            <Descriptions.Item label="Título">{item.title || '-'}</Descriptions.Item>
            <Descriptions.Item label="Status">{item.status}</Descriptions.Item>
            <Descriptions.Item label="Retry Count">{item.retry_count || 0}</Descriptions.Item>
            <Descriptions.Item label="Progresso">{item.progress?.percent || 0}%</Descriptions.Item>
            <Descriptions.Item label="Velocidade">{fmtSpeed(item.progress?.bps)}</Descriptions.Item>
            <Descriptions.Item label="Fontes">{(item.sources || []).length}</Descriptions.Item>
            <Descriptions.Item label="Última tentativa">{item.last_retry || '-'}</Descriptions.Item>
          </Descriptions>

          <Divider orientation="left" plain>Fontes Encontradas</Divider>
          <Table dataSource={item.sources || []} columns={sourceColumns} rowKey={(r, i) => i}
            size="small" pagination={false} scroll={{ y: 150 }}
            locale={{ emptyText: <Empty description="Nenhuma fonte encontrada" /> }} />
        </>
      ),
    },
    {
      key: 'aria2',
      label: 'Tasks aria2',
      children: (
        <Table dataSource={aria2Tasks} columns={aria2Columns} rowKey="gid"
          size="small" pagination={false} scroll={{ y: 300 }}
          locale={{ emptyText: <Empty description="Nenhum task aria2" /> }} />
      ),
    },
    {
      key: 'peers',
      label: 'Peers BT',
      children: (
        <Table dataSource={peers} columns={peerColumns} rowKey={(r, i) => r.ip + i}
          size="small" pagination={false} scroll={{ y: 300 }}
          locale={{ emptyText: <Empty description="Nenhum peer conectado" /> }} />
      ),
    },
    {
      key: 'files',
      label: 'Arquivos',
      children: (
        <Table dataSource={files} columns={fileColumns} rowKey="index"
          size="small" pagination={false} scroll={{ y: 300 }}
          locale={{ emptyText: <Empty description="Nenhum arquivo" /> }} />
      ),
    },
    {
      key: 'servers',
      label: 'Servidores',
      children: (
        <Table dataSource={servers} columns={serverColumns} rowKey={(r, i) => r.host + i}
          size="small" pagination={false} scroll={{ y: 300 }}
          locale={{ emptyText: <Empty description="Nenhum servidor conectado" /> }} />
      ),
    },
    {
      key: 'options',
      label: 'Opções',
      children: taskOption && (
        <Descriptions column={1} size="small" bordered>
          {Object.entries(taskOption).slice(0, 30).map(([k, v]) => (
            <Descriptions.Item key={k} label={k}>{v}</Descriptions.Item>
          ))}
        </Descriptions>
      ),
    },
  ];

  return (
    <Drawer
      title={serial ? `Detalhes: ${item?.title || serial}` : 'Detalhes'}
      open={open}
      onClose={onClose}
      width={720}
      loading={loading}
    >
      {item && (
        <Tabs items={tabItems} size="small" activeKey={activeTab} onChange={setActiveTab} />
      )}
    </Drawer>
  );
}
