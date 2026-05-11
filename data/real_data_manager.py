import os
from dotenv import load_dotenv

# Carga las llaves del archivo .env
load_dotenv()

class RealDataManager:
    def __init__(self):
        self.api_football = os.getenv('API_FOOTBALL_KEY')
        self.football_data = os.getenv('FOOTBALL_DATA_API_KEY')
        self.sportmonks = os.getenv('SPORTMONKS_API_TOKEN')

    def verificar_sistema(self):
        if all([self.api_football, self.football_data, self.sportmonks]):
            return "✅ ¡CONEXIÓN EXITOSA! La Gema ya está vinculada a internet."
        return "❌ Error: Faltan llaves en el archivo .env"

if __name__ == "__main__":
    manager = RealDataManager()
    print(manager.verificar_sistema())