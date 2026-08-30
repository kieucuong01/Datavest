-- DataVest supported market scope.
-- Retains historical/user rows for auditability while removing retired
-- markets from active catalogs and system universes.

UPDATE qd_market_symbols
SET is_active = 0,
    is_hot = 0
WHERE market NOT IN ('USStock', 'VNStock', 'Crypto', 'Forex')
   OR (market = 'Forex' AND UPPER(REPLACE(REPLACE(REPLACE(symbol, '/', ''), '-', ''), ' ', '')) <> 'XAUUSD');

UPDATE qd_universes
SET status = 'archived',
    updated_at = NOW()
WHERE market NOT IN ('', 'USStock', 'VNStock', 'Crypto', 'Forex')
   OR source_ref ILIKE 'CNStock:%'
   OR source_ref ILIKE 'HKStock:%'
   OR source_ref ILIKE 'Futures:%'
   OR source_ref ILIKE 'MOEX:%';
