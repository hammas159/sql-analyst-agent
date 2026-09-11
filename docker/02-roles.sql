-- The agent connects as this role. Everything below is enforced by Postgres, not
-- by a prompt and not by string inspection in Python.
--
-- Layered on purpose: the SQL validator in the application rejects non-SELECT
-- statements before they are ever sent, and this role guarantees that a validator
-- bug is still not a data-loss bug. Prompt instructions are the weakest of the
-- three and are treated as such.

CREATE ROLE agent_ro LOGIN PASSWORD 'agent_ro';

-- No write privileges anywhere, including on future tables.
REVOKE ALL ON SCHEMA public FROM agent_ro;
GRANT USAGE ON SCHEMA public TO agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agent_ro;

-- Cannot create anything, anywhere.
REVOKE CREATE ON SCHEMA public FROM agent_ro;
REVOKE ALL ON DATABASE retail FROM agent_ro;
GRANT CONNECT ON DATABASE retail TO agent_ro;

-- A runaway query cannot pin the database. Set on the role, so it applies to every
-- session it opens regardless of what the client forgets to set.
ALTER ROLE agent_ro SET statement_timeout = '10s';
ALTER ROLE agent_ro SET idle_in_transaction_session_timeout = '15s';
ALTER ROLE agent_ro SET default_transaction_read_only = on;

-- Cap the damage a single wide query can do to the application's memory.
ALTER ROLE agent_ro SET work_mem = '16MB';
