-- Esquemas e tabelas base. Idempotente.
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS clean;
CREATE SCHEMA IF NOT EXISTS quarantine;
CREATE SCHEMA IF NOT EXISTS meta;

-- Camada raw: cada linha do CSV como veio, em jsonb, com a linha de origem.
CREATE TABLE IF NOT EXISTS raw.registros (
    arquivo       text    NOT NULL,
    linha_origem  integer NOT NULL,
    lote_sha256   text    NOT NULL,
    dados         jsonb   NOT NULL,
    PRIMARY KEY (arquivo, linha_origem, lote_sha256)
);

-- Linhas rejeitadas com o motivo.
CREATE TABLE IF NOT EXISTS quarantine.registros (
    arquivo         text    NOT NULL,
    linha_origem    integer NOT NULL,
    lote_sha256     text    NOT NULL,
    motivo          text    NOT NULL,
    id_sobrevivente text,
    dados           jsonb   NOT NULL,
    PRIMARY KEY (arquivo, linha_origem, lote_sha256)
);

CREATE TABLE IF NOT EXISTS meta.ingest_log (
    id                 serial PRIMARY KEY,
    arquivo            text        NOT NULL,
    sha256             text        NOT NULL,
    linhas_lidas       integer     NOT NULL,
    linhas_ok          integer     NOT NULL,
    linhas_quarentena  integer     NOT NULL,
    executado_em       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (arquivo, sha256)
);

CREATE TABLE IF NOT EXISTS meta.relatorio_qualidade (
    id           serial PRIMARY KEY,
    gerado_em    timestamptz NOT NULL DEFAULT now(),
    relatorio    jsonb       NOT NULL
);

-- Copia persistente dos vetores do Chroma. O indice do Chroma vive no container e some a cada deploy;
-- no boot ele e restaurado daqui, sem chamar a API de embeddings.
CREATE TABLE IF NOT EXISTS meta.vetores (
    backend    text NOT NULL,
    chunk_id   text NOT NULL,
    documento  text NOT NULL,
    metadata   jsonb NOT NULL,
    vetor      double precision[] NOT NULL,
    PRIMARY KEY (backend, chunk_id)
);

CREATE TABLE IF NOT EXISTS meta.dicionario (
    objeto    text NOT NULL,
    coluna    text NOT NULL DEFAULT '',
    tipo      text,
    descricao text NOT NULL,
    PRIMARY KEY (objeto, coluna)
);

CREATE TABLE IF NOT EXISTS clean.dim_vendedor (
    id_vendedor    text PRIMARY KEY,
    nome           text NOT NULL,
    email          text,
    telefone       text,
    uf             char(2),
    data_admissao  date,
    meta_mensal    numeric(12,2),
    comissao_pct   numeric(5,2),
    status         text,
    supervisor     text,
    flags          text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS clean.dim_comprador (
    id_comprador    text PRIMARY KEY,
    razao_social    text NOT NULL,
    cnpj            text,
    cidade          text,
    uf              char(2),
    segmento        text,
    porte           text,
    contato         text,
    email           text,
    data_cadastro   date,
    limite_credito  numeric(14,2),
    status          text,
    flags           text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS clean.dim_vendedor_alias (
    id_descartado   text PRIMARY KEY,
    id_sobrevivente text NOT NULL REFERENCES clean.dim_vendedor (id_vendedor)
);

CREATE TABLE IF NOT EXISTS clean.dim_comprador_alias (
    id_descartado   text PRIMARY KEY,
    id_sobrevivente text NOT NULL REFERENCES clean.dim_comprador (id_comprador)
);

CREATE TABLE IF NOT EXISTS clean.fato_venda (
    id_venda               text PRIMARY KEY,
    data                   date NOT NULL CHECK (data BETWEEN DATE '2020-01-01' AND DATE '2024-12-31'),
    id_vendedor            text NOT NULL REFERENCES clean.dim_vendedor (id_vendedor),
    id_comprador           text NOT NULL REFERENCES clean.dim_comprador (id_comprador),
    produto                text,
    produto_original       text,
    categoria              text,
    categoria_produto      text,
    quantidade             integer NOT NULL CHECK (quantidade > 0),
    valor_unitario         numeric(12,2) NOT NULL CHECK (valor_unitario > 0),
    desconto               numeric(5,4),
    valor_total            numeric(14,2) NOT NULL,
    valor_liquido          numeric(14,2) NOT NULL,
    valor_total_informado  numeric(14,2),
    status                 text NOT NULL CHECK (status IN ('concluida','cancelada','devolvida','pendente')),
    uf                     char(2),
    observacoes            text,
    flags                  text[] NOT NULL DEFAULT '{}',
    linha_origem           integer
);

CREATE TABLE IF NOT EXISTS clean.estoque (
    id_produto            text PRIMARY KEY,
    nome_produto          text NOT NULL,
    categoria             text,
    estoque_atual         integer CHECK (estoque_atual >= 0),
    estoque_minimo        integer,
    ultima_reposicao      date,
    lead_time_dias        integer,
    fornecedor            text,
    custo_unitario        numeric(12,2),
    localizacao_deposito  text,
    status                text,
    flags                 text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS clean.decisao (
    id_decisao          text PRIMARY KEY,
    data                date,
    tipo                text,
    descricao           text,
    responsavel         text,
    impacto             text,
    resultado           text,
    observacoes         text,
    suspeita_injection  boolean NOT NULL DEFAULT false,
    padroes_injection   text[] NOT NULL DEFAULT '{}',
    flags               text[] NOT NULL DEFAULT '{}'
);
