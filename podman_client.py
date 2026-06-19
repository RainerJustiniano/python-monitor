"""
podman_client.py
=================
Camada de acesso ao Podman via subprocess + JSON.

Demonstra:
- Módulo `subprocess` (chamadas de comandos externos)
- Módulo `json` (parsing de dados estruturados)
- Tratamento de exceções (try/except, exceções customizadas)
- Funções puras com tipos (type hints) e docstrings
- Estruturas de dados (listas de dicionários)
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional


class PodmanNotFoundError(Exception):
    """Lançada quando o comando 'podman' não está instalado/disponível."""


class PodmanCommandError(Exception):
    """Lançada quando um comando podman retorna erro (exit code != 0)."""


@dataclass
class ContainerInfo:
    """Representa o estado de um container em um instante de tempo."""
    name: str
    image: str
    status: str
    state: str
    ports: str = ""
    cpu_percent: float = 0.0
    mem_usage: str = "—"
    mem_percent: float = 0.0
    ip_address: str = "—"


def _check_podman_installed() -> None:
    """Verifica se o binário podman existe no PATH antes de qualquer chamada."""
    if shutil.which("podman") is None:
        raise PodmanNotFoundError(
            "O comando 'podman' não foi encontrado no PATH. "
            "Verifique se o Podman está instalado (sudo apt install podman)."
        )


def _run(args: list[str], timeout: int = 10) -> str:
    """
    Executa um comando podman e retorna sua saída (stdout) como string.
    Levanta PodmanCommandError em caso de falha.
    """
    _check_podman_installed()
    try:
        result = subprocess.run(
            ["podman", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise PodmanCommandError(f"Comando expirou (timeout): {' '.join(args)}") from exc

    if result.returncode != 0:
        raise PodmanCommandError(result.stderr.strip() or "Erro desconhecido ao executar podman")

    return result.stdout


def list_containers() -> list[ContainerInfo]:
    """
    Lista todos os containers (rodando ou parados) usando 'podman ps -a --format json'.
    Retorna uma lista de objetos ContainerInfo.
    """
    raw = _run(["ps", "-a", "--format", "json"])
    if not raw.strip():
        return []

    data = json.loads(raw)
    containers: list[ContainerInfo] = []

    for item in data:
        # Registros sem "Id" são malformados/inválidos — pula para o
        # próximo item da lista em vez de tentar processar dados quebrados
        if not item.get("Id"):
            continue

        # Podman retorna o nome dentro de uma lista ["adminsrv"]
        names = item.get("Names", ["?"])
        name = names[0] if isinstance(names, list) else str(names)

        ports_list = item.get("Ports", [])
        ports = ", ".join(
            f"{p.get('host_port', '?')}->{p.get('container_port', '?')}"
            for p in ports_list
        ) if ports_list else "—"

        containers.append(
            ContainerInfo(
                name=name,
                image=item.get("Image", "?"),
                status=item.get("Status", "?"),
                state=item.get("State", "unknown"),
                ports=ports,
            )
        )

    return containers


def unique_states(containers: list[ContainerInfo]) -> set[str]:
    """
    Retorna o CONJUNTO (set) de estados distintos presentes na lista de
    containers — ex.: {"running", "exited"}. Um set é ideal aqui porque
    não nos importa quantos containers estão em cada estado, só QUAIS
    estados diferentes existem no momento, sem repetição.
    """
    return {c.state for c in containers}


def get_stats(name: str) -> Optional[dict]:
    """
    Retorna estatísticas de uso (CPU%, memória) de um container em execução.
    Usa 'podman stats --no-stream --format json'.
    Retorna None se o container não estiver rodando (não há stats para parado).
    """
    try:
        raw = _run(["stats", "--no-stream", "--format", "json", name], timeout=5)
    except PodmanCommandError:
        return None

    if not raw.strip():
        return None

    data = json.loads(raw)
    if not data:
        return None

    stat = data[0]

    # Campos retornados pelo podman variam de versão para versão;
    # tratamos ambos os formatos comuns (CamelCase e snake_case).
    cpu_raw = stat.get("CPU", stat.get("cpu_percent", "0%"))
    mem_usage = stat.get("MemUsage", stat.get("mem_usage", "—"))
    mem_perc_raw = stat.get("MemPerc", stat.get("mem_percent", "0%"))

    cpu_from_stats = _parse_percent(cpu_raw)
    cpu_from_top = _cpu_percent_via_top(name)

    # 'podman stats' pode subestimar o uso de CPU em ambientes Podman
    # rootless com cgroups em modo "hybrid" — processos criados via
    # 'podman exec -d' às vezes não são contabilizados corretamente.
    # 'podman top' lê direto de /proc por processo e é mais confiável
    # nesse cenário. Usamos o MAIOR dos dois números, assim continuamos
    # corretos em ambientes onde 'stats' funciona normalmente, e também
    # corretos onde ele subestima.
    cpu_percent = max(cpu_from_stats, cpu_from_top)

    return {
        "cpu_percent": cpu_percent,
        "mem_usage": mem_usage,
        "mem_percent": _parse_percent(mem_perc_raw),
    }


def _cpu_percent_via_top(name: str) -> float:
    """
    Soma o %CPU de TODOS os processos dentro do container, usando
    'podman top' (duas colunas: pid e pcpu) em vez de 'podman stats'.
    Serve como fonte alternativa quando 'podman stats' não reflete
    processos extras (ex.: criados via 'podman exec -d').
    """
    try:
        raw = _run(["top", name, "pid", "pcpu"], timeout=5)
    except PodmanCommandError:
        return 0.0

    total = 0.0
    linhas = raw.strip().splitlines()
    for linha in linhas[1:]:  # a primeira linha é o cabeçalho "PID PCPU"
        partes = linha.split()
        if len(partes) < 2:
            continue
        try:
            total += float(partes[1])
        except ValueError:
            continue

    return total


def _parse_percent(value) -> float:
    """Converte strings como '12.34%' em float (12.34). Tolerante a erros."""
    try:
        return float(str(value).replace("%", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def inspect_ip(name: str) -> str:
    """Retorna o(s) endereço(s) IP do container, ou '—' se não disponível."""
    try:
        raw = _run(["inspect", name, "--format", "{{.NetworkSettings.Networks}}"])
        return raw.strip() or "—"
    except PodmanCommandError:
        return "—"


def start_container(name: str) -> str:
    """Inicia um container parado. Retorna mensagem de resultado."""
    _run(["start", name])
    return f"Container '{name}' iniciado com sucesso."


def stop_container(name: str) -> str:
    """Para um container em execução. Retorna mensagem de resultado."""
    _run(["stop", name])
    return f"Container '{name}' parado com sucesso."


def restart_container(name: str) -> str:
    """Reinicia um container. Retorna mensagem de resultado."""
    _run(["restart", name])
    return f"Container '{name}' reiniciado com sucesso."
