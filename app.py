"""
app.py
======
Interface gráfica principal — Painel de Monitoramento da Infraestrutura.

Demonstra:
- Programação orientada a objetos (classe MonitorApp)
- Threading (coleta de dados em segundo plano, sem travar a GUI)
- Comunicação segura entre threads via queue.Queue
- Manipulação de arquivos (exportação CSV)
- Tratamento de exceções
- Estruturas de controle (laços, condicionais)
- Bibliotecas externas: customtkinter, matplotlib (via charts.py), psutil
"""

from __future__ import annotations

import csv
import os
import queue
import threading
import time
from datetime import datetime
from tkinter import ttk

import customtkinter as ctk

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

import podman_client as pc
from charts import LiveChart

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class MonitorApp(ctk.CTk):
    """Janela principal da aplicação de monitoramento."""

    DEFAULT_INTERVAL_SECONDS = 4

    def __init__(self, logger):
        super().__init__()
        self.logger = logger

        self.title("Painel de Monitoramento — Infraestrutura Corporativa")
        self.geometry("1300x650")
        self.minsize(1100, 600)

        # Estado interno
        self._data_queue: queue.Queue = queue.Queue()
        self._running = True
        self._selected_container: str | None = None
        self._refresh_interval = self.DEFAULT_INTERVAL_SECONDS
        self._last_containers: list[pc.ContainerInfo] = []

        self._build_layout()
        self._start_background_thread()
        self._poll_queue()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        self._build_top_bar()
        self._build_container_table()
        self._build_detail_panel()
        self._build_log_panel()

    def _build_top_bar(self) -> None:
        top = ctk.CTkFrame(self, height=70)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        top.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(
            top, text="🖥️  Infraestrutura Corporativa — projeto-iac",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=15, pady=15, sticky="w")

        ctk.CTkButton(
            top, text="Atualizar agora", command=self._force_refresh, width=140,
        ).grid(row=0, column=1, padx=5)

        ctk.CTkButton(
            top, text="Exportar CSV", command=self._export_csv, width=120,
            fg_color="#3b6ea5", hover_color="#2d567f",
        ).grid(row=0, column=2, padx=5)

        ctk.CTkButton(
            top, text="Ver log salvo", command=self._view_log, width=120,
            fg_color="#6a4c93", hover_color="#523a72",
        ).grid(row=0, column=3, padx=5)

        self.status_label = ctk.CTkLabel(
            top, text="Iniciando...", text_color="gray", anchor="e"
        )
        self.status_label.grid(row=0, column=5, padx=15, sticky="e")

        if PSUTIL_AVAILABLE:
            self.host_label = ctk.CTkLabel(top, text="", text_color="#3ba55d")
            self.host_label.grid(row=0, column=4, padx=15)

    def _build_container_table(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=5)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame, text="Containers", font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))

        columns = ("name", "status", "cpu", "mem", "ports")
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview", background="#1e1e1e", foreground="white",
            fieldbackground="#1e1e1e", rowheight=28, font=("Segoe UI", 10),
        )
        style.configure("Treeview.Heading", background="#2b2b2b", foreground="white")
        style.map("Treeview", background=[("selected", "#3ba55d")])

        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        headers = {
            "name": "Nome", "status": "Status", "cpu": "CPU %",
            "mem": "Memória", "ports": "Portas",
        }
        widths = {"name": 110, "status": 130, "cpu": 70, "mem": 110, "ports": 130}
        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], anchor="center")

        # Barra de rolagem vertical — necessária quando há muitos containers
        # (sem isso, linhas além da altura visível ficam inacessíveis)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=10)
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 10), pady=10)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_container)

    def _build_detail_panel(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=5)
        frame.grid_columnconfigure(0, weight=1)

        self.detail_title = ctk.CTkLabel(
            frame, text="Selecione um container", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.detail_title.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 5))

        self.detail_info = ctk.CTkLabel(frame, text="", justify="left", anchor="w")
        self.detail_info.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))

        chart_holder = ctk.CTkFrame(frame, fg_color="#1e1e1e")
        chart_holder.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        frame.grid_rowconfigure(2, weight=1)

        self.chart = LiveChart(chart_holder, title="Uso de CPU (%)")
        self.chart.widget().pack(fill="both", expand=True, padx=5, pady=5)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            btn_frame, text="▶ Start", fg_color="#3ba55d", hover_color="#2d8048",
            command=lambda: self._container_action("start"),
        ).grid(row=0, column=0, padx=4, sticky="ew")

        ctk.CTkButton(
            btn_frame, text="■ Stop", fg_color="#c0392b", hover_color="#922b21",
            command=lambda: self._container_action("stop"),
        ).grid(row=0, column=1, padx=4, sticky="ew")

        ctk.CTkButton(
            btn_frame, text="↻ Restart", fg_color="#e67e22", hover_color="#af601a",
            command=lambda: self._container_action("restart"),
        ).grid(row=0, column=2, padx=4, sticky="ew")

    def _build_log_panel(self) -> None:
        frame = ctk.CTkFrame(self, height=140)
        frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 10))
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame, text="Eventos recentes", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))

        self.log_box = ctk.CTkTextbox(frame, height=90, font=("Consolas", 11))
        self.log_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # Coleta de dados em segundo plano (thread separada)
    # ------------------------------------------------------------------
    def _start_background_thread(self) -> None:
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self) -> None:
        """
        Executa em uma thread separada para não bloquear a interface
        enquanto aguarda a resposta dos comandos podman (que podem
        demorar um pouco). Os resultados são colocados em uma Queue,
        que é a forma segura de levar dados de uma thread para a
        thread principal da GUI no Tkinter.
        """
        while self._running:
            try:
                containers = pc.list_containers()
                self.logger.debug(
                    f"Ciclo de coleta: {len(containers)} container(s) encontrado(s) "
                    f"— estados: {pc.unique_states(containers)}"
                )

                stats_by_name = {}
                for c in containers:
                    if c.state == "running":
                        stats = pc.get_stats(c.name)
                        if stats:
                            stats_by_name[c.name] = stats

                host_stats = None
                if PSUTIL_AVAILABLE:
                    host_stats = {
                        "cpu": psutil.cpu_percent(interval=None),
                        "mem": psutil.virtual_memory().percent,
                    }

                self._data_queue.put({
                    "containers": containers,
                    "stats": stats_by_name,
                    "host": host_stats,
                    "error": None,
                })
            except pc.PodmanNotFoundError as exc:
                self._data_queue.put({"error": str(exc)})
            except Exception as exc:  # pragma: no cover - defesa contra falhas inesperadas
                self._data_queue.put({"error": f"Erro inesperado: {exc}"})

            time.sleep(self._refresh_interval)

    def _poll_queue(self) -> None:
        """
        Roda na thread principal (GUI). Verifica periodicamente se há
        dados novos na queue e atualiza os widgets — esse é o único
        lugar onde widgets Tkinter são tocados, evitando problemas de
        concorrência entre threads.
        """
        try:
            while True:
                data = self._data_queue.get_nowait()
                self._update_ui(data)
        except queue.Empty:
            pass

        self.after(500, self._poll_queue)

    # ------------------------------------------------------------------
    # Atualização da interface
    # ------------------------------------------------------------------
    def _update_ui(self, data: dict) -> None:
        if data.get("error"):
            self.status_label.configure(text=f"⚠ {data['error']}", text_color="#e74c3c")
            self._log(f"ERRO: {data['error']}")
            return

        containers = data["containers"]
        stats = data["stats"]
        self._last_containers = containers

        self.tree.delete(*self.tree.get_children())
        for c in containers:
            cpu = stats.get(c.name, {}).get("cpu_percent", 0.0)
            mem = stats.get(c.name, {}).get("mem_usage", "—")
            status_icon = "🟢" if c.state == "running" else "🔴"
            self.tree.insert(
                "", "end", iid=c.name,
                values=(c.name, f"{status_icon} {c.state}", f"{cpu:.1f}", mem, c.ports),
            )

        if self._selected_container and self._selected_container in stats:
            cpu = stats[self._selected_container]["cpu_percent"]
            self.chart.update(cpu)

        timestamp = datetime.now().strftime("%H:%M:%S")
        estados = pc.unique_states(containers)  # set — estados distintos no momento
        self.status_label.configure(
            text=f"Atualizado {timestamp}  |  Estados: {', '.join(sorted(estados))}",
            text_color="gray",
        )

        if PSUTIL_AVAILABLE and data.get("host"):
            host = data["host"]
            self.host_label.configure(
                text=f"Host → CPU: {host['cpu']:.0f}%  |  RAM: {host['mem']:.0f}%"
            )

    def _on_select_container(self, _event) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        name = selection[0]
        self._selected_container = name
        self.chart.clear()

        container = next((c for c in self._last_containers if c.name == name), None)
        if container:
            self.detail_title.configure(text=f"📦 {name}")
            self.detail_info.configure(
                text=(
                    f"Imagem:  {container.image}\n"
                    f"Status:  {container.status}\n"
                    f"Portas:  {container.ports}"
                )
            )

    # ------------------------------------------------------------------
    # Ações do usuário
    # ------------------------------------------------------------------
    def _container_action(self, action: str) -> None:
        if not self._selected_container:
            self._log("Nenhum container selecionado.")
            return

        name = self._selected_container

        def run():
            try:
                # match/case (Python 3.10+) — equivalente a um switch,
                # mais legível que vários if/elif quando comparamos
                # um único valor contra várias opções fixas.
                match action:
                    case "start":
                        message = pc.start_container(name)
                    case "stop":
                        message = pc.stop_container(name)
                    case "restart":
                        message = pc.restart_container(name)
                    case _:
                        message = f"Ação desconhecida: {action}"

                self._log(message)
                self.logger.info(message)
            except pc.PodmanCommandError as exc:
                self._log(f"Falha ao executar '{action}' em {name}: {exc}")
                self.logger.error(f"Falha ao executar '{action}' em {name}: {exc}")

        # Roda em thread separada para não travar a GUI durante o comando
        threading.Thread(target=run, daemon=True).start()

    def _force_refresh(self) -> None:
        self._log("Atualização manual solicitada pelo usuário.")
        # Acelera a próxima coleta sem esperar o intervalo completo
        threading.Thread(target=self._immediate_poll, daemon=True).start()

    def _immediate_poll(self) -> None:
        try:
            containers = pc.list_containers()
            stats_by_name = {
                c.name: pc.get_stats(c.name)
                for c in containers if c.state == "running"
            }
            stats_by_name = {k: v for k, v in stats_by_name.items() if v}
            self._data_queue.put({"containers": containers, "stats": stats_by_name, "host": None, "error": None})
        except Exception as exc:
            self._data_queue.put({"error": str(exc)})

    def _view_log(self) -> None:
        """
        Lê o arquivo monitor.log (modo "r" — leitura) e mostra as últimas
        linhas em uma janela separada. É o complemento da exportação CSV:
        lá nós ESCREVEMOS um arquivo; aqui nós LEMOS um arquivo de volta.
        """
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor.log")

        if not os.path.exists(log_path):
            self._log("Ainda não existe monitor.log para ler.")
            return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                linhas = f.readlines()
        except OSError as exc:
            self._log(f"Erro ao ler o log: {exc}")
            return

        ultimas = linhas[-50:]  # só as últimas 50 linhas, pra não poluir a tela

        janela = ctk.CTkToplevel(self)
        janela.title("monitor.log — últimas 50 linhas")
        janela.geometry("700x400")

        caixa = ctk.CTkTextbox(janela, font=("Consolas", 10))
        caixa.pack(fill="both", expand=True, padx=10, pady=10)
        caixa.insert("end", "".join(ultimas) if ultimas else "(arquivo vazio)")
        caixa.configure(state="disabled")

        self._log(f"Log aberto: {len(ultimas)} linha(s) exibida(s) de {len(linhas)} no total.")

    def _export_csv(self) -> None:
        """Exporta o snapshot atual da tabela de containers para um arquivo CSV."""
        if not self._last_containers:
            self._log("Nada para exportar ainda — aguarde a primeira coleta.")
            return

        os.makedirs(EXPORTS_DIR, exist_ok=True)
        filename = f"snapshot_{datetime.now():%Y%m%d_%H%M%S}.csv"
        filepath = os.path.join(EXPORTS_DIR, filename)

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["nome", "imagem", "status", "estado", "portas"])
                for c in self._last_containers:
                    writer.writerow([c.name, c.image, c.status, c.state, c.ports])
        except OSError as exc:
            self._log(f"Erro ao exportar CSV: {exc}")
            self.logger.error(f"Erro ao exportar CSV: {exc}")
        else:
            # O bloco "else" do try só executa se NENHUMA exceção ocorreu —
            # diferente de só colocar essas linhas depois do try/except,
            # aqui fica explícito que essa é a "via de sucesso".
            self._log(f"Exportado: exports/{filename}")
            self.logger.info(f"Snapshot exportado para {filepath}")
        finally:
            # O bloco "finally" executa SEMPRE, com ou sem erro —
            # útil para um registro de auditoria de que a operação
            # foi tentada, independentemente do resultado.
            self.logger.debug(f"Tentativa de exportação CSV finalizada ({filename}).")

    # ------------------------------------------------------------------
    # Log na interface
    # ------------------------------------------------------------------
    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_close(self) -> None:
        self._running = False
        self.logger.info("Sessão finalizada pelo usuário.")
        self.destroy()
