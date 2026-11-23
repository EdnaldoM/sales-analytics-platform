-- Least privilege for the source databases.
--   generator      : owner of each database and its tables (full read/write)
--   airbyte_reader : CONNECT + SELECT only, including tables created later
-- By default every role may connect to every database (PUBLIC); this is revoked.

\connect ecommerce
REVOKE ALL ON DATABASE ecommerce FROM PUBLIC;
GRANT CONNECT ON DATABASE ecommerce TO airbyte_reader;
GRANT USAGE ON SCHEMA public TO airbyte_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO airbyte_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE generator IN SCHEMA public
    GRANT SELECT ON TABLES TO airbyte_reader;

\connect crm
REVOKE ALL ON DATABASE crm FROM PUBLIC;
GRANT CONNECT ON DATABASE crm TO airbyte_reader;
GRANT USAGE ON SCHEMA public TO airbyte_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO airbyte_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE generator IN SCHEMA public
    GRANT SELECT ON TABLES TO airbyte_reader;

\connect erp
REVOKE ALL ON DATABASE erp FROM PUBLIC;
GRANT CONNECT ON DATABASE erp TO airbyte_reader;
GRANT USAGE ON SCHEMA public TO airbyte_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO airbyte_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE generator IN SCHEMA public
    GRANT SELECT ON TABLES TO airbyte_reader;
