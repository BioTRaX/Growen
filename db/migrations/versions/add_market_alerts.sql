-- Migración MarketAlert - Sistema de alertas de precios de mercado
-- Creación manual de tabla y índices

-- 1. Crear tabla market_alerts
CREATE TABLE IF NOT EXISTS market_alerts (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    old_value NUMERIC(12,2),
    new_value NUMERIC(12,2) NOT NULL,
    delta_percentage NUMERIC(8,4) NOT NULL,
    message TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolved_by INTEGER,
    resolution_note TEXT,
    email_sent BOOLEAN NOT NULL DEFAULT FALSE,
    email_sent_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 2. Crear foreign keys
ALTER TABLE market_alerts
ADD CONSTRAINT fk_market_alerts_product_id
FOREIGN KEY (product_id) REFERENCES canonical_products(id) ON DELETE CASCADE;

ALTER TABLE market_alerts
ADD CONSTRAINT fk_market_alerts_resolved_by
FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL;

-- 3. Crear índices
CREATE INDEX IF NOT EXISTS idx_market_alerts_product_id ON market_alerts(product_id);
CREATE INDEX IF NOT EXISTS idx_market_alerts_created_at ON market_alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_market_alerts_resolved ON market_alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_market_alerts_product_active ON market_alerts(product_id, resolved);

-- 4. Actualizar version de Alembic
INSERT INTO alembic_version (version_num) VALUES ('add_market_alerts')
ON CONFLICT (version_num) DO NOTHING;
