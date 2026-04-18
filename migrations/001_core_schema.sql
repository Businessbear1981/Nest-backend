-- ============================================================
-- NEST Advisors — Core Schema Migration 001
-- PostgreSQL 15+ (Supabase)
-- ============================================================

-- ─── auto-update trigger function ───
CREATE OR REPLACE FUNCTION nest_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 1. deals
-- ============================================================
CREATE TABLE deals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  status        text NOT NULL DEFAULT 'pipeline' CHECK (status IN ('pipeline','active','closing','closed','dead')),
  state         text,
  market        text,
  deal_type     text DEFAULT 'bond',
  bond_face     numeric(16,2) DEFAULT 0,
  dscr          numeric(6,3) DEFAULT 0,
  ltv           numeric(6,2) DEFAULT 0,
  cf_leverage   numeric(6,3) DEFAULT 0,
  bs_leverage   numeric(6,3) DEFAULT 0,
  d_ebitda      numeric(6,3) DEFAULT 0,
  icr           numeric(6,3) DEFAULT 0,
  refi_cycles   int DEFAULT 0,
  ae_economics  numeric(16,2) DEFAULT 0,
  readiness_score int DEFAULT 0 CHECK (readiness_score BETWEEN 0 AND 100),
  checklist     jsonb DEFAULT '[]'::jsonb,
  stress_scenarios jsonb DEFAULT '[]'::jsonb,
  capital_stack jsonb DEFAULT '[]'::jsonb,
  sources_uses  jsonb DEFAULT '[]'::jsonb,
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE deals ENABLE ROW LEVEL SECURITY;
CREATE POLICY deals_admin ON deals FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_deals_status     ON deals (status);
CREATE INDEX idx_deals_created_at ON deals (created_at);

CREATE TRIGGER trg_deals_updated_at BEFORE UPDATE ON deals
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 2. bond_structures
-- ============================================================
CREATE TABLE bond_structures (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id       uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  tranche       text NOT NULL,
  amount        numeric(16,2) NOT NULL DEFAULT 0,
  pct           numeric(5,2) DEFAULT 0,
  rate          text,
  grade         text,
  maturity_date date,
  coupon        numeric(5,3),
  is_io         boolean DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE bond_structures ENABLE ROW LEVEL SECURITY;
CREATE POLICY bond_structures_admin ON bond_structures FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_bond_structures_deal_id ON bond_structures (deal_id);
CREATE INDEX idx_bond_structures_grade   ON bond_structures (grade);

CREATE TRIGGER trg_bond_structures_updated_at BEFORE UPDATE ON bond_structures
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 3. refi_cycles
-- ============================================================
CREATE TABLE refi_cycles (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id       uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  cycle_number  int NOT NULL,
  start_date    date,
  end_date      date,
  target_rate   numeric(5,3),
  achieved_rate numeric(5,3),
  status        text DEFAULT 'pending' CHECK (status IN ('pending','active','complete','skipped')),
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE refi_cycles ENABLE ROW LEVEL SECURITY;
CREATE POLICY refi_cycles_admin ON refi_cycles FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_refi_cycles_deal_id ON refi_cycles (deal_id);
CREATE INDEX idx_refi_cycles_status  ON refi_cycles (status);

CREATE TRIGGER trg_refi_cycles_updated_at BEFORE UPDATE ON refi_cycles
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 4. ae_fund
-- ============================================================
CREATE TABLE ae_fund (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  aum           numeric(16,2) DEFAULT 0,
  target_return numeric(5,2),
  ytd_return    numeric(5,2),
  strategy      text,
  lc_phase      text DEFAULT 'surety' CHECK (lc_phase IN ('surety','hybrid','lc_dominant','self_collateralized')),
  status        text DEFAULT 'active',
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE ae_fund ENABLE ROW LEVEL SECURITY;
CREATE POLICY ae_fund_admin ON ae_fund FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_ae_fund_status ON ae_fund (status);

CREATE TRIGGER trg_ae_fund_updated_at BEFORE UPDATE ON ae_fund
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 5. equity_positions
-- ============================================================
CREATE TABLE equity_positions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id       uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  fund_id       uuid REFERENCES ae_fund(id),
  position_type text NOT NULL DEFAULT 'equity',
  amount        numeric(16,2) NOT NULL DEFAULT 0,
  pct_ownership numeric(5,2) DEFAULT 0,
  entry_date    date,
  exit_date     date,
  irr_target    numeric(5,2),
  irr_actual    numeric(5,2),
  status        text DEFAULT 'active',
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE equity_positions ENABLE ROW LEVEL SECURITY;
CREATE POLICY equity_positions_admin ON equity_positions FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_equity_positions_deal_id ON equity_positions (deal_id);
CREATE INDEX idx_equity_positions_status  ON equity_positions (status);

CREATE TRIGGER trg_equity_positions_updated_at BEFORE UPDATE ON equity_positions
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 6. market_signals
-- ============================================================
CREATE TABLE market_signals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_type   text NOT NULL,
  source        text,
  ticker        text,
  value         numeric(16,6),
  direction     text CHECK (direction IN ('bullish','bearish','neutral')),
  confidence    numeric(4,2) CHECK (confidence BETWEEN 0 AND 1),
  captured_at   timestamptz NOT NULL DEFAULT NOW(),
  metadata      jsonb DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE market_signals ENABLE ROW LEVEL SECURITY;
CREATE POLICY market_signals_admin ON market_signals FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_market_signals_type       ON market_signals (signal_type);
CREATE INDEX idx_market_signals_created_at ON market_signals (created_at);

CREATE TRIGGER trg_market_signals_updated_at BEFORE UPDATE ON market_signals
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 7. covenants
-- ============================================================
CREATE TABLE covenants (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id         uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  covenant_type   text NOT NULL,
  description     text,
  threshold_value numeric(16,4),
  current_value   numeric(16,4),
  in_compliance   boolean DEFAULT true,
  test_frequency  text DEFAULT 'quarterly',
  next_test_date  date,
  created_at      timestamptz NOT NULL DEFAULT NOW(),
  updated_at      timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE covenants ENABLE ROW LEVEL SECURITY;
CREATE POLICY covenants_admin ON covenants FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_covenants_deal_id ON covenants (deal_id);

CREATE TRIGGER trg_covenants_updated_at BEFORE UPDATE ON covenants
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 8. investors
-- ============================================================
CREATE TABLE investors (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  entity_type   text,
  contact_email text,
  contact_phone text,
  aum           numeric(16,2),
  investor_type text CHECK (investor_type IN ('institutional','family_office','hnwi','fund','bank','insurance')),
  tier          text DEFAULT 'B' CHECK (tier IN ('A','B','C')),
  status        text DEFAULT 'prospect',
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE investors ENABLE ROW LEVEL SECURITY;
CREATE POLICY investors_admin ON investors FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_investors_status ON investors (status);

CREATE TRIGGER trg_investors_updated_at BEFORE UPDATE ON investors
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 9. agents
-- ============================================================
CREATE TABLE agents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL UNIQUE,
  role          text NOT NULL,
  status        text DEFAULT 'standby' CHECK (status IN ('active','standby','error','disabled')),
  last_run_at   timestamptz,
  run_count     int DEFAULT 0,
  config        jsonb DEFAULT '{}'::jsonb,
  error_log     text,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
CREATE POLICY agents_admin ON agents FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_agents_status ON agents (status);

CREATE TRIGGER trg_agents_updated_at BEFORE UPDATE ON agents
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 10. perm_debt_rolloffs
-- ============================================================
CREATE TABLE perm_debt_rolloffs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id         uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  lender_name     text,
  current_balance numeric(16,2) DEFAULT 0,
  rate            numeric(5,3),
  maturity_date   date,
  months_to_stab  int,
  rolloff_target  date,
  status          text DEFAULT 'monitoring' CHECK (status IN ('monitoring','approaching','refinanced','closed')),
  created_at      timestamptz NOT NULL DEFAULT NOW(),
  updated_at      timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE perm_debt_rolloffs ENABLE ROW LEVEL SECURITY;
CREATE POLICY perm_debt_rolloffs_admin ON perm_debt_rolloffs FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_perm_debt_rolloffs_deal_id ON perm_debt_rolloffs (deal_id);
CREATE INDEX idx_perm_debt_rolloffs_status  ON perm_debt_rolloffs (status);

CREATE TRIGGER trg_perm_debt_rolloffs_updated_at BEFORE UPDATE ON perm_debt_rolloffs
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 11. lenders
-- ============================================================
CREATE TABLE lenders (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  lender_type   text CHECK (lender_type IN ('bank','agency','conduit','life_co','debt_fund','credit_union')),
  min_loan      numeric(16,2),
  max_loan      numeric(16,2),
  property_types text[],
  states        text[],
  rate_floor    numeric(5,3),
  rate_ceiling  numeric(5,3),
  contact_name  text,
  contact_email text,
  status        text DEFAULT 'active',
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE lenders ENABLE ROW LEVEL SECURITY;
CREATE POLICY lenders_admin ON lenders FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_lenders_status ON lenders (status);

CREATE TRIGGER trg_lenders_updated_at BEFORE UPDATE ON lenders
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 12. lender_matches
-- ============================================================
CREATE TABLE lender_matches (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id       uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  lender_id     uuid NOT NULL REFERENCES lenders(id) ON DELETE CASCADE,
  score         numeric(5,2) DEFAULT 0 CHECK (score BETWEEN 0 AND 100),
  match_reasons jsonb DEFAULT '[]'::jsonb,
  status        text DEFAULT 'suggested' CHECK (status IN ('suggested','contacted','negotiating','committed','passed')),
  proposed_rate numeric(5,3),
  proposed_amount numeric(16,2),
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE lender_matches ENABLE ROW LEVEL SECURITY;
CREATE POLICY lender_matches_admin ON lender_matches FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_lender_matches_deal_id   ON lender_matches (deal_id);
CREATE INDEX idx_lender_matches_score     ON lender_matches (score);
CREATE INDEX idx_lender_matches_status    ON lender_matches (status);

CREATE TRIGGER trg_lender_matches_updated_at BEFORE UPDATE ON lender_matches
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 13. ma_targets
-- ============================================================
CREATE TABLE ma_targets (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_name  text NOT NULL,
  naics_code    text,
  industry      text,
  revenue       numeric(16,2),
  ebitda        numeric(16,2),
  employees     int,
  location      text,
  score         numeric(5,2) DEFAULT 0 CHECK (score BETWEEN 0 AND 100),
  status        text DEFAULT 'identified' CHECK (status IN ('identified','researching','outreach','nda','loi','due_diligence','closed','passed')),
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE ma_targets ENABLE ROW LEVEL SECURITY;
CREATE POLICY ma_targets_admin ON ma_targets FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_ma_targets_status ON ma_targets (status);
CREATE INDEX idx_ma_targets_score  ON ma_targets (score);

CREATE TRIGGER trg_ma_targets_updated_at BEFORE UPDATE ON ma_targets
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 14. ma_deals
-- ============================================================
CREATE TABLE ma_deals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_id     uuid NOT NULL REFERENCES ma_targets(id) ON DELETE CASCADE,
  deal_id       uuid REFERENCES deals(id) ON DELETE SET NULL,
  acquisition_price numeric(16,2),
  ev_ebitda     numeric(6,2),
  financing     text,
  close_date    date,
  status        text DEFAULT 'negotiating' CHECK (status IN ('negotiating','due_diligence','closing','closed','terminated')),
  business_plan jsonb DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE ma_deals ENABLE ROW LEVEL SECURITY;
CREATE POLICY ma_deals_admin ON ma_deals FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_ma_deals_deal_id ON ma_deals (deal_id);
CREATE INDEX idx_ma_deals_status  ON ma_deals (status);

CREATE TRIGGER trg_ma_deals_updated_at BEFORE UPDATE ON ma_deals
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 15. modeling_results
-- ============================================================
CREATE TABLE modeling_results (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id       uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  model_type    text NOT NULL,
  version       int DEFAULT 1,
  inputs        jsonb DEFAULT '{}'::jsonb,
  outputs       jsonb DEFAULT '{}'::jsonb,
  irr           numeric(6,3),
  npv           numeric(16,2),
  dscr_min      numeric(6,3),
  dscr_avg      numeric(6,3),
  is_feasible   boolean DEFAULT false,
  run_by        text,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE modeling_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY modeling_results_admin ON modeling_results FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_modeling_results_deal_id ON modeling_results (deal_id);
CREATE INDEX idx_modeling_results_created_at ON modeling_results (created_at);

CREATE TRIGGER trg_modeling_results_updated_at BEFORE UPDATE ON modeling_results
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 16. risk_scores
-- ============================================================
CREATE TABLE risk_scores (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id       uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  overall_score numeric(5,2) DEFAULT 0 CHECK (overall_score BETWEEN 0 AND 100),
  credit_risk   numeric(5,2) DEFAULT 0,
  market_risk   numeric(5,2) DEFAULT 0,
  construction_risk numeric(5,2) DEFAULT 0,
  legal_risk    numeric(5,2) DEFAULT 0,
  operational_risk  numeric(5,2) DEFAULT 0,
  environmental_risk numeric(5,2) DEFAULT 0,
  political_risk numeric(5,2) DEFAULT 0,
  grade         text,
  assessed_at   timestamptz NOT NULL DEFAULT NOW(),
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE risk_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY risk_scores_admin ON risk_scores FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_risk_scores_deal_id ON risk_scores (deal_id);
CREATE INDEX idx_risk_scores_score   ON risk_scores (overall_score);
CREATE INDEX idx_risk_scores_grade   ON risk_scores (grade);

CREATE TRIGGER trg_risk_scores_updated_at BEFORE UPDATE ON risk_scores
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- 17. risk_alerts
-- ============================================================
CREATE TABLE risk_alerts (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id       uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  risk_score_id uuid REFERENCES risk_scores(id) ON DELETE SET NULL,
  severity      text NOT NULL CHECK (severity IN ('low','medium','high','critical')),
  category      text NOT NULL,
  title         text NOT NULL,
  description   text,
  is_resolved   boolean DEFAULT false,
  resolved_at   timestamptz,
  resolved_by   text,
  created_at    timestamptz NOT NULL DEFAULT NOW(),
  updated_at    timestamptz NOT NULL DEFAULT NOW()
);
ALTER TABLE risk_alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY risk_alerts_admin ON risk_alerts FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_risk_alerts_deal_id    ON risk_alerts (deal_id);
CREATE INDEX idx_risk_alerts_severity   ON risk_alerts (severity);
CREATE INDEX idx_risk_alerts_created_at ON risk_alerts (created_at);

CREATE TRIGGER trg_risk_alerts_updated_at BEFORE UPDATE ON risk_alerts
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();

-- ============================================================
-- SEED DATA — 3 Demo Deals
-- ============================================================

-- Deal 1: Life Star Pointe Loop
INSERT INTO deals (
  name, status, state, market, bond_face, dscr, ltv, cf_leverage, bs_leverage,
  d_ebitda, icr, refi_cycles, ae_economics, readiness_score,
  checklist, stress_scenarios, capital_stack, sources_uses
) VALUES (
  'Life Star Pointe Loop', 'active', 'FL', 'Orlando',
  231000000, 2.35, 52.0, 1.32, 1.78, 4.1, 3.85, 3, 18400000, 82,
  '[{"label":"PLOM executed","done":true},{"label":"Hylant surety bound","done":true},{"label":"LGFC approval","done":true},{"label":"Rating agency engaged","done":true},{"label":"Investor book opened","done":false},{"label":"Closing counsel retained","done":true},{"label":"Environmental Phase II","done":false},{"label":"Title commitment","done":true}]'::jsonb,
  '[{"name":"Rate shock +200bp","dscr":1.82,"ltv":58,"pass":true},{"name":"NOI decline -15%","dscr":1.95,"ltv":55,"pass":true},{"name":"Vacancy surge +10%","dscr":1.61,"ltv":62,"pass":true}]'::jsonb,
  '[{"tranche":"Series A","amount":173250000,"pct":75,"rate":"7.0%"},{"tranche":"Series B","amount":16170000,"pct":7,"rate":"12.5%"},{"tranche":"Equity","amount":41580000,"pct":18,"rate":"IRR 22%"}]'::jsonb,
  '[{"label":"Series A Bonds","amount":173250000,"type":"source"},{"label":"Series B Bonds","amount":16170000,"type":"source"},{"label":"Sponsor Equity","amount":41580000,"type":"source"},{"label":"Land & Site Work","amount":42000000,"type":"use"},{"label":"Hard Costs","amount":138600000,"type":"use"},{"label":"Soft Costs","amount":23100000,"type":"use"},{"label":"Financing Costs","amount":16170000,"type":"use"},{"label":"Reserves","amount":11130000,"type":"use"}]'::jsonb
);

-- Deal 2: Meridian Cove
INSERT INTO deals (
  name, status, state, market, bond_face, dscr, ltv, cf_leverage, bs_leverage,
  d_ebitda, icr, refi_cycles, ae_economics, readiness_score,
  checklist, stress_scenarios, capital_stack, sources_uses
) VALUES (
  'Meridian Cove', 'active', 'FL', 'Tampa',
  142000000, 2.12, 58.0, 1.55, 1.92, 4.8, 3.42, 2, 11200000, 67,
  '[{"label":"PLOM executed","done":true},{"label":"Hylant surety bound","done":true},{"label":"LGFC approval","done":false},{"label":"Rating agency engaged","done":true},{"label":"Investor book opened","done":false},{"label":"Closing counsel retained","done":true},{"label":"Environmental Phase II","done":true},{"label":"Title commitment","done":false}]'::jsonb,
  '[{"name":"Rate shock +200bp","dscr":1.58,"ltv":64,"pass":true},{"name":"NOI decline -15%","dscr":1.72,"ltv":60,"pass":true},{"name":"Vacancy surge +10%","dscr":1.39,"ltv":68,"pass":false}]'::jsonb,
  '[{"tranche":"Series A","amount":106500000,"pct":75,"rate":"7.25%"},{"tranche":"Series B","amount":9940000,"pct":7,"rate":"13.0%"},{"tranche":"Equity","amount":25560000,"pct":18,"rate":"IRR 24%"}]'::jsonb,
  '[{"label":"Series A Bonds","amount":106500000,"type":"source"},{"label":"Series B Bonds","amount":9940000,"type":"source"},{"label":"Sponsor Equity","amount":25560000,"type":"source"},{"label":"Land & Site Work","amount":28400000,"type":"use"},{"label":"Hard Costs","amount":85200000,"type":"use"},{"label":"Soft Costs","amount":14200000,"type":"use"},{"label":"Financing Costs","amount":9940000,"type":"use"},{"label":"Reserves","amount":4260000,"type":"use"}]'::jsonb
);

-- Deal 3: Palmetto Ridge
INSERT INTO deals (
  name, status, state, market, bond_face, dscr, ltv, cf_leverage, bs_leverage,
  d_ebitda, icr, refi_cycles, ae_economics, readiness_score,
  checklist, stress_scenarios, capital_stack, sources_uses
) VALUES (
  'Palmetto Ridge', 'pipeline', 'FL', 'Jacksonville',
  78000000, 1.88, 63.0, 1.72, 2.15, 5.2, 2.95, 1, 6100000, 41,
  '[{"label":"PLOM executed","done":true},{"label":"Hylant surety bound","done":false},{"label":"LGFC approval","done":false},{"label":"Rating agency engaged","done":false},{"label":"Investor book opened","done":false},{"label":"Closing counsel retained","done":true},{"label":"Environmental Phase II","done":false},{"label":"Title commitment","done":false}]'::jsonb,
  '[{"name":"Rate shock +200bp","dscr":1.35,"ltv":72,"pass":false},{"name":"NOI decline -15%","dscr":1.52,"ltv":67,"pass":true},{"name":"Vacancy surge +10%","dscr":1.21,"ltv":74,"pass":false}]'::jsonb,
  '[{"tranche":"Series A","amount":58500000,"pct":75,"rate":"7.5%"},{"tranche":"Series B","amount":5460000,"pct":7,"rate":"13.5%"},{"tranche":"Equity","amount":14040000,"pct":18,"rate":"IRR 26%"}]'::jsonb,
  '[{"label":"Series A Bonds","amount":58500000,"type":"source"},{"label":"Series B Bonds","amount":5460000,"type":"source"},{"label":"Sponsor Equity","amount":14040000,"type":"source"},{"label":"Land & Site Work","amount":15600000,"type":"use"},{"label":"Hard Costs","amount":46800000,"type":"use"},{"label":"Soft Costs","amount":7800000,"type":"use"},{"label":"Financing Costs","amount":5460000,"type":"use"},{"label":"Reserves","amount":2340000,"type":"use"}]'::jsonb
);

-- Seed 15 agents
INSERT INTO agents (name, role, status) VALUES
  ('Vector',      'Call/put timing',            'active'),
  ('Apex',        'Short position manager',     'active'),
  ('Chain',       'Blockchain execution',       'standby'),
  ('Atlas',       'Financial modeling',          'active'),
  ('Morgan',      'Memo & marketing writer',    'active'),
  ('Sterling',    'Investor placement',         'active'),
  ('Bridge',      'Perm debt monitoring',        'standby'),
  ('Quantum',     'HFT fund optimizer',         'active'),
  ('Maxwell',     'Credit analyst',             'active'),
  ('Aria',        'Client & BD outreach',       'standby'),
  ('Merlin',      'M&A intelligence',           'standby'),
  ('LenderScout', 'Direct lender sourcing',     'active'),
  ('Prometheus',  'Financial modeling engine',   'active'),
  ('Sentinel',    'Risk assessment engine',     'active'),
  ('Blaze',       'Elite marketing engine',     'standby');
