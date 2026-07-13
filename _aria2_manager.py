"""
_aria2_manager.py — Gerenciador do daemon aria2c com RPC JSON-RPC.

Funcionalidades:
- Inicia/para daemon aria2c com RPC habilitado (porta 6800)
- add_uri(): adiciona download com multi-chunk (16 conexões)
- status(): consulta status de downloads ativos/completos/parados
- pause/resume/remove: controle individual de downloads
- Resume automático: aria2c salva .aria2 control file, retoma do byte exato
- Daemon persistente: sobrevive a crashes do Python orquestrador
- Session file: lista de downloads é persistida em disco

Uso:
    from _aria2_manager import Aria2Manager
    mgr = Aria2Manager()
    mgr.start_daemon()           # inicia aria2c com RPC
    gid = mgr.add_uri(url, dest_dir, filename)  # adiciona download
    mgr.wait_complete(gid)       # aguarda conclusão
    mgr.stop_daemon()            # para daemon graciosamente
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ARIA2C_EXE = r"C:\aria2\aria2c.exe"
RPC_PORT = 6801
RPC_SECRET = "psx_download_2026"
SESSION_FILE = r"D:\roms\library\roms\_importre_state\aria2_session.txt"
DOWNLOAD_DIR = r"D:\roms\library\roms\_importre_state\downloads"
LOG_FILE = r"D:\roms\library\roms\_importre_state\aria2c.log"
PID_FILE = r"D:\roms\library\roms\_importre_state\aria2c.pid"


class Aria2Manager:
    """Gerencia o daemon aria2c via JSON-RPC."""

    def __init__(self, port=RPC_PORT, secret=RPC_SECRET):
        self.port = port
        self.secret = secret
        self.rpc_url = f"http://localhost:{port}/jsonrpc"
        self._daemon_proc = None

    # ── Daemon management ──────────────────────────────────────────

    def start_daemon(self):
        """Inicia aria2c como daemon com RPC habilitado."""
        # Verifica se já está rodando (verificação robusta: porta + PID + tasklist)
        if self.is_daemon_running():
            print(f"aria2c daemon já rodando na porta {self.port}")
            return True
        
        # Verificação extra: se há qualquer aria2c.exe rodando, não iniciar outro
        try:
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq aria2c.exe", "/NH"],
                              capture_output=True, text=True, timeout=3)
            if "aria2c.exe" in r.stdout:
                print(f"aria2c já está rodando (tasklist) — não iniciando outro")
                return True
        except:
            pass

        # Garante diretórios
        Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(SESSION_FILE).parent.mkdir(parents=True, exist_ok=True)

        # Cria session file vazio se não existir
        if not os.path.exists(SESSION_FILE):
            Path(SESSION_FILE).touch()

        cmd = [
            ARIA2C_EXE,
            f"--rpc-listen-port={self.port}",
            f"--rpc-secret={self.secret}",
            "--enable-rpc=true",
            "--rpc-allow-origin-all=true",
            "--rpc-listen-all=false",
            "--continue=true",
            "--always-resume=true",
            "--max-tries=0",              # retry infinito
            "--retry-wait=3",             # 3s entre retries
            "--max-concurrent-downloads=20",  # 20 arquivos em paralelo (40 causava 500 no archive.org)
            "--max-connection-per-server=4",  # 4 conexões por servidor
            "--split=4",                  # 4 chunks por arquivo
            "--min-split-size=1M",        # chunks de no mínimo 1MB
            "--file-allocation=trunc",    # trunc não precisa de privilégio admin (falloc precisa)
            "--max-overall-download-limit=0",  # sem limite global
            "--bt-max-peers=0",           # sem BT (apenas HTTP/HTTPS)
            # NOTA: Tor proxy testado e rejeitado — overhead de Tor (0.02-0.05MB/s) é pior que
            # rate limit do archive.org direto (0.2MB/s). Ver _test_tor_speed.py e lição 45.
            # Cookies de sessão do archive.org (auth = rate limit maior + coleções restritas)
            "--load-cookies=" + os.path.join(os.path.dirname(DOWNLOAD_DIR), "archive_cookies.txt"),
            f"--dir={DOWNLOAD_DIR}",
            f"--log={LOG_FILE}",
            "--log-level=warn",
            "--console-log-level=warn",
            "--input-file=" + SESSION_FILE,
            "--save-session=" + SESSION_FILE,
            "--save-session-interval=10",  # salva session a cada 10s
            "--auto-file-renaming=false",
            "--allow-overwrite=true",    # sobrescrever arquivos órfãos (sem .aria2 control file)
            # NÃO usar --daemon=true no Windows (problemático)
            # Em vez disso, usamos DETACHED_PROCESS + CREATE_NO_WINDOW
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            self._daemon_proc = proc

            # Salva PID
            with open(PID_FILE, "w") as f:
                f.write(str(proc.pid))

            # Aguarda daemon responder (timeout reduzido: 10 tentativas x 0.5s = 5s)
            for i in range(10):
                time.sleep(0.5)
                if self.is_daemon_running():
                    msg = f"aria2c daemon iniciado (PID={proc.pid}, porta={self.port})"
                    try:
                        print(msg)
                    except:
                        pass  # stdout pode estar fechado em pythonw
                    return True

            # Verificar se o processo ainda está vivo
            if proc.poll() is not None:
                msg = f"ERRO: aria2c processo morreu imediatamente (exit code={proc.returncode})"
            else:
                msg = "ERRO: aria2c daemon não respondeu RPC em 5s"
            try:
                print(msg)
            except:
                pass
            return False

        except Exception as e:
            try:
                print(f"ERRO ao iniciar aria2c: {e}")
            except:
                pass
            return False

    def stop_daemon(self):
        """Para o daemon aria2c graciosamente via RPC."""
        try:
            # Tenta shutdown graceful com timeout curto
            import urllib.request
            payload = json.dumps({
                "jsonrpc": "2.0", "id": "stop",
                "method": "aria2.shutdown",
                "params": [f"token:{self.secret}"],
            }).encode("utf-8")
            req = urllib.request.Request(
                self.rpc_url, data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=3)
        except:
            pass
        # Aguarda apenas 1s
        time.sleep(1)
        # Force kill pelo PID
        try:
            if os.path.exists(PID_FILE):
                pid = int(open(PID_FILE).read().strip())
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, timeout=5)
                os.remove(PID_FILE)
        except:
            pass
        # Force kill global como último recurso
        try:
            subprocess.run(["taskkill", "/F", "/IM", "aria2c.exe"],
                           capture_output=True, timeout=5)
        except:
            pass
        self._daemon_proc = None
        print("aria2c daemon parado")

    def is_daemon_running(self):
        """Verifica se o daemon está respondendo via RPC.
        Primeiro checa se a porta está em uso (rápido), depois tenta RPC.
        Isto evita iniciar múltiplas instâncias quando o aria2c está ocupado baixando
        e o RPC timeout faz is_daemon_running retornar False falsamente.
        """
        # 1. Verificação rápida: porta em uso?
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", self.port))
            s.close()
            if result != 0:
                return False  # porta não está em uso — daemon não está rodando
        except:
            pass
        
        # 2. Verificação por PID salvo (mais rápida que RPC)
        try:
            if os.path.exists(PID_FILE):
                pid = int(open(PID_FILE).read().strip())
                r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                  capture_output=True, text=True, timeout=3)
                if str(pid) in r.stdout:
                    # Processo existe — daemon está rodando (mesmo se RPC estiver lento)
                    return True
        except:
            pass
        
        # 3. Verificação por tasklist (qualquer aria2c na porta)
        try:
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq aria2c.exe", "/NH"],
                              capture_output=True, text=True, timeout=3)
            if "aria2c.exe" in r.stdout:
                # Há aria2c rodando — assumir que está vivo
                return True
        except:
            pass
        
        # 4. Fallback: tentar RPC (lento, pode timeout)
        try:
            self._call("aria2.getVersion")
            return True
        except:
            return False

    def get_pid(self):
        """Retorna PID do daemon ou None."""
        try:
            if os.path.exists(PID_FILE):
                pid = int(open(PID_FILE).read().strip())
                # Verifica se processo está vivo
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True, text=True, timeout=5)
                if str(pid) in result.stdout:
                    return pid
                else:
                    os.remove(PID_FILE)
        except:
            pass
        return None

    # ── JSON-RPC ───────────────────────────────────────────────────

    def _call(self, method, params=None):
        """Chama método JSON-RPC do aria2c."""
        if params is None:
            params = []
        # Secret token deve ser primeiro parâmetro
        full_params = [f"token:{self.secret}"] + params

        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": "1",
            "method": method,
            "params": full_params,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.rpc_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "error" in data:
                    raise RuntimeError(f"aria2 RPC error: {data['error']}")
                return data.get("result")
        except urllib.error.URLError as e:
            raise ConnectionError(f"aria2c RPC indisponível: {e}")
        except Exception as e:
            raise ConnectionError(f"aria2c RPC erro: {e}")

    # ── Download operations ────────────────────────────────────────

    def add_uri(self, url, dest_dir=None, filename=None, options=None):
        """
        Adiciona URL para download. Retorna GID (group ID).

        Args:
            url: URL do arquivo
            dest_dir: diretório destino (default: DOWNLOAD_DIR)
            filename: nome do arquivo (default: nome da URL)
            options: dict de opções extras do aria2c
        Returns:
            GID string (16 chars hex)
        """
        opts = {}
        if dest_dir:
            opts["dir"] = dest_dir
        if filename:
            opts["out"] = filename
        if options:
            opts.update(options)

        # addUri(uris[], options={}, position=undefined)
        params = [[url], opts]
        gid = self._call("aria2.addUri", params)
        return gid

    def add_metalink(self, metalink_path, options=None):
        """Adiciona metalink para download. Retorna array de GIDs."""
        opts = options or {}
        # addMetalink(metalinkFile_b64, options={})
        with open(metalink_path, "rb") as f:
            import base64
            b64 = base64.b64encode(f.read()).decode("ascii")
        params = [b64, opts]
        gids = self._call("aria2.addMetalink", params)
        return gids

    def tell_status(self, gid):
        """Retorna status completo de um download por GID."""
        return self._call("aria2.tellStatus", [gid])

    def tell_active(self):
        """Lista downloads ativos."""
        return self._call("aria2.tellActive", [[]])

    def tell_waiting(self, offset=0, num=100):
        """Lista downloads aguardando."""
        return self._call("aria2.tellWaiting", [offset, num, []])

    def tell_stopped(self, offset=0, num=100):
        """Lista downloads completos/erro."""
        return self._call("aria2.tellStopped", [offset, num, []])

    def pause(self, gid):
        """Pausa download."""
        return self._call("aria2.pause", [gid])

    def resume(self, gid):
        """Resume download pausado."""
        return self._call("aria2.unpause", [gid])

    def remove(self, gid):
        """Remove download (e deleta arquivo parcial se force=true)."""
        try:
            return self._call("aria2.remove", [gid])
        except:
            return self._call("aria2.forceRemove", [gid])

    def remove_download_result(self, gid):
        """Remove resultado de download completo/erro da lista."""
        return self._call("aria2.removeDownloadResult", [gid])

    def get_global_stat(self):
        """Estatísticas globais: velocidade, contagens."""
        return self._call("aria2.getGlobalStat")

    def purge_download_result(self):
        """Limpa todos resultados completos/erro."""
        return self._call("aria2.purgeDownloadResult")

    def change_option(self, gid, options):
        """Muda opções de um download ativo."""
        return self._call("aria2.changeOption", [gid, options])

    def change_global_option(self, options):
        """Muda opções globais (ex: max-concurrent-downloads)."""
        return self._call("aria2.changeGlobalOption", [options])

    # ── Helpers ────────────────────────────────────────────────────

    def wait_complete(self, gid, timeout=3600, poll_interval=2):
        """
        Aguarda download completar. Retorna True se completo, False se timeout/erro.

        Args:
            gid: GID do download
            timeout: tempo máximo em segundos
            poll_interval: intervalo de polling em segundos
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                status = self.tell_status(gid)
                state = status.get("status", "unknown")
                if state == "complete":
                    return True
                elif state == "error" or state == "removed":
                    return False
                # active / waiting / paused → continuar aguardando
            except Exception as e:
                print(f"  aria2 wait_complete: erro consultando {gid}: {e}")
            time.sleep(poll_interval)
        return False

    def get_download_info(self, gid):
        """Retorna dict com info resumida do download."""
        try:
            s = self.tell_status(gid)
            return {
                "gid": gid,
                "status": s.get("status"),
                "filename": s.get("files", [{}])[0].get("path", ""),
                "total_length": int(s.get("totalLength", 0)),
                "completed_length": int(s.get("completedLength", 0)),
                "download_speed": int(s.get("downloadSpeed", 0)),
                "upload_speed": int(s.get("uploadSpeed", 0)),
                "connections": int(s.get("connections", 0)),
                "num_seeders": int(s.get("numSeeders", 0)),
                "error_code": s.get("errorCode", "0"),
                "error_message": s.get("errorMessage", ""),
                "progress_pct": (
                    float(s.get("completedLength", 0)) / float(s.get("totalLength", 1)) * 100
                    if int(s.get("totalLength", 0)) > 0 else 0
                ),
            }
        except Exception as e:
            return {"gid": gid, "status": "error", "error_message": str(e)}

    def list_all(self):
        """Lista todos downloads (active + waiting + stopped)."""
        result = []
        try:
            result.extend(self.tell_active())
        except:
            pass
        try:
            result.extend(self.tell_waiting(0, 100))
        except:
            pass
        try:
            result.extend(self.tell_stopped(0, 100))
        except:
            pass
        return result

    def get_summary(self):
        """Retorna resumo: contagens + velocidade total."""
        try:
            stat = self.get_global_stat()
            active = self.tell_active()
            return {
                "active": int(stat.get("numActive", 0)),
                "waiting": int(stat.get("numWaiting", 0)),
                "stopped": int(stat.get("numStopped", 0)),
                "download_speed": int(stat.get("downloadSpeed", 0)),
                "upload_speed": int(stat.get("uploadSpeed", 0)),
                "active_details": [self._summarize(d) for d in active],
            }
        except Exception as e:
            return {"error": str(e)}

    def _summarize(self, d):
        """Resume um download dict do aria2."""
        try:
            total = int(d.get("totalLength", 0))
            completed = int(d.get("completedLength", 0))
            pct = (completed / total * 100) if total > 0 else 0
            files = d.get("files", [{}])
            path = files[0].get("path", "") if files else ""
            return {
                "gid": d.get("gid"),
                "status": d.get("status"),
                "filename": os.path.basename(path) if path else "",
                "total_mb": total / 1e6,
                "completed_mb": completed / 1e6,
                "pct": pct,
                "speed_mbs": int(d.get("downloadSpeed", 0)) / 1e6,
                "connections": int(d.get("connections", 0)),
            }
        except:
            return {"gid": d.get("gid"), "status": d.get("status")}


# ── CLI para teste standalone ──────────────────────────────────────

def _main_cli():
    """CLI: python _aria2_manager.py [start|stop|status|test <url>]"""
    if len(sys.argv) < 2:
        print("Uso: python _aria2_manager.py [start|stop|status|test <url>]")
        sys.exit(1)

    cmd = sys.argv[1]
    mgr = Aria2Manager()

    if cmd == "start":
        ok = mgr.start_daemon()
        sys.exit(0 if ok else 1)

    elif cmd == "stop":
        mgr.stop_daemon()
        sys.exit(0)

    elif cmd == "status":
        if not mgr.is_daemon_running():
            print("aria2c daemon NÃO está rodando")
            sys.exit(1)
        summary = mgr.get_summary()
        print(json.dumps(summary, indent=2, default=str))

    elif cmd == "test":
        if len(sys.argv) < 3:
            print("Uso: python _aria2_manager.py test <url>")
            sys.exit(1)
        url = sys.argv[2]
        if not mgr.is_daemon_running():
            mgr.start_daemon()
        print(f"Adicionando: {url}")
        gid = mgr.add_uri(url)
        print(f"GID: {gid}")
        print("Aguardando conclusão...")
        ok = mgr.wait_complete(gid, timeout=300)
        if ok:
            info = mgr.get_download_info(gid)
            print(f"Completo: {info['filename']} ({info['completed_length']/1e6:.1f}MB)")
        else:
            info = mgr.get_download_info(gid)
            print(f"Falhou: {info.get('error_message', 'timeout')}")
        sys.exit(0 if ok else 1)

    else:
        print(f"Comando desconhecido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    _main_cli()
