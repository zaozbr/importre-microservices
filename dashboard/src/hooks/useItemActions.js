import { useCallback } from 'react';
import { message } from 'antd';

// Hook para acoes por item e aria2
export function useItemActions(onSuccess) {
  const action = useCallback(async (endpoint, method = 'POST', body = null) => {
    try {
      const opts = { method };
      if (body) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(body);
      }
      const res = await fetch(endpoint, opts);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      if (data.ok !== false) {
        if (onSuccess) onSuccess();
        return data;
      }
      throw new Error(data.error || 'Falha');
    } catch (e) {
      message.error(`Falha: ${e.message}`);
      return null;
    }
  }, [onSuccess]);

  const aria2Rpc = useCallback(async (method, params = []) => {
    try {
      const res = await fetch('/aria2', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', method: `aria2.${method}`, id: 'dash', params: ['token:devin', ...params] }),
      });
      const json = await res.json();
      return json.result;
    } catch (e) {
      message.error(`aria2 ${method}: ${e.message}`);
      return null;
    }
  }, []);

  return {
    // Item actions
    retry: (serial) => action(`/api/item/${serial}/retry`),
    search: (serial) => action(`/api/item/${serial}/search`),
    requeue: (serial) => action(`/api/item/${serial}/requeue`),
    multisource: (serial) => action(`/api/item/${serial}/multisource`),
    cancel: (serial) => action(`/api/item/${serial}/cancel`),
    getDetails: (serial) => action(`/api/item/${serial}/details`, 'GET'),
    reprocessFailures: () => action('/api/reprocess-failures'),
    // aria2 task actions
    aria2Pause: (gid) => action(`/api/aria2/pause/${gid}`),
    aria2Unpause: (gid) => action(`/api/aria2/unpause/${gid}`),
    aria2Remove: (gid) => action(`/api/aria2/remove/${gid}`),
    aria2Peers: (gid) => action(`/api/aria2/peers/${gid}`),
    aria2Files: (gid) => action(`/api/aria2/files/${gid}`),
    aria2Servers: (gid) => action(`/api/aria2/servers/${gid}`),
    aria2GetOption: (gid) => action(`/api/aria2/option/${gid}`),
    aria2ChangeOption: (gid, opts) => action(`/api/aria2/change-option/${gid}`, 'POST', opts),
    aria2ChangePosition: (gid, pos, how) => action(`/api/aria2/change-position/${gid}`, 'POST', { pos, how }),
    // aria2 global
    aria2GetGlobalOption: () => action('/api/aria2/global-option', 'GET'),
    aria2ChangeGlobalOption: (opts) => action('/api/aria2/change-global-option', 'POST', opts),
    // add downloads
    aria2AddUri: (uris, options) => action('/api/aria2/add-uri', 'POST', { uris, options }),
    aria2AddTorrent: (torrent, options) => action('/api/aria2/add-torrent', 'POST', { torrent, options }),
    // raw RPC
    aria2Rpc,
  };
}
