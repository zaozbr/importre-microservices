import React, { useState } from 'react';
import { Modal, Input, Form, Tabs, message, Button, Space } from 'antd';
import { LinkOutlined, CloudOutlined } from '@ant-design/icons';

const { TextArea } = Input;

export default function AddDownloadModal({ open, onClose, onAdd }) {
  const [form] = Form.useForm();
  const [activeTab, setActiveTab] = useState('uri');
  const [loading, setLoading] = useState(false);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      if (activeTab === 'uri') {
        const uris = values.uris.split('\n').map(u => u.trim()).filter(Boolean);
        const options = {};
        if (values.out) options.out = values.out;
        if (values.dir) options.dir = values.dir;
        const result = await onAdd.aria2AddUri(uris, options);
        if (result) {
          message.success(`Download adicionado: ${result.gid}`);
          form.resetFields();
          onClose();
        }
      } else if (activeTab === 'torrent') {
        const result = await onAdd.aria2AddTorrent(values.torrent, {});
        if (result) {
          message.success(`Torrent adicionado: ${result.gid}`);
          form.resetFields();
          onClose();
        }
      }
    } catch (e) {
      if (e.errorFields) return; // validation error
      message.error(`Erro: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'uri',
      label: <span><LinkOutlined /> URL</span>,
      children: (
        <Form form={form} layout="vertical">
          <Form.Item name="uris" label="URLs (uma por linha)" rules={[{ required: true, message: 'Digite pelo menos uma URL' }]}>
            <TextArea rows={4} placeholder="https://example.com/file.zip&#10;https://mirror.com/file.zip" />
          </Form.Item>
          <Form.Item name="out" label="Nome do arquivo (opcional)">
            <Input placeholder="file.zip" />
          </Form.Item>
          <Form.Item name="dir" label="Diretório (opcional)">
            <Input placeholder="F:\downloads" />
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'torrent',
      label: <span><CloudOutlined /> Torrent</span>,
      children: (
        <Form form={form} layout="vertical">
          <Form.Item name="torrent" label="Base64 do .torrent ou magnet link" rules={[{ required: true, message: 'Digite o torrent ou magnet' }]}>
            <TextArea rows={4} placeholder="magnet:?xt=urn:btih:..." />
          </Form.Item>
        </Form>
      ),
    },
  ];

  return (
    <Modal title="Adicionar Download" open={open} onCancel={onClose}
      onOk={handleOk} confirmLoading={loading} okText="Adicionar" cancelText="Cancelar"
      width={600}>
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} size="small" />
    </Modal>
  );
}
