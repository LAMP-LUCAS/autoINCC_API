-- ==============================================================================
-- AutoINCC - PostgreSQL Star Schema DDL Script
-- ==============================================================================

-- 1. Dimensão Temporal (dim_tempo)
CREATE TABLE IF NOT EXISTS dim_tempo (
    data_id DATE PRIMARY KEY,
    ano INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    trimestre INTEGER NOT NULL,
    semestre INTEGER NOT NULL,
    nome_mes VARCHAR(20) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dim_tempo_ano ON dim_tempo (ano);
CREATE INDEX IF NOT EXISTS idx_dim_tempo_ano_mes ON dim_tempo (ano, mes);

-- 2. Dimensão de Categorias (dim_categoria)
CREATE TABLE IF NOT EXISTS dim_categoria (
    categoria_id SERIAL PRIMARY KEY,
    nome_categoria VARCHAR(100) UNIQUE NOT NULL,
    descricao TEXT
);

-- 3. Dimensão Geográfica (dim_geografia)
CREATE TABLE IF NOT EXISTS dim_geografia (
    cidade_id SERIAL PRIMARY KEY,
    nome_cidade VARCHAR(100) NOT NULL,
    uf VARCHAR(2) NOT NULL
);

-- 4. Dimensão de Tipos de Índice (dim_tipo_indice)
CREATE TABLE IF NOT EXISTS dim_tipo_indice (
    tipo_id SERIAL PRIMARY KEY,
    sigla VARCHAR(20) UNIQUE NOT NULL,
    fonte VARCHAR(50) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dim_tipo_indice_sigla ON dim_tipo_indice (sigla);

-- 5. Tabela Fato (fato_incc)
CREATE TABLE IF NOT EXISTS fato_incc (
    data_id DATE NOT NULL REFERENCES dim_tempo(data_id) ON DELETE CASCADE,
    categoria_id INTEGER NOT NULL REFERENCES dim_categoria(categoria_id) ON DELETE CASCADE,
    cidade_id INTEGER NOT NULL REFERENCES dim_geografia(cidade_id) ON DELETE CASCADE,
    tipo_id INTEGER NOT NULL REFERENCES dim_tipo_indice(tipo_id) ON DELETE CASCADE,
    variacao_mensal NUMERIC(10, 6) NOT NULL,
    variacao_ytd NUMERIC(10, 6),
    variacao_12m NUMERIC(10, 6),
    numero_indice NUMERIC(28, 6) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (data_id, categoria_id, cidade_id, tipo_id)
);

CREATE INDEX IF NOT EXISTS idx_fato_incc_tipo_data ON fato_incc (tipo_id, data_id DESC);

-- ==============================================================================
-- Carga Inicial de Dimensões Padrão (Seed)
-- ==============================================================================

INSERT INTO dim_categoria (categoria_id, nome_categoria, descricao)
VALUES (1, 'Geral', 'Índice Geral do INCC consolidado')
ON CONFLICT (categoria_id) DO NOTHING;

INSERT INTO dim_geografia (cidade_id, nome_cidade, uf)
VALUES (1, 'Nacional', 'BR')
ON CONFLICT (cidade_id) DO NOTHING;

INSERT INTO dim_tipo_indice (tipo_id, sigla, fonte)
VALUES 
    (1, 'INCC-M', 'BCB SGS'),
    (2, 'INCC-DI', 'BCB SGS')
ON CONFLICT (tipo_id) DO NOTHING;
