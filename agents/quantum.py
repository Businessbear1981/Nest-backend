"""Quantum — HFT fund optimizer agent.
Runs simulations, tracks war chest, computes LC capacity.
"""
from services.core import hft, ts


class QuantumAgent:
    def run_simulation(self, aum: float, months: int = 12) -> dict:
        result = hft.simulate(aum, months)
        result["timestamp"] = ts()
        result["agent"] = "quantum"
        return result

    def get_war_chest(self, positions: list = None) -> dict:
        positions = positions or []
        deployed = sum(p.get("amount_usd", 0) for p in positions)
        total_surplus = sum(p.get("surplus_usd", 0) for p in positions)
        available = max(0, total_surplus - deployed)
        return {
            "total_surplus_usd": round(total_surplus),
            "deployed_usd": round(deployed),
            "available_usd": round(available),
            "positions": len(positions),
            "ma_deployable_usd": round(available * 0.6),
            "timestamp": ts(),
        }

    def get_lc_capacity(self, aum: float) -> dict:
        advance_rate = 0.80
        lc_capacity = aum * advance_rate
        phase = ("phase_4" if aum >= 80e6 else "phase_3" if aum >= 40e6
                 else "phase_2" if aum >= 15e6 else "phase_1")
        phase_labels = {
            "phase_1": "Surety dominant ($0-15M)",
            "phase_2": "Hybrid surety+LC ($15-40M)",
            "phase_3": "LC dominant ($40-80M)",
            "phase_4": "Self-collateralized ($80M+)",
        }
        return {
            "aum_usd": round(aum),
            "advance_rate": advance_rate,
            "lc_capacity_usd": round(lc_capacity),
            "phase": phase,
            "phase_label": phase_labels[phase],
            "timestamp": ts(),
        }


quantum = QuantumAgent()
