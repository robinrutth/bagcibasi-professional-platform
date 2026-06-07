CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS customers (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  sector TEXT,
  payment_terms TEXT DEFAULT 'Vadeli',
  risk_level TEXT DEFAULT 'Düşük',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS carriers (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  vehicle_type TEXT NOT NULL,
  routes TEXT,
  phone TEXT,
  ownership_type TEXT DEFAULT 'Aracı',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vehicles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  plate TEXT UNIQUE,
  vehicle_type TEXT NOT NULL,
  max_tonnage NUMERIC(8, 2) NOT NULL,
  fuel_type TEXT DEFAULT 'Dizel',
  emission_factor NUMERIC(8, 3) NOT NULL,
  cost_per_km NUMERIC(10, 2) NOT NULL,
  status TEXT DEFAULT 'Müsait'
);

CREATE TABLE IF NOT EXISTS shipments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  customer_id UUID REFERENCES customers(id),
  customer_name TEXT NOT NULL DEFAULT 'Yeni Müşteri',
  origin TEXT NOT NULL,
  destination TEXT NOT NULL,
  cargo_type TEXT NOT NULL,
  tonnage NUMERIC(8, 2) NOT NULL,
  delivery_date DATE NOT NULL,
  distance_km NUMERIC(10, 2) NOT NULL,
  vehicle_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Hazırlanıyor',
  cost_amount NUMERIC(14, 2) NOT NULL,
  invoice_amount NUMERIC(14, 2) NOT NULL,
  profit_amount NUMERIC(14, 2) NOT NULL,
  profit_margin NUMERIC(8, 4) NOT NULL,
  co2_kg NUMERIC(12, 2) NOT NULL,
  risk_level TEXT NOT NULL,
  ai_recommendation TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shipment_status_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  shipment_id UUID NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS expenses (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  shipment_id UUID REFERENCES shipments(id),
  category TEXT NOT NULL,
  amount NUMERIC(14, 2) NOT NULL,
  expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS cash_movements (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  description TEXT NOT NULL,
  movement_type TEXT NOT NULL CHECK (movement_type IN ('in', 'out', 'pending')),
  amount NUMERIC(14, 2) NOT NULL,
  payment_type TEXT DEFAULT 'Peşin',
  movement_date DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS carbon_calculations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  shipment_id UUID REFERENCES shipments(id) ON DELETE CASCADE,
  distance_km NUMERIC(10, 2) NOT NULL,
  tonnage NUMERIC(8, 2) NOT NULL,
  vehicle_type TEXT NOT NULL,
  fuel_type TEXT DEFAULT 'Dizel',
  co2_kg NUMERIC(12, 2) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  actor TEXT NOT NULL DEFAULT 'system',
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  username TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'operation',
  password_hash TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_jti TEXT NOT NULL UNIQUE,
  token_hash TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS revoked_tokens (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  token_jti TEXT NOT NULL UNIQUE,
  token_type TEXT NOT NULL,
  revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO customers (name, sector, payment_terms, risk_level, notes) VALUES
  ('Berksa', 'Ambalaj', 'Vadeli', 'Orta', 'İlk müşteri, vadeli çalışır.'),
  ('Kent Beton', 'İnşaat', 'Peşin', 'Düşük', 'Peşin ödeme alışkanlığı iyi.'),
  ('MamaTürkiye', 'Gıda', 'Peşin', 'Düşük', 'Düzenli küçük hacimli taşıma.'),
  ('Gürel İnşaat', 'İnşaat', 'Vadeli', 'Orta', 'Yüksek hacimli potansiyel.')
ON CONFLICT DO NOTHING;

INSERT INTO vehicles (plate, vehicle_type, max_tonnage, fuel_type, emission_factor, cost_per_km, status) VALUES
  ('35 BL 001', 'Kamyonet', 3.5, 'Dizel', 0.300, 21.0, 'Müsait'),
  ('45 BL 002', 'Kamyon', 18.0, 'Dizel', 0.600, 31.0, 'Müsait'),
  ('34 BL 003', 'Tır', 26.0, 'Dizel', 0.900, 45.0, 'Yolda')
ON CONFLICT (plate) DO NOTHING;

INSERT INTO cash_movements (description, movement_type, amount, payment_type) VALUES
  ('Açılış sermayesi', 'in', 550000, 'Peşin'),
  ('Operasyon tahsilatı', 'in', 30000, 'Peşin'),
  ('Tedarikçi ödemeleri', 'out', 70000, 'Havale'),
  ('Bekleyen tahsilat', 'pending', 63000, 'Vadeli');
