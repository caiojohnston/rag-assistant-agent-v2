"""Pipeline de carga: limpa os CSV, grava no Postgres, gera o relatorio de qualidade.

Uso:
    python -m cristalux.pipeline.run            # carga normal (pula arquivos ja ingeridos)
    python -m cristalux.pipeline.run --force    # reprocessa mesmo que o hash seja conhecido
    python -m cristalux.pipeline.run --sem-banco  # so limpeza e relatorio, sem Postgres
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from cristalux.cleaning import parsers as p
from cristalux.cleaning.base import ler_csv
from cristalux.cleaning.decisoes import limpar_decisoes
from cristalux.cleaning.entidades import limpar_compradores, limpar_vendedores
from cristalux.cleaning.estoque import limpar_estoque
from cristalux.cleaning.quality import formatos_de_data, gerar_relatorio, perfil_arquivo, salvar
from cristalux.cleaning.vendas import limpar_vendas
from cristalux.config import settings
from cristalux.db import load
from cristalux.db.setup import conectar, setup

log = logging.getLogger("cristalux.pipeline")

ARQUIVOS = ["compradores", "vendedores", "estoque_logistica", "decisoes", "vendas"]


def limpar_tudo(data_dir: Path, ids_vendedor_extra=(), ids_comprador_extra=(), alias_vendedor=None, alias_comprador=None):
    """Roda toda a limpeza em memoria. Devolve (raws, resultados)."""
    raws = {n: ler_csv(data_dir / f"{n}.csv") for n in ARQUIVOS}
    res = {
        "compradores": limpar_compradores(raws["compradores"]),
        "vendedores": limpar_vendedores(raws["vendedores"]),
        "estoque_logistica": limpar_estoque(raws["estoque_logistica"]),
        "decisoes": limpar_decisoes(raws["decisoes"]),
    }
    vendedores = set(res["vendedores"].clean["id_vendedor"]) | set(ids_vendedor_extra)
    compradores = set(res["compradores"].clean["id_comprador"]) | set(ids_comprador_extra)
    res["vendas"] = limpar_vendas(
        raws["vendas"], vendedores, compradores,
        {**(alias_vendedor or {}), **res["vendedores"].stats["alias"]},
        {**(alias_comprador or {}), **res["compradores"].stats["alias"]})
    return raws, res


def _extras(raws: dict, res: dict) -> dict[str, dict]:
    """Medidas de grafias e formatos de data para o relatorio de qualidade."""
    v, c, e = raws["vendas"], raws["compradores"], raws["estoque_logistica"]
    vc = res["vendas"].clean
    return {
        "vendas": {
            "formatos_data": formatos_de_data(v["data"]),
            "variantes": {
                "regiao": (v["regiao"].map(p.limpar).dropna().nunique(), v["regiao"].map(p.parse_uf).dropna().nunique()),
                "status": (v["status"].map(p.limpar).dropna().nunique(), v["status"].map(p.parse_status_venda).dropna().nunique()),
                "produto": (v["produto"].map(p.limpar).dropna().nunique(), v["produto"].map(p.parse_produto).dropna().nunique()),
                "categoria": (v["categoria"].map(p.limpar).dropna().nunique(), v["categoria"].map(p.parse_categoria).dropna().nunique()),
            },
        },
        "compradores": {
            "formatos_data": formatos_de_data(c["data_cadastro"]),
            "variantes": {
                "estado": (c["estado"].map(p.limpar).dropna().nunique(), c["estado"].map(p.parse_uf).dropna().nunique()),
                "segmento": (c["segmento"].map(p.limpar).dropna().nunique(), res["compradores"].clean["segmento"].nunique()),
                "porte": (c["porte"].map(p.limpar).dropna().nunique(), res["compradores"].clean["porte"].nunique()),
            },
        },
        "vendedores": {"formatos_data": formatos_de_data(raws["vendedores"]["data_admissao"]), "variantes": {
            "regiao": (raws["vendedores"]["regiao"].map(p.limpar).dropna().nunique(),
                       raws["vendedores"]["regiao"].map(p.parse_uf).dropna().nunique())}},
        "estoque_logistica": {"formatos_data": formatos_de_data(e["ultima_reposicao"]), "variantes": {}},
        "decisoes": {"formatos_data": formatos_de_data(raws["decisoes"]["data"]), "variantes": {}},
        "_vendas_limpas": len(vc),
    }


def relatorio_qualidade(raws: dict, res: dict) -> dict:
    extras = _extras(raws, res)
    perfis = [perfil_arquivo(n, raws[n], res[n], extras.get(n)) for n in ARQUIVOS]
    return gerar_relatorio(perfis)


def executar(data_dir: Path | None = None, force: bool = False, com_banco: bool = True) -> dict:
    data_dir = data_dir or settings.data_dir
    if not com_banco:
        raws, res = limpar_tudo(data_dir)
        rel = relatorio_qualidade(raws, res)
        salvar(rel, settings.reports_dir)
        return rel

    setup()
    with conectar() as conn:
        raws, res = limpar_tudo(
            data_dir,
            ids_vendedor_extra=load.ids_existentes(conn, "clean.dim_vendedor", "id_vendedor"),
            ids_comprador_extra=load.ids_existentes(conn, "clean.dim_comprador", "id_comprador"),
            alias_vendedor=load.aliases(conn, "clean.dim_vendedor_alias"),
            alias_comprador=load.aliases(conn, "clean.dim_comprador_alias"))
        salvar(relatorio_qualidade(raws, res), settings.reports_dir)

        # Dimensoes antes dos fatos por causa das chaves estrangeiras.
        etapas = [
            ("compradores", "clean.dim_comprador"), ("vendedores", "clean.dim_vendedor"),
            ("estoque_logistica", "clean.estoque"), ("decisoes", "clean.decisao"), ("vendas", "clean.fato_venda"),
        ]
        for arquivo, tabela in etapas:
            digest = load.sha256(data_dir / f"{arquivo}.csv")
            if not force and load.ja_ingerido(conn, arquivo, digest):
                log.info("%s: hash ja ingerido, pulando", arquivo)
                continue
            r = res[arquivo]
            load.gravar_clean(conn, tabela, r.clean)
            if arquivo == "compradores":
                load.gravar_alias(conn, "clean.dim_comprador_alias", r.stats["alias"])
            if arquivo == "vendedores":
                load.gravar_alias(conn, "clean.dim_vendedor_alias", r.stats["alias"])
            load.gravar_raw_e_quarentena(conn, arquivo, digest, raws[arquivo], r)
            load.registrar_ingestao(conn, arquivo, digest, r)
            log.info("%s: %s limpas, %s em quarentena", arquivo, r.stats["linhas_limpas"], r.stats["quarentena"])
        conn.commit()
    return {n: r.stats for n, r in res.items()}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sem-banco", action="store_true")
    a = ap.parse_args()
    out = executar(force=a.force, com_banco=not a.sem_banco)
    if a.sem_banco:
        print(f"relatorio salvo em {settings.reports_dir}")
    else:
        for nome, stats in out.items():
            print(nome, {k: v for k, v in stats.items() if k != "alias"})


if __name__ == "__main__":
    main()
