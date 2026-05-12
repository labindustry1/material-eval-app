-- Material evaluation production schema.
-- Tables live in a private schema and are intended for backend/service-role access first.

create schema if not exists material_eval;

create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;

create table if not exists material_eval.evaluation_runs (
    id uuid primary key default extensions.gen_random_uuid(),
    created_at timestamptz not null default now(),
    material_name text not null,
    domain text not null,
    part_name text not null,
    topology text not null,
    payload_json jsonb not null,
    report_markdown text not null
);

create table if not exists material_eval.documents (
    id uuid primary key default extensions.gen_random_uuid(),
    source text not null,
    source_path text not null,
    parser text not null,
    content_hash text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (source_path)
);

create table if not exists material_eval.document_chunks (
    id uuid primary key default extensions.gen_random_uuid(),
    document_id uuid not null references material_eval.documents(id) on delete cascade,
    chunk_index integer not null,
    text text not null,
    text_hash text not null,
    source text not null,
    parser text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (document_id, chunk_index)
);

create table if not exists material_eval.chunk_embeddings (
    id uuid primary key default extensions.gen_random_uuid(),
    chunk_id uuid not null references material_eval.document_chunks(id) on delete cascade,
    provider_name text not null,
    model_name text not null default 'BAAI/bge-m3',
    dimension integer not null default 1024,
    embedding extensions.vector(1024) not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (chunk_id, provider_name, model_name),
    check (dimension = 1024)
);

create table if not exists material_eval.report_reviews (
    id uuid primary key default extensions.gen_random_uuid(),
    run_id uuid not null references material_eval.evaluation_runs(id) on delete cascade,
    created_at timestamptz not null default now(),
    reviewer text not null,
    status text not null,
    comment text not null,
    metadata jsonb not null default '{}'::jsonb
);

alter table material_eval.evaluation_runs enable row level security;
alter table material_eval.documents enable row level security;
alter table material_eval.document_chunks enable row level security;
alter table material_eval.chunk_embeddings enable row level security;
alter table material_eval.report_reviews enable row level security;

create index if not exists evaluation_runs_created_at_idx
    on material_eval.evaluation_runs (created_at desc);

create index if not exists documents_source_path_idx
    on material_eval.documents (source_path);

create index if not exists documents_content_hash_idx
    on material_eval.documents (content_hash);

create index if not exists document_chunks_document_id_idx
    on material_eval.document_chunks (document_id, chunk_index);

create index if not exists document_chunks_text_hash_idx
    on material_eval.document_chunks (text_hash);

create index if not exists chunk_embeddings_chunk_id_provider_idx
    on material_eval.chunk_embeddings (chunk_id, provider_name, model_name);

create index if not exists chunk_embeddings_embedding_hnsw_idx
    on material_eval.chunk_embeddings
    using hnsw (embedding extensions.vector_cosine_ops);

create index if not exists report_reviews_run_id_idx
    on material_eval.report_reviews (run_id, created_at desc);

create or replace function material_eval.match_document_chunks(
    query_embedding extensions.vector(1024),
    match_count integer default 8,
    match_threshold double precision default 0.2,
    provider_name_filter text default 'bge-m3+dense',
    model_name_filter text default 'BAAI/bge-m3'
)
returns table (
    chunk_id uuid,
    document_id uuid,
    source text,
    parser text,
    chunk_index integer,
    text text,
    similarity double precision
)
language sql
stable
as $$
    select
        dc.id as chunk_id,
        dc.document_id,
        dc.source,
        dc.parser,
        dc.chunk_index,
        dc.text,
        1 - (ce.embedding <=> query_embedding) as similarity
    from material_eval.chunk_embeddings ce
    join material_eval.document_chunks dc on dc.id = ce.chunk_id
    where ce.provider_name = provider_name_filter
      and ce.model_name = model_name_filter
      and 1 - (ce.embedding <=> query_embedding) >= match_threshold
    order by ce.embedding <=> query_embedding
    limit match_count;
$$;

grant usage on schema material_eval to service_role;
grant select, insert, update, delete on all tables in schema material_eval to service_role;
grant execute on function material_eval.match_document_chunks(
    extensions.vector(1024),
    integer,
    double precision,
    text,
    text
) to service_role;
