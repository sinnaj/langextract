-- PostgreSQL Schema for Norm Ingestion Pipeline
-- Copyright 2025 - Norm Storage and DNF Logic Schema

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enums
CREATE TYPE obligation_type AS ENUM ('MANDATORY','RECOMMENDED','OPTIONAL');
CREATE TYPE clause_type AS ENUM ('APPLIES_IF','SATISFIED_IF','EXEMPT_IF');
CREATE TYPE value_type AS ENUM ('BOOLEAN','INTEGER','NUMERIC','STRING','ENUM','ARRAY','JSON');
CREATE TYPE logic_op AS ENUM ('AND','OR');
CREATE TYPE cmp_op AS ENUM ('EQ','NEQ','GT','GTE','LT','LTE','IN','NOT_IN','CONTAINS','NOT_CONTAINS');

-- Optional scaffolding
CREATE TABLE documents (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title            TEXT,
  jurisdiction     TEXT,
  language         TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sections (
  id               TEXT PRIMARY KEY,
  document_id      UUID REFERENCES documents(id),
  parent_section_id TEXT REFERENCES sections(id),
  paragraph_number TEXT
);

-- Core
CREATE TABLE norms (
  id                  UUID PRIMARY KEY,
  document_id         UUID REFERENCES documents(id),
  section_id          TEXT REFERENCES sections(id),
  extraction_class    TEXT NOT NULL,
  extraction_text     TEXT NOT NULL,
  obligation          obligation_type,
  norm_statement      TEXT,
  applies_if_text     TEXT,
  satisfied_if_text   TEXT,
  exempt_if_text      TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE topics (
  id   SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL
);

CREATE TABLE norm_topics (
  norm_id  UUID REFERENCES norms(id) ON DELETE CASCADE,
  topic_id INT  REFERENCES topics(id) ON DELETE CASCADE,
  PRIMARY KEY (norm_id, topic_id)
);

CREATE TABLE questions (
  id           SERIAL PRIMARY KEY,
  key          TEXT UNIQUE NOT NULL,
  label        TEXT,
  value_hint   value_type,
  allowed_enum TEXT[]
);
CREATE INDEX idx_questions_key_trgm ON questions USING GIN (key gin_trgm_ops);

CREATE TABLE norm_clause_groups (
  id           BIGSERIAL PRIMARY KEY,
  norm_id      UUID REFERENCES norms(id) ON DELETE CASCADE,
  clause       clause_type NOT NULL,
  parent_id    BIGINT REFERENCES norm_clause_groups(id) ON DELETE CASCADE,
  logic        logic_op NOT NULL DEFAULT 'AND'
);

CREATE TABLE norm_requirements (
  id             BIGSERIAL PRIMARY KEY,
  norm_id        UUID REFERENCES norms(id) ON DELETE CASCADE,
  clause         clause_type NOT NULL,
  group_id       BIGINT REFERENCES norm_clause_groups(id) ON DELETE SET NULL,
  question_id    INT REFERENCES questions(id) ON DELETE RESTRICT,
  operator       cmp_op NOT NULL DEFAULT 'EQ',
  expected_type  value_type NOT NULL,
  expected_value JSONB NOT NULL,
  UNIQUE (norm_id, clause, question_id, operator, expected_value)
);

CREATE INDEX idx_normreq_norm_clause ON norm_requirements (norm_id, clause);
CREATE INDEX idx_normreq_question ON norm_requirements (question_id);
CREATE INDEX idx_normreq_expected_gin ON norm_requirements USING GIN (expected_value jsonb_path_ops);
