-- Migration 006: Fix categoria name uniqueness
-- Problem: two global UNIQUE(name) constraints block valid same-name subcategories
--          under different parents (e.g. "DELANTERO" under "FRENOS" and "AMORTIGUADORES")
-- Solution: drop both incorrect constraints, add one composite unique index
--           with NULLS NOT DISTINCT so root categories (parent_id IS NULL)
--           are still deduplicated by name.
-- PostgreSQL version: 18.1 (NULLS NOT DISTINCT supported since PG15)
--
-- Run once. Safe to run on a live database with low traffic (index build is fast
-- on a small categoria table). No data is modified.

BEGIN;

-- Step 1: Drop the two redundant global unique constraints
ALTER TABLE public.categoria DROP CONSTRAINT IF EXISTS categoria_name_key;
ALTER TABLE public.categoria DROP CONSTRAINT IF EXISTS categoria_name_unique;

-- Step 2: Add correct composite unique index
-- NULLS NOT DISTINCT: treats (name='X', parent_id=NULL) as equal to another
-- (name='X', parent_id=NULL), preventing duplicate root categories.
-- Non-null parent_ids compare normally, so same name under different parents is allowed.
CREATE UNIQUE INDEX categoria_name_parent_uq
    ON public.categoria (name, parent_id)
    NULLS NOT DISTINCT;

COMMIT;
