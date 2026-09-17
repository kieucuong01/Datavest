ALTER TABLE qd_market_symbols ADD COLUMN IF NOT EXISTS sector VARCHAR(255) NOT NULL DEFAULT '';
ALTER TABLE qd_market_symbols ADD COLUMN IF NOT EXISTS listed_date DATE;
ALTER TABLE qd_market_symbols ADD COLUMN IF NOT EXISTS delisted_date DATE;
ALTER TABLE qd_market_symbols ADD COLUMN IF NOT EXISTS trading_status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE qd_market_symbols ADD COLUMN IF NOT EXISTS source VARCHAR(50) NOT NULL DEFAULT '';
ALTER TABLE qd_market_symbols ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMPTZ;

UPDATE qd_market_symbols
   SET asset_class = CASE
       WHEN symbol IN ('VNINDEX', 'VN30') THEN 'index'
       ELSE 'equity'
   END
 WHERE market = 'VNStock'
   AND asset_class = 'crypto';

CREATE INDEX IF NOT EXISTS idx_market_symbols_hose_active
  ON qd_market_symbols(exchange, is_active, trading_status)
  WHERE market = 'VNStock';
