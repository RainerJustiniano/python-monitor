# Painel de Monitoramento de Infraestrutura em Python

**Instituto Federal de Mato Grosso — Campus Cuiabá**
**Disciplina:** Lógica de Programação em Python

---

## Sumário

1. [Introdução](#1-introdução)
2. [Objetivos](#2-objetivos)
3. [Arquitetura do Sistema](#3-arquitetura-do-sistema)
4. [Tecnologias e Bibliotecas Utilizadas](#4-tecnologias-e-bibliotecas-utilizadas)
5. [Estrutura do Projeto](#5-estrutura-do-projeto)
6. [Descrição dos Módulos](#6-descrição-dos-módulos)
7. [Instalação](#7-instalação)
8. [Execução](#8-execução)
9. [Funcionalidades](#9-funcionalidades)
10. [Testes e Validação](#10-testes-e-validação)
11. [Limitações e Observações Técnicas](#11-limitações-e-observações-técnicas)
12. [Conclusão](#12-conclusão)

---

## 1. Introdução

Este projeto consiste em uma aplicação desktop, desenvolvida em Python, com interface gráfica para monitoramento em tempo real de uma infraestrutura de containers Podman. A aplicação foi desenvolvida como trabalho da disciplina de Lógica de Programação em Python, utilizando como alvo de monitoramento a infraestrutura corporativa simulada desenvolvida na disciplina de Conteinerização e Orquestração (projeto `projeto-iac`), integrando o conteúdo de ambas as disciplinas em uma única solução funcional.

A aplicação permite visualizar, em tempo real, o estado de cada container (em execução ou parado), o consumo de CPU e memória, além de oferecer controles para iniciar, parar e reiniciar containers diretamente pela interface gráfica.

## 2. Objetivos

O desenvolvimento deste projeto teve como objetivo aplicar, de forma prática e integrada, os principais tópicos abordados na ementa da disciplina:

- Variáveis, tipos de dados e estruturas de dados (listas, dicionários, conjuntos, tuplas)
- Estruturas de condição (`if`/`elif`/`else`, `match`/`case`)
- Estruturas de repetição (`while`, `for`, `continue`)
- Funções e expressões `lambda`
- Manipulação de arquivos (leitura e escrita)
- Tratamento de exceções (`try`/`except`/`else`/`finally`, `raise`)
- Registro de eventos (módulo `logging`)
- Programação orientada a objetos (classes, encapsulamento)
- Utilização de bibliotecas externas (interface gráfica, gráficos, monitoramento de sistema)
- Concorrência (`threading`) e comunicação segura entre threads (`queue`)

## 3. Arquitetura do Sistema

A aplicação é estruturada em duas linhas de execução (threads) que operam de forma independente e se comunicam por meio de uma fila (`queue.Queue`):

```
┌────────────────────┐      queue.Queue()      ┌─────────────────────┐
│  THREAD DE COLETA   │ ──────────────────────▶ │  THREAD PRINCIPAL    │
│  (segundo plano)     │                         │  (interface gráfica)  │
│                      │                         │                       │
│  • podman ps -a      │                         │  • lê a fila a cada   │
│  • podman stats      │                         │    500ms              │
│  • podman top        │                         │  • atualiza a tabela  │
│  • psutil (host)      │                         │  • redesenha o gráfico│
└────────────────────┘                         └─────────────────────┘
```

A separação em duas threads é necessária porque os comandos executados via `subprocess` (chamadas ao Podman) podem levar tempo para responder. Caso essa espera ocorresse na mesma thread responsável pela interface gráfica, a janela ficaria momentaneamente sem resposta a cada ciclo de atualização. A thread de coleta roda em segundo plano, depositando os dados coletados em uma fila; a thread principal apenas consome essa fila em intervalos curtos e atualiza os elementos visuais, sem nunca aguardar diretamente a resposta de um comando externo.

## 4. Tecnologias e Bibliotecas Utilizadas

| Biblioteca | Tipo | Finalidade |
|---|---|---|
| `customtkinter` | Externa | Construção da interface gráfica |
| `matplotlib` | Externa | Renderização do gráfico de uso de CPU em tempo real |
| `psutil` | Externa | Coleta de métricas do sistema operacional hospedeiro |
| `subprocess` | Padrão | Execução de comandos do Podman |
| `json` | Padrão | Interpretação da saída estruturada do Podman |
| `threading` | Padrão | Execução concorrente da coleta de dados |
| `queue` | Padrão | Comunicação segura entre threads |
| `logging` | Padrão | Registro de eventos da aplicação |
| `csv` | Padrão | Exportação de dados estruturados |
| `dataclasses` | Padrão | Definição de estruturas de dados simplificadas |
| `collections.deque` | Padrão | Manutenção de um histórico de tamanho fixo para o gráfico |

## 5. Estrutura do Projeto

```
python-monitor/
│
├── main.py              # Ponto de entrada da aplicação
├── app.py                # Interface gráfica e orquestração da aplicação
├── podman_client.py       # Camada de comunicação com o Podman
├── charts.py              # Componente de gráfico em tempo real
├── logger_config.py       # Configuração do sistema de registro de eventos
├── requirements.txt       # Dependências externas do projeto
├── exports/                # Diretório de destino dos arquivos CSV exportados
└── monitor.log              # Arquivo de log gerado em tempo de execução
```

## 6. Descrição dos Módulos

### 6.1 `main.py`

Ponto de entrada da aplicação. É responsável por inicializar o sistema de registro de eventos, verificar a disponibilidade do comando `podman` no sistema operacional e, em caso afirmativo, instanciar e executar a interface gráfica. A verificação prévia da disponibilidade do Podman evita que a aplicação seja iniciada em um ambiente sem os pré-requisitos necessários, apresentando uma mensagem de erro compreensível em vez de uma exceção não tratada.

### 6.2 `podman_client.py`

Módulo responsável exclusivamente pela comunicação com o Podman, sem qualquer dependência da interface gráfica — caracterizando uma separação de responsabilidades. A comunicação ocorre por meio do módulo `subprocess`, invocando os comandos do Podman e interpretando a saída no formato JSON.

Principais funções:

- `list_containers()`: retorna a lista de containers existentes, representados por instâncias da classe `ContainerInfo` (uma `dataclass`).
- `unique_states(containers)`: retorna um conjunto (`set`) com os estados distintos presentes na lista de containers, sem repetição.
- `get_stats(name)`: retorna as métricas de uso de CPU e memória de um container específico.
- `_cpu_percent_via_top(name)`: calcula o uso de CPU somando o percentual de cada processo individual do container, utilizado como fonte alternativa de dados (ver seção 11).
- `start_container`, `stop_container`, `restart_container`: controlam o ciclo de vida de um container.

O módulo define também duas exceções customizadas, `PodmanNotFoundError` e `PodmanCommandError`, permitindo que falhas sejam tratadas de forma específica pelas camadas superiores da aplicação.

### 6.3 `charts.py`

Define a classe `LiveChart`, responsável por renderizar um gráfico de linha em tempo real utilizando a biblioteca `matplotlib`, embutido na interface gráfica. O histórico de valores é mantido em uma estrutura `deque` com tamanho máximo fixo, de forma que apenas as últimas trinta amostras permaneçam visíveis, evitando crescimento indefinido de memória e mantendo a legibilidade do gráfico. O eixo vertical do gráfico ajusta seu limite superior dinamicamente quando o valor de CPU monitorado excede o teto atual.

### 6.4 `app.py`

Módulo principal da interface gráfica, contendo a classe `MonitorApp`. Reúne três responsabilidades centrais: a construção dos elementos visuais, a coleta periódica de dados em uma thread separada, e o tratamento das interações do usuário (seleção de containers, botões de controle, exportação de dados).

Funcionalidades de destaque implementadas neste módulo:

- Estrutura de condição `match`/`case` para o despacho das ações de iniciar, parar e reiniciar um container.
- Comunicação entre threads via `queue.Queue`, evitando acesso concorrente direto aos elementos da interface gráfica.
- Exportação de dados para arquivo CSV, implementada com a sequência completa de blocos `try`/`except`/`else`/`finally`.
- Leitura do arquivo de log persistido em disco, demonstrando a operação complementar à exportação (escrita seguida de leitura de arquivo).

### 6.5 `logger_config.py`

Configura o sistema de registro de eventos da aplicação utilizando o módulo padrão `logging`. São definidos dois manipuladores (*handlers*) distintos: um manipulador de arquivo, que registra todas as mensagens, incluindo as de nível `DEBUG`; e um manipulador de console, que exibe apenas mensagens de nível `INFO` ou superior, evitando a poluição visual do terminal durante a utilização normal da aplicação.

## 7. Instalação

Os passos a seguir devem ser executados em ambiente Linux (ou WSL, no caso de sistemas Windows) com Python 3.10 ou superior instalado.

### 7.1 Pré-requisito: infraestrutura monitorada

Esta aplicação monitora os containers definidos no projeto `projeto-iac`. É necessário que essa infraestrutura esteja em execução antes de utilizar o painel.

```bash
git clone https://github.com/RainerJustiniano/projeto-iac.git
cd projeto-iac
bash setup.sh
```

**Verificação:**
```bash
podman ps -a
```
Devem ser exibidos cinco containers (`dns`, `adminsrv`, `worksrv`, `datastore`, `client`), todos com status "Up".

### 7.2 Clonagem do repositório

```bash
git clone https://github.com/RainerJustiniano/python-monitor.git
cd python-monitor
```

### 7.3 Instalação do Tkinter e do gerenciador de pacotes Python (dependências de sistema)

O `customtkinter` depende do `tkinter`, que é um pacote de sistema e não é instalado automaticamente pelo gerenciador de pacotes Python (`pip`). Em algumas instalações mínimas (comum em distribuições Linux recentes, como Ubuntu 25.x), o próprio `pip` também não vem pré-instalado.

```bash
sudo apt update
sudo apt install -y python3-tk python3-pip
```

**Verificação:**
```bash
python3 -c "import tkinter; print('tkinter OK')"
pip --version
```
A primeira saída esperada é `tkinter OK`; a segunda deve exibir o número de versão do `pip`, sem erro de "command not found". Caso ocorra um erro nesta etapa, a aplicação não poderá ser iniciada.

### 7.4 Instalação das dependências Python

```bash
pip install -r requirements.txt --break-system-packages
```

**Verificação:**
```bash
python3 -c "import customtkinter, matplotlib, psutil; print('Bibliotecas OK')"
```
A saída esperada é `Bibliotecas OK`.

## 8. Execução

```bash
python3 main.py
```

Ao ser executada, a aplicação verifica a disponibilidade do Podman, inicia o sistema de registro de eventos, e abre a janela principal exibindo a tabela de containers, atualizada automaticamente em intervalos de quatro segundos.

## 9. Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| Listagem de containers | Tabela com nome, status, uso de CPU, memória e portas, atualizada automaticamente |
| Seleção de container | Exibe detalhes e gráfico de CPU em tempo real do container selecionado |
| Controle de containers | Botões para iniciar, parar e reiniciar o container selecionado |
| Exportação de dados | Geração de arquivo CSV com o estado atual de todos os containers |
| Consulta de log | Leitura e exibição das últimas linhas do arquivo de log da aplicação |
| Métricas do host | Exibição do uso de CPU e memória da própria máquina, via `psutil` |
| Atualização manual | Botão para forçar uma nova coleta de dados sem aguardar o intervalo automático |

## 10. Testes e Validação

A camada de comunicação com o Podman (`podman_client.py`) foi validada por meio de testes com dados simulados (*mocks*), cobrindo os seguintes cenários:

- Listagem de containers em execução e parados, com e sem portas mapeadas
- Filtragem de registros malformados (ausência do campo identificador)
- Interpretação de diferentes formatos de retorno do comando `podman stats`
- Comportamento da função de estatísticas quando o container não possui dados disponíveis

A interface gráfica foi validada de ponta a ponta utilizando um servidor de display virtual (Xvfb), com containers reais em execução, confirmando:

- Preenchimento correto da tabela de containers
- Atualização periódica dos dados via thread e fila
- Funcionamento dos controles de iniciar e parar containers
- Geração e leitura correta dos arquivos exportados
- Atualização das métricas do host tanto no ciclo automático quanto na atualização manual

## 11. Limitações e Observações Técnicas

### 11.1 Subestimação do uso de CPU pelo comando `podman stats`

Em ambientes Podman configurados em modo *rootless*, com o gerenciador de cgroups operando em modo "hybrid", observou-se que o comando `podman stats` pode subestimar significativamente o uso de CPU quando processos adicionais são criados dentro do container por meio do comando `podman exec -d`. Em um cenário de teste com cinco processos consumindo aproximadamente 73% de CPU cada (confirmado via `podman top`), o `podman stats` reportou apenas 3,75% de uso total.

Como correção, a função `get_stats()` calcula o uso de CPU por dois métodos distintos — pelo `podman stats` tradicional e pela soma do percentual individual de cada processo via `podman top` — e adota o maior valor entre os dois resultados, corrigindo a subestimação sem comprometer o funcionamento em ambientes onde o `podman stats` opera corretamente.

### 11.2 Compatibilidade com ambientes sem suporte gráfico

A aplicação requer um ambiente com suporte a interface gráfica (servidor X ou equivalente). Em ambientes WSL, isso depende do WSLg, disponibilizado por padrão em instalações recentes do Windows 11. A aplicação não é compatível com ambientes de execução em nuvem sem suporte gráfico, como o GitHub Codespaces, uma vez que estes não possuem acesso à infraestrutura Podman monitorada nem a um servidor de exibição gráfica.

## 12. Conclusão

O projeto demonstra a aplicação prática de conceitos fundamentais e avançados da linguagem Python em um cenário de monitoramento de infraestrutura real, integrando programação orientada a objetos, concorrência, tratamento de exceções, manipulação de arquivos e utilização de bibliotecas externas em uma solução funcional e validada. A escolha de monitorar uma infraestrutura previamente desenvolvida em outra disciplina permitiu a integração de conhecimentos de duas áreas distintas — conteinerização e desenvolvimento de software — em um único projeto coeso.

---

*Trabalho desenvolvido para a disciplina de Lógica de Programação em Python — Instituto Federal de Mato Grosso, Campus Cuiabá.*
