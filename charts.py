"""
charts.py
=========
Gráfico de linha em tempo real embutido na interface, usando matplotlib.

Demonstra:
- Integração entre duas bibliotecas (matplotlib + customtkinter)
- Estrutura de dados especializada (collections.deque com tamanho fixo)
- Programação orientada a objetos (encapsulamento do estado do gráfico)
"""

from collections import deque

import matplotlib
matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class LiveChart:
    """
    Gráfico de linha que mantém um histórico rolante (janela fixa) de valores
    — ideal para mostrar a evolução do uso de CPU de um container ao longo
    do tempo, sem deixar o gráfico crescer indefinidamente.
    """

    MAX_POINTS = 30  # quantidade de amostras visíveis no gráfico

    def __init__(self, parent, title: str = "Uso de CPU (%)"):
        self.history: deque[float] = deque(maxlen=self.MAX_POINTS)

        self.figure = Figure(figsize=(4.2, 2.4), dpi=90, facecolor="#2b2b2b")
        self.ax = self.figure.add_subplot(111)
        self._style_axes(title)

        self.line, = self.ax.plot([], [], color="#3ba55d", linewidth=2)

        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.draw()

    def _style_axes(self, title: str) -> None:
        """Aplica um visual escuro consistente com o tema da interface."""
        self.ax.set_facecolor("#1e1e1e")
        self.ax.set_title(title, color="white", fontsize=10)
        self.ax.tick_params(colors="white", labelsize=8)
        self._y_max = 100  # teto atual do eixo Y — pode crescer dinamicamente
        self.ax.set_ylim(0, self._y_max)
        for spine in self.ax.spines.values():
            spine.set_color("#555555")

    def widget(self):
        """Retorna o widget Tkinter para ser posicionado no layout (.pack/.grid)."""
        return self.canvas.get_tk_widget()

    def update(self, value: float) -> None:
        """Adiciona um novo valor ao histórico e redesenha o gráfico."""
        self.history.append(value)
        x_values = list(range(len(self.history)))
        y_values = list(self.history)

        # Quando há vários processos dentro do mesmo container (ex.: 5
        # processos "yes" rodando ao mesmo tempo), a soma de CPU pode
        # passar de 100% (cada núcleo conta separadamente). Em vez de
        # cortar a linha no topo do gráfico, esticamos o teto do eixo Y
        # para sempre caber o valor mais alto já visto.
        if value > self._y_max:
            self._y_max = (int(value / 50) + 1) * 50  # arredonda pra próxima centena/50
            self.ax.set_ylim(0, self._y_max)

        self.line.set_data(x_values, y_values)
        self.ax.set_xlim(0, max(self.MAX_POINTS - 1, 1))
        self.canvas.draw_idle()

    def clear(self) -> None:
        """Limpa o histórico (ex.: ao trocar de container selecionado)."""
        self.history.clear()
        self.line.set_data([], [])
        self._y_max = 100
        self.ax.set_ylim(0, self._y_max)
        self.canvas.draw_idle()
