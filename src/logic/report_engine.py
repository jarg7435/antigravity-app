from datetime import datetime
from typing import Dict, Any, List
from src.models.base import Match, PredictionResult

class ReportEngine:
    """
    Genera reportes estructurados para análisis pre-partido y post-partido.
    Soporta formatos Markdown y próximamente PDF/Excel.
    """
    
    def generate_markdown_report(self, match: Match, prediction: Any) -> str:
        import json
        
        # NUCLEAR SAFETY: Serialize to JSON to strip all Pydantic class logic and avoid AttributeError
        try:
            # Try various serialization methods for Pydantic v1/v2
            if hasattr(prediction, "model_dump_json"):
                json_data = prediction.model_dump_json()
            elif hasattr(prediction, "json"):
                json_data = prediction.json()
            else:
                # Last resort: convert to dict and then to json
                try:
                    import pydantic
                    json_data = json.dumps(prediction, default=lambda o: o.dict() if hasattr(o, "dict") else vars(o))
                except:
                    json_data = "{}"
            
            p_dict = json.loads(json_data)
        except:
            p_dict = {}

        # Safe extraction from dict
        score = p_dict.get('score_prediction', '0-0')
        conf_val = p_dict.get('confidence_score', 0)
        conf = f"{conf_val * 100:.0f}%" if conf_val else "0%"
        
        # Probabilities
        wp_h = p_dict.get('win_prob_home', 0.33)
        wp_d = p_dict.get('draw_prob', 0.34)
        wp_a = p_dict.get('win_prob_away', 0.33)
        
        ext_sum = p_dict.get('external_analysis_summary', "Análisis estratégico no disponible en esta sesión.")

        report = f"""# ⚽ Reporte Estratégico LAGEMA JARG74
**Fecha:** {match.date.strftime('%Y-%m-%d')} | **Hora:** {match.kickoff_time}
**Competición:** {match.competition}
**Enfrentamiento:** {match.home_team.name} vs {match.away_team.name}

---

## 📊 Probabilidades IA (Ensemble Model)
- **Local (1):** {wp_h * 100:.2f}%
- **Empate (X):** {wp_d * 100:.2f}%
- **Visitante (2):** {wp_a * 100:.2f}%

**Predicción de Marcador:** {score}
**Nivel de Confianza:** {conf}

---

## 💎 Análisis de Valor (Betting Value)
"""
        val_opps = p_dict.get('value_opportunities', [])
        if val_opps:
            for opp in val_opps:
                report += f"- **Mercado {opp.get('market', '?')}**: Valor {opp.get('value_pct', 0)}% | Cuota {opp.get('odds', 0)} | Stake {opp.get('suggested_stake_pct', 0)}%\n"
        else:
            report += "No se detectaron oportunidades de valor significativas (>5%).\n"

        report += f"""
---

## 🛡️ Inteligencia de Capa Externa
{ext_sum}

---
*Generado automáticamente por LAGEMA JARG74 Engine v6.25 (Cortex Safe Mode)*
"""
        return report

    def save_report(self, content: str, filename: str):
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
