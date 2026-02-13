import sys
import os

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.logic.ml_engine import MLEngine
from src.data.db_manager import DataManager
from src.data.training_manager import TrainingManager

def run_calibration():
    print("--- Iniciando Calibracion de Modelos LAGEMA JARG74 ---")
    
    # Forzar encoding si es necesario
    if sys.stdout.encoding != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    ml_engine = MLEngine()
    db_manager = DataManager()
    tm = TrainingManager(db_manager, ml_engine)
    
    # Ejecutar ciclo de entrenamiento
    results = tm.run_full_training_cycle()
    
    print("\n--- RESULTADOS DE CALIBRACION ---")
    print(f"Muestras Analizadas: {results['samples_analyzed']}")
    
    metrics = results['training_metrics']
    print(f"Accuracy (Test Set): {metrics['accuracy']*100:.2f}%")
    print(f"F1-Score: {metrics['f1_score']:.4f}")
    print(f"AUC-ROC: {metrics['auc_roc']:.4f}")
    
    cv = results['cv_metrics']
    print("\n--- VALIDACION CRUZADA (K-Fold) ---")
    print(f"CV Accuracy Media: {cv['cv_accuracy_mean']*100:.2f}%")
    print(f"Desviacion Estandar: {cv['cv_accuracy_std']:.4f}")
    
    if metrics['accuracy'] >= 0.55:
        print("\nOK: Precision >= 55%")
    else:
        print("\nAVISO: Precision < 55%. Requiere mas datos.")

if __name__ == "__main__":
    run_calibration()
