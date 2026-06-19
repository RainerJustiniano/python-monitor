"""
logger_config.py
=================
Configura o sistema de logging da aplicação.

Demonstra:
- Módulo padrão `logging` (registro de eventos)
- Manipulação de arquivos (escreve em monitor.log)
- Formatação de strings com timestamp
"""

import logging
import os
from datetime import datetime

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "monitor.log")


def setup_logger(name: str = "monitor") -> logging.Logger:
    """
    Cria e configura um logger que escreve simultaneamente:
    - no arquivo monitor.log (persistente, para auditoria)
    - no console (para debug durante o desenvolvimento)

    Retorna o objeto Logger já configurado, pronto para uso.
    """
    logger = logging.getLogger(name)
    # O logger em si aceita o nível mais detalhado (DEBUG); cada handler
    # decide, individualmente, o que realmente vai exibir/gravar.
    logger.setLevel(logging.DEBUG)

    # Evita duplicar handlers se a função for chamada mais de uma vez
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de arquivo — grava TUDO, incluindo mensagens de debug
    # (detalhes técnicos úteis para investigar problemas depois,
    # mas que poluiriam o console durante o uso normal)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    # Handler de console — só mostra INFO ou mais grave (sem debug)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    logger.info("=" * 60)
    logger.info(f"Sessão iniciada em {datetime.now():%d/%m/%Y %H:%M:%S}")
    logger.info("=" * 60)

    return logger
