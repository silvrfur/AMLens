-- Optional: SELECT-only login for the agent adapter (AML_SOURCE_DATABASE_URL).
-- Run as the database owner/admin, AFTER `alembic upgrade head`:
--   psql "<admin connection>" -v reader_password="'choose-a-strong-password'" -f scripts/create_readonly_role.sql
CREATE ROLE amlens_reader LOGIN PASSWORD :reader_password;
GRANT CONNECT ON DATABASE amlens TO amlens_reader;
GRANT USAGE ON SCHEMA public TO amlens_reader;
GRANT SELECT ON transactions, alerts TO amlens_reader;
