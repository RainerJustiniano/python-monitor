"""
main.py
=======
Ponto de entrada da aplicação.

Painel de Monitoramento — Infraestrutura Corporativa (projeto-iac)
Trabalho da disciplina de Lógica de Programação em Python.

Execução:
    python3 main.py
"""

import shutil
import sys

from logger_config import setup_logger


def main() -> int:
    logger = setup_logger()

    if shutil.which("podman") is None:
        print(
            "\n❌ O comando 'podman' não foi encontrado.\n"
            "   Instale com: sudo apt install -y podman\n"
            "   Este painel depende do Podman para monitorar os containers.\n"
        )
        logger.error("Podman não encontrado no PATH — encerrando aplicação.")
        return 1

    try:
        from app import MonitorApp
        app = MonitorApp(logger)
        app.mainloop()
    except Exception as exc:
        logger.exception(f"Erro fatal na aplicação: {exc}")
        print(f"\n❌ Erro ao iniciar a aplicação: {exc}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
