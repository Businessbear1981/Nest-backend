"""Market benchmarks embedded for Prometheus financial modeling.

NIC MAP, CBRE, CoStar data snapshots — Q4 2025.
Used by Prometheus for assumption validation and feasibility studies.
"""

SENIOR_LIVING_BENCHMARKS = {
    "il_revenue_per_unit_monthly": {"low": 3800, "mid": 5200, "high": 7500},
    "al_revenue_per_unit_monthly": {"low": 5500, "mid": 7200, "high": 10000},
    "mc_revenue_per_unit_monthly": {"low": 6500, "mid": 8500, "high": 12000},
    "opex_per_il_unit_annual": {"low": 42000, "mid": 55000, "high": 72000},
    "opex_per_al_unit_annual": {"low": 68000, "mid": 82000, "high": 105000},
    "opex_per_mc_unit_annual": {"low": 88000, "mid": 108000, "high": 138000},
    "staffing_pct_of_revenue": {"low": 52, "mid": 58, "high": 65},
    "stabilized_occupancy": {"low": 82, "mid": 88, "high": 94},
    "stabilization_months": {"fast": 24, "typical": 30, "slow": 42},
    "exit_cap_rate": {"compressed": 5.5, "market": 6.75, "stressed": 8.25},
    "dev_cost_per_il_unit": {"low": 280000, "mid": 380000, "high": 520000},
    "dev_cost_per_al_unit": {"low": 200000, "mid": 280000, "high": 380000},
}

INDUSTRIAL_BENCHMARKS = {
    "rent_per_sf_annual": {"low": 8.50, "mid": 14.00, "high": 22.00},
    "vacancy_rate": {"low": 3.0, "mid": 5.5, "high": 9.0},
    "opex_per_sf_annual": {"low": 1.50, "mid": 2.25, "high": 3.50},
    "dev_cost_per_sf": {"low": 85, "mid": 130, "high": 195},
    "exit_cap_rate": {"compressed": 4.5, "market": 5.75, "stressed": 7.25},
}

MULTIFAMILY_BENCHMARKS = {
    "revenue_per_unit_monthly": {"low": 1200, "mid": 1850, "high": 3200},
    "vacancy_rate": {"low": 4.0, "mid": 6.5, "high": 10.0},
    "opex_per_unit_annual": {"low": 6500, "mid": 9000, "high": 13000},
    "dev_cost_per_unit": {"low": 180000, "mid": 280000, "high": 420000},
    "exit_cap_rate": {"compressed": 4.25, "market": 5.25, "stressed": 6.75},
}

OFFICE_BENCHMARKS = {
    "rent_per_sf_annual": {"low": 22.00, "mid": 35.00, "high": 65.00},
    "vacancy_rate": {"low": 8.0, "mid": 14.0, "high": 22.0},
    "opex_per_sf_annual": {"low": 8.00, "mid": 12.00, "high": 18.00},
    "exit_cap_rate": {"compressed": 5.5, "market": 7.0, "stressed": 9.0},
}

ALL_BENCHMARKS = {
    "senior_living": SENIOR_LIVING_BENCHMARKS,
    "industrial": INDUSTRIAL_BENCHMARKS,
    "multifamily": MULTIFAMILY_BENCHMARKS,
    "office": OFFICE_BENCHMARKS,
}


def get_benchmarks(asset_type: str) -> dict:
    """Return benchmarks for a given asset type."""
    return ALL_BENCHMARKS.get(asset_type, {})
