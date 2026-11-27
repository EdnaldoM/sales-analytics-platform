-- =============================================================================
-- Ingestion check: rows per table in RAW, and duplicates per primary key.
-- Compare TOTAL_ROWS with `make stats` (PostgreSQL) after a sync.
-- Expected: TOTAL_ROWS = DISTINCT_KEYS on every row (Append + Deduped keeps
-- one row per key), and the same counts as PostgreSQL.
-- Run as: SYSADMIN (inherits LOADER, the owner of the RAW schemas)
-- =============================================================================

USE ROLE SYSADMIN;
USE WAREHOUSE INGEST_WH;

SELECT 'ecommerce.customers' AS source_table, COUNT(*) AS total_rows, COUNT(DISTINCT customer_id) AS distinct_keys, MAX(_airbyte_extracted_at) AS last_extracted_at FROM RAW.ECOMMERCE.CUSTOMERS
UNION ALL SELECT 'ecommerce.orders',             COUNT(*), COUNT(DISTINCT order_id),        MAX(_airbyte_extracted_at) FROM RAW.ECOMMERCE.ORDERS
UNION ALL SELECT 'ecommerce.order_items',        COUNT(*), COUNT(DISTINCT order_item_id),   MAX(_airbyte_extracted_at) FROM RAW.ECOMMERCE.ORDER_ITEMS
UNION ALL SELECT 'ecommerce.payments',           COUNT(*), COUNT(DISTINCT payment_id),      MAX(_airbyte_extracted_at) FROM RAW.ECOMMERCE.PAYMENTS
UNION ALL SELECT 'ecommerce.returns',            COUNT(*), COUNT(DISTINCT return_id),       MAX(_airbyte_extracted_at) FROM RAW.ECOMMERCE.RETURNS
UNION ALL SELECT 'ecommerce.return_items',       COUNT(*), COUNT(DISTINCT return_item_id),  MAX(_airbyte_extracted_at) FROM RAW.ECOMMERCE.RETURN_ITEMS
UNION ALL SELECT 'crm.customers',                COUNT(*), COUNT(DISTINCT crm_customer_id), MAX(_airbyte_extracted_at) FROM RAW.CRM.CUSTOMERS
UNION ALL SELECT 'crm.customer_contacts',        COUNT(*), COUNT(DISTINCT contact_id),      MAX(_airbyte_extracted_at) FROM RAW.CRM.CUSTOMER_CONTACTS
UNION ALL SELECT 'erp.product_categories',       COUNT(*), COUNT(DISTINCT category_id),     MAX(_airbyte_extracted_at) FROM RAW.ERP.PRODUCT_CATEGORIES
UNION ALL SELECT 'erp.products',                 COUNT(*), COUNT(DISTINCT product_id),      MAX(_airbyte_extracted_at) FROM RAW.ERP.PRODUCTS
UNION ALL SELECT 'erp.product_cost_history',     COUNT(*), COUNT(DISTINCT cost_id),         MAX(_airbyte_extracted_at) FROM RAW.ERP.PRODUCT_COST_HISTORY
ORDER BY source_table;
