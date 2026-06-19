# Painel de Monitoramento — Infraestrutura Corporativa

**Trabalho da disciplina de Lógica de Programação em Python**
Instituto Federal de Mato Grosso — Campus Cuiabá

Aplicação desktop com interface gráfica que monitora em tempo real os containers Podman da infraestrutura corporativa desenvolvida na disciplina de Conteinerização e Orquestração ([`projeto-iac`](https://github.com/RainerJustiniano/projeto-iac)).

---

## Sumário

1. [O que o projeto demonstra](#o-que-o-projeto-demonstra)
2. [Arquitetura geral](#arquitetura-geral)
3. [Pré-requisitos e instalação](#pré-requisitos-e-instalação)
4. [Solução de problemas](#solução-de-problemas-leia-antes-de-pedir-ajuda)
5. [Explicação do código, arquivo por arquivo](#explicação-do-código-arquivo-por-arquivo)
6. [Perguntas que podem surgir na apresentação](#perguntas-que-podem-surgir-na-apresentação)
7. [Limitação conhecida: podman stats](#limitação-conhecida-podman-stats-pode-subestimar-a-cpu)
8. [Testes realizados](#testes-realizados)

---

## O que o projeto demonstra

| Requisito da disciplina | Onde está no código |
|---|---|
| Biblioteca externa (interface gráfica) | `customtkinter` em `app.py` |
| Biblioteca externa (gráficos) | `matplotlib` em `charts.py` |
| Biblioteca externa (monitoramento do host) | `psutil` em `app.py` |
| Interface gráfica | Janela completa com tabela, gráfico, botões e log |
| Monitoramento | Containers Podman (CPU, memória, status) em tempo real |
| Programação orientada a objetos | Classes `MonitorApp`, `LiveChart`, `ContainerInfo` |
| Threading / concorrência | Coleta de dados em thread separada (`threading.Thread`) |
| Comunicação entre threads | `queue.Queue` (forma segura de levar dados até a interface) |
| Tratamento de exceções | `PodmanNotFoundError`, `PodmanCommandError`, blocos try/except |
| Manipulação de arquivos | Exportação CSV (`csv`), logging em arquivo (`logging`) |
| Estruturas de dados | `dataclass`, `deque` (histórico do gráfico), listas/dicionários |
| **Conjuntos (`set`)** | `unique_states()` em `podman_client.py` — estados distintos dos containers |
| **`match`/`case`** | `_container_action()` em `app.py` — despacha start/stop/restart |
| **`break`/`continue`** | `list_containers()` — pula registros malformados sem travar |
| **Leitura de arquivo (`open(..., "r")`)** | `_view_log()` em `app.py` — lê e exibe o `monitor.log` salvo |
| **`try`/`except`/`else`/`finally`** | `_export_csv()` — fluxo completo com os 4 blocos |
| **`logging.debug()`** | Grava detalhes de cada ciclo de coleta só no arquivo (console mostra só INFO+) |
| Subprocessos | `subprocess` para executar comandos `podman` |
| Parsing de dados | `json` para interpretar a saída do Podman |

---

## Arquitetura geral

```
┌──────────────────┐      queue.Queue()      ┌───────────────────┐
│  THREAD DE COLETA │ ─────────────────────▶ │  THREAD PRINCIPAL  │
│  (segundo plano)  │                         │  (interface/GUI)   │
│                    │                         │                     │
│  • podman ps -a    │                         │  • lê a fila a      │
│  • podman stats    │                         │    cada 500ms       │
│  • psutil (host)   │                         │  • atualiza tabela  │
│  • sleep(4s)        │                         │  • redesenha gráfico│
└──────────────────┘                         └───────────────────┘
```

**Por que duas threads?** Os comandos `podman` podem demorar um pouco para responder. Se a interface gráfica esperasse essa resposta diretamente, a janela "congelaria" (ficaria sem resposta a cliques) durante esse tempo. Por isso, a coleta de dados roda em uma thread separada, em loop, e só entrega o resultado pronto para a tela através de uma fila (`queue.Queue`) — que é a forma seguro de mover dados entre threads no Tkinter, já que widgets gráficos não podem ser alterados diretamente de fora da thread principal.

---

## Pré-requisitos e instalação

> **Importante:** siga os passos NA ORDEM, e rode o comando de verificação depois de cada um. Pular um passo é a causa mais comum dos erros "ModuleNotFoundError".

### Passo 1 — Clonar os dois repositórios

Este painel monitora a infraestrutura do `projeto-iac` — então você precisa dos dois:

```bash
cd ~
git clone https://github.com/RainerJustiniano/projeto-iac.git
git clone https://github.com/RainerJustiniano/python-monitor.git
```

### Passo 2 — Instalar Podman e subir a infraestrutura

```bash
sudo apt update
sudo apt install -y podman ansible sshpass git

cd ~/projeto-iac
bash setup.sh
```

**Verificação:**
```bash
podman ps -a
```
✅ Espera-se ver 5 containers: `dns`, `adminsrv`, `worksrv`, `datastore`, `client` — todos "Up".

### Passo 3 — Instalar o `tkinter` (pacote de sistema, **não é só pip**)

```bash
sudo apt install -y python3-tk
```

**Verificação:**
```bash
python3 -c "import tkinter; print('tkinter OK')"
```
✅ Deve imprimir `tkinter OK`. Se der erro aqui, **não avance** — o programa não vai abrir.

### Passo 4 — Instalar as bibliotecas Python do projeto

```bash
cd ~/python-monitor
pip install -r requirements.txt --break-system-packages
```

**Verificação:**
```bash
python3 -c "import customtkinter, matplotlib, psutil; print('Bibliotecas OK')"
```
✅ Deve imprimir `Bibliotecas OK`. Se dar `ModuleNotFoundError`, o comando de instalação acima não rodou direito — role para cima e veja se apareceu algum erro em vermelho na saída dele, ou rode de novo.

### Passo 5 — Rodar o painel

```bash
python3 main.py
```

A janela deve abrir mostrando os 5 containers.

---

## Solução de problemas (leia antes de pedir ajuda!)

| Erro / Sintoma | Causa | Solução |
|---|---|---|
| `ModuleNotFoundError: No module named 'tkinter'` | Pacote de sistema não instalado (pip não resolve isso) | `sudo apt install -y python3-tk` |
| `ModuleNotFoundError: No module named 'customtkinter'` | Passo 4 não foi executado, ou falhou silenciosamente | Rode de novo: `pip install -r requirements.txt --break-system-packages` e confira a verificação do Passo 4 |
| `❌ O comando 'podman' não foi encontrado` | Podman não instalado nessa máquina | `sudo apt install -y podman` |
| Tabela aparece **vazia**, sem nenhum container | Os containers do `projeto-iac` não estão rodando | `cd ~/projeto-iac && bash setup.sh` |
| Janela **não abre**, nenhum erro aparece | Falta ambiente gráfico no WSL (sem WSLg) | Veja a seção abaixo "Janela não abre" |
| Erro ao rodar `pip install` mencionando "externally-managed-environment" | Proteção do Python 3.12+ contra instalar pacotes globalmente | Use a flag `--break-system-packages` (já está no comando do Passo 4) |
| CPU mostra **0.0%** mesmo com containers em uso | Comportamento normal — só mostra CPU de containers com status `running` | Inicie o container com o botão **▶ Start** no próprio painel |
| Tentou testar pelo **GitHub Codespaces** e não funcionou | Codespaces é uma máquina na nuvem — não tem Podman, não tem os containers, e não tem tela gráfica | Esse painel só funciona no WSL/Linux **local**, onde os containers realmente existem |

### "Janela não abre" — verificando o ambiente gráfico

```bash
echo $DISPLAY
```

- Se aparecer algo como `:0` → ambiente gráfico OK, o problema é outro (confira os passos acima)
- Se vier **vazio** → seu WSL não tem suporte gráfico (WSLg). Isso normalmente já vem ativado por padrão no **Windows 11**. Se estiver no Windows 10, instale o WSLg manualmente ou atualize para o Windows 11.

Teste rápido para confirmar se o WSLg está funcionando, independente do nosso programa:
```bash
sudo apt install -y x11-apps
xclock
```
Se um relógio aparecer na tela, o ambiente gráfico está OK.

---

## Explicação do código, arquivo por arquivo

### `main.py` — ponto de entrada

É o primeiro arquivo executado. Faz três coisas, em ordem:

1. Configura o sistema de logging (`setup_logger()`)
2. Verifica se o comando `podman` existe na máquina (`shutil.which("podman")`) — se não existir, mostra uma mensagem amigável em vez de deixar o programa quebrar com um erro feio
3. Cria a janela principal (`MonitorApp`) e entra no loop da interface (`app.mainloop()`)

```python
if shutil.which("podman") is None:
    print("❌ O comando 'podman' não foi encontrado...")
    return 1
```

Esse tipo de verificação chama-se **validação prévia** — checar as condições necessárias antes de tentar usar um recurso, evitando que o erro apareça de forma confusa mais tarde.

---

### `podman_client.py` — a "ponte" com o Podman

Esse arquivo não sabe nada sobre interface gráfica. Sua única responsabilidade é conversar com o Podman e devolver dados já organizados. Essa separação (interface não se mistura com lógica de dados) é uma boa prática chamada **separação de responsabilidades**.

**Como ele conversa com o Podman:** o Podman não tem uma "biblioteca Python oficial" simples de usar — então chamamos ele como se fosse um comando de terminal, usando `subprocess`:

```python
result = subprocess.run(["podman", "ps", "-a", "--format", "json"], ...)
```

A flag `--format json` faz o Podman devolver a resposta em **JSON** em vez de texto solto — daí usamos `json.loads()` para transformar isso em listas e dicionários do Python, fáceis de manipular.

**Principais funções:**

| Função | O que faz |
|---|---|
| `list_containers()` | Lista todos os containers e devolve uma lista de objetos `ContainerInfo` |
| `get_stats(name)` | Pega CPU% e memória de um container específico (só funciona se ele estiver rodando) |
| `start_container(name)` / `stop_container(name)` / `restart_container(name)` | Controlam o ciclo de vida do container |
| `inspect_ip(name)` | Descobre o IP do container dentro da rede |

**A classe `ContainerInfo`** é um `@dataclass` — um jeito mais simples de criar uma classe que só guarda dados, sem precisar escrever `__init__` na mão:

```python
@dataclass
class ContainerInfo:
    name: str
    image: str
    status: str
    state: str
    ports: str = "—"
    cpu_percent: float = 0.0
```

**Tratamento de erros:** criamos duas exceções personalizadas (`PodmanNotFoundError` e `PodmanCommandError`) em vez de deixar o Python mostrar um erro genérico. Isso permite que o resto do programa saiba exatamente *o que* deu errado e decida o que fazer — por exemplo, mostrar uma mensagem amigável na tela em vez de travar.

---

### `charts.py` — o gráfico de CPU ao vivo

A classe `LiveChart` embrulha um gráfico do **matplotlib** dentro de um widget que o Tkinter entende (`FigureCanvasTkAgg`).

**A parte mais interessante é o histórico com tamanho fixo:**

```python
self.history: deque[float] = deque(maxlen=self.MAX_POINTS)
```

Um `deque` (fila de duas pontas) com `maxlen=30` funciona como uma lista normal, mas quando você adiciona o 31º item, o primeiro item é **automaticamente descartado**. Isso evita que o gráfico cresça para sempre e fique cada vez mais lento — sempre mostramos só os últimos 30 segundos de uso de CPU.

```python
def update(self, value: float) -> None:
    self.history.append(value)
    ...
    self.canvas.draw_idle()
```

Cada vez que chega um novo valor de CPU, ele entra no `deque` e o gráfico é redesenhado.

---

### `app.py` — a interface gráfica (o arquivo mais importante)

Contém a classe `MonitorApp`, que herda de `ctk.CTk` (a janela principal do CustomTkinter). É o maior arquivo porque junta três responsabilidades: montar a tela, coletar dados em segundo plano, e reagir aos cliques do usuário.

**1. Montagem da tela** — vários métodos `_build_*`:

```python
def _build_layout(self):
    self._build_top_bar()         # título, botões, métricas do host
    self._build_container_table()  # tabela de containers
    self._build_detail_panel()     # gráfico + botões start/stop/restart
    self._build_log_panel()        # log de eventos
```

Dividir a construção da tela em vários métodos pequenos (em vez de um `__init__` gigante) facilita entender e modificar cada parte separadamente.

**2. A thread de coleta** — roda para sempre em segundo plano:

```python
def _poll_loop(self):
    while self._running:
        containers = pc.list_containers()
        stats = {c.name: pc.get_stats(c.name) for c in containers if c.state == "running"}
        self._data_queue.put({"containers": containers, "stats": stats, ...})
        time.sleep(self._refresh_interval)
```

**3. A leitura da fila, na thread principal:**

```python
def _poll_queue(self):
    try:
        while True:
            data = self._data_queue.get_nowait()
            self._update_ui(data)
    except queue.Empty:
        pass
    self.after(500, self._poll_queue)  # se chama de novo em 500ms
```

O método `self.after(500, ...)` é um recurso do próprio Tkinter: "espere 500ms e rode essa função de novo". Isso cria um laço de atualização **sem travar a interface**, bem diferente de um `while True` comum, que bloquearia a tela.

**4. Ações do usuário** (Start/Stop/Restart): cada clique dispara uma nova thread curta, para que mesmo um comando que demore um pouco não trave a tela:

```python
def _container_action(self, action):
    def run():
        message = actions[action](name)
        self._log(message)
    threading.Thread(target=run, daemon=True).start()
```

**5. Exportar CSV** — usa o módulo padrão `csv` para gravar os dados atuais em arquivo:

```python
with open(filepath, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["nome", "imagem", "status", "estado", "portas"])
    for c in self._last_containers:
        writer.writerow([c.name, c.image, c.status, c.state, c.ports])
```

---

### `logger_config.py` — registro de eventos

Configura o módulo padrão `logging` para escrever simultaneamente:
- no arquivo `monitor.log` (fica salvo mesmo depois de fechar o programa)
- no console (útil durante o desenvolvimento)

```python
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
console_handler = logging.StreamHandler()
```

Diferente de simplesmente usar `print()`, o `logging` permite níveis de gravidade (`INFO`, `ERROR`, etc.) e grava automaticamente a data/hora de cada evento — essencial para depois conseguir auditar o que aconteceu.

---

## Perguntas que podem surgir na apresentação

**"Por que não usar `print()` em vez de `logging`?"**
`print()` só mostra na tela; some quando o terminal fecha. `logging` grava em arquivo permanentemente e permite níveis de gravidade — importante para depurar problemas depois que o programa já foi fechado.

**"Por que precisa de duas threads? Não dava pra fazer tudo numa só?"**
Daria, mas a tela ficaria "congelada" (sem responder a cliques) durante todo o tempo em que o programa estivesse esperando a resposta do comando `podman`, que pode demorar. Com duas threads, a tela continua respondendo normalmente enquanto a coleta acontece por trás.

**"O que aconteceria se eu não usasse `queue.Queue` para comunicar as threads?"**
Tkinter (a base do customtkinter) não foi feito para ser alterado por mais de uma thread ao mesmo tempo. Mexer direto nos widgets de dentro da thread de coleta pode causar comportamento imprevisível ou travamentos aleatórios. A fila resolve isso: a thread de coleta só *deposita* dados, e só a thread principal *usa* esses dados para atualizar a tela.

**"O que é um `dataclass`? Por que usar em vez de uma classe normal?"**
É um recurso do Python que gera automaticamente o `__init__` e outros métodos repetitivos quando a classe serve só para guardar dados (como `ContainerInfo`). Economiza código sem perder clareza.

**"O que acontece se o Podman não estiver instalado?"**
O programa verifica isso *antes* de tentar abrir a janela (`main.py`) e mostra uma mensagem clara em vez de travar com um erro técnico confuso.

---

## Limitação conhecida: `podman stats` pode subestimar a CPU

Em ambientes Podman **rootless** com cgroups em modo "hybrid" (comum no WSL), processos criados dentro do container via `podman exec -d` às vezes não são contabilizados corretamente pelo `podman stats`. Em um teste real, com 5 processos `yes` consumindo ~73% de CPU cada (confirmado via `podman top`), o `podman stats` reportava apenas **3.75%** — um valor claramente incorreto.

**Solução implementada:** `get_stats()` agora calcula a CPU de duas formas — pelo `podman stats` tradicional e somando o `%CPU` de cada processo via `podman top` — e usa o **maior valor entre as duas**. Isso corrige a subestimação nesse cenário, sem prejudicar ambientes onde `podman stats` já funciona normalmente.

Como a soma de vários processos pode superar 100% (cada núcleo conta separadamente), o gráfico (`charts.py`) também foi ajustado para **esticar o eixo Y automaticamente** quando o valor passa do teto atual, em vez de cortar a linha no topo.

---

## Testes realizados

A lógica de parsing (`podman_client.py`) foi validada com dados simulados (mock de `subprocess`), cobrindo:
- Container em execução com portas mapeadas
- Container parado sem portas
- Estatísticas de CPU/memória em formatos diferentes
- Container sem estatísticas disponíveis (retorno `None`)

A interface completa foi testada de ponta a ponta com um display virtual (Xvfb) e containers reais, confirmando listagem correta na tabela, atualização periódica via thread+queue, exportação de CSV e métricas do host via `psutil`.

---

*Projeto desenvolvido para a disciplina de Lógica de Programação em Python — IFMT Campus Cuiabá*
