-- Law 2 (Database & Schema Isolation):
-- Initializes the 4 strictly isolated PostgreSQL schemas for the Super App Modular Monolith.
-- Cross-schema Foreign Keys are strictly prohibited; cross-context references use pure indexed UUIDs.

CREATE SCHEMA IF NOT EXISTS identity_schema;
CREATE SCHEMA IF NOT EXISTS wallet_schema;
CREATE SCHEMA IF NOT EXISTS commerce_schema;
CREATE SCHEMA IF NOT EXISTS media_ai_schema;
