import React, { useState, useEffect } from 'react';
import { Modal, Form, InputNumber, Input, Switch, Slider, message, Tabs, Divider } from 'antd';

export default function Aria2SettingsModal({ open, onClose, actions }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState(null);

  useEffect(() => {
    if (open && actions) {
      const fetchOpts = async () => {
        const result = await actions.aria2GetGlobalOption();
        if (result?.option) setOptions(result.option);
      };
      fetchOpts();
    }
  }, [open, actions]);

  useEffect(() => {
    if (options) {
      form.setFieldsValue({
        'max-concurrent-downloads': parseInt(options['max-concurrent-downloads'] || '5'),
        'max-connection-per-server': parseInt(options['max-connection-per-server'] || '1'),
        'split': parseInt(options['split'] || '5'),
        'min-split-size': options['min-split-size'] || '20M',
        'max-overall-download-limit': options['max-overall-download-limit'] || '0',
        'max-overall-upload-limit': options['max-overall-upload-limit'] || '0',
        'max-download-limit': options['max-download-limit'] || '0',
        'max-upload-limit': options['max-upload-limit'] || '0',
        'seed-ratio': parseFloat(options['seed-ratio'] || '0'),
        'seed-time': parseInt(options['seed-time'] || '0'),
        'bt-request-peer-speed-limit': options['bt-request-peer-speed-limit'] || '2M',
        'bt-max-peers': parseInt(options['bt-max-peers'] || '55'),
        'continue': options['continue'] === 'true',
        'file-allocation': options['file-allocation'] || 'prealloc',
        'dir': options['dir'] || '',
      });
    }
  }, [options, form]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const opts = {};
      for (const [key, val] of Object.entries(values)) {
        if (val !== undefined && val !== null) {
          opts[key] = typeof val === 'boolean' ? (val ? 'true' : 'false') : String(val);
        }
      }
      const result = await actions.aria2ChangeGlobalOption(opts);
      if (result) {
        message.success('Configurações salvas');
        onClose();
      }
    } catch (e) {
      if (e.errorFields) return;
      message.error(`Erro: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'download',
      label: 'Download',
      children: (
        <>
          <Form.Item name="max-concurrent-downloads" label="Downloads simultâneos">
            <InputNumber min={1} max={50} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="max-connection-per-server" label="Conexões por servidor">
            <InputNumber min={1} max={16} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="split" label="Split (partes)">
            <InputNumber min={1} max={64} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="min-split-size" label="Tamanho mínimo por split">
            <Input placeholder="20M" />
          </Form.Item>
          <Form.Item name="continue" label="Continuar downloads parcial" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="file-allocation" label="Alocação de arquivo">
            <Input placeholder="prealloc" />
          </Form.Item>
          <Form.Item name="dir" label="Diretório padrão">
            <Input placeholder="F:\downloads" />
          </Form.Item>
        </>
      ),
    },
    {
      key: 'speed',
      label: 'Velocidade',
      children: (
        <>
          <Form.Item name="max-overall-download-limit" label="Limite global download">
            <Input placeholder="0 (ilimitado)" />
          </Form.Item>
          <Form.Item name="max-overall-upload-limit" label="Limite global upload">
            <Input placeholder="0 (ilimitado)" />
          </Form.Item>
          <Form.Item name="max-download-limit" label="Limite por task download">
            <Input placeholder="0 (ilimitado)" />
          </Form.Item>
          <Form.Item name="max-upload-limit" label="Limite por task upload">
            <Input placeholder="0 (ilimitado)" />
          </Form.Item>
        </>
      ),
    },
    {
      key: 'bittorrent',
      label: 'BitTorrent',
      children: (
        <>
          <Form.Item name="seed-ratio" label="Seed ratio (0 = não parar)">
            <InputNumber min={0} max={100} step={0.1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="seed-time" label="Seed time (minutos, 0 = não parar)">
            <InputNumber min={0} max={10080} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="bt-max-peers" label="Máximo de peers">
            <InputNumber min={0} max={500} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="bt-request-peer-speed-limit" label="Velocidade mínima de peer">
            <Input placeholder="2M" />
          </Form.Item>
        </>
      ),
    },
  ];

  return (
    <Modal title="Configurações aria2" open={open} onCancel={onClose}
      onOk={handleOk} confirmLoading={loading} okText="Salvar" cancelText="Cancelar"
      width={560}>
      <Form form={form} layout="vertical">
        <Tabs items={tabItems} size="small" />
      </Form>
    </Modal>
  );
}
