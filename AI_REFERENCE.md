# SuperX - Referencia Completa para IAs

> **INSTRUCCIÓN:** Copia este archivo a cualquier IA antes de pedirle que escriba código para SuperX.

---

## 1. REGLAS DE IMPORT (MUY IMPORTANTE)

### Regla 1: Entre módulos diferentes → ABSOLUTOS desde raíz
```python
from core.rules import calculate_skills
from data.database import get_supabase
from config.app_constants import SESSION_COOKIE_NAME
```

### Regla 2: Dentro del mismo paquete → RELATIVOS con `.`
```python
# Desde core/cualquier_archivo.py:
from .constants import RACES
from .mrg_engine import resolve_action

# Desde data/cualquier_archivo.py:
from .database import get_supabase

# Desde ui/cualquier_archivo.py:
from .state import get_player
```

### Regla 3: NUNCA hacer esto
```python
# MAL - no existe este re-export
from core import RACES

# MAL - import relativo fuera del paquete
from ..data.database import supabase

# BIEN
from core.constants import RACES
from data.database import get_supabase
```

---

## 2. ESTRUCTURA DEL PROYECTO

```
SuperX/
├── app.py                    # Punto de entrada Streamlit
├── config/
│   ├── settings.py
│   └── app_constants.py
├── core/
│   ├── constants.py
│   ├── rules.py
│   ├── models.py
│   ├── character_engine.py
│   ├── economy_engine.py
│   ├── mrg_engine.py
│   ├── mrg_constants.py
│   ├── mrg_effects.py
│   ├── time_engine.py
│   ├── prestige_engine.py
│   ├── prestige_constants.py
│   ├── world_models.py
│   ├── world_constants.py
│   └── galaxy_generator.py
├── data/
│   ├── database.py
│   ├── player_repository.py
│   ├── character_repository.py
│   ├── planet_repository.py
│   ├── world_repository.py
│   └── log_repository.py
├── services/
│   ├── gemini_service.py
│   ├── ai_tools.py
│   └── event_service.py
├── ui/
│   ├── state.py
│   ├── auth_page.py
│   ├── main_game_page.py
│   └── [otras páginas]
└── utils/
    ├── security.py
    └── helpers.py
```

---

## 3. CATÁLOGO DE EXPORTS POR MÓDULO

### config/settings.py
```python
get_secret(key: str) -> str | None
SUPABASE_URL: str | None
SUPABASE_KEY: str | None
GEMINI_API_KEY: str | None
```

### config/app_constants.py
```python
# Tiempo
LOCK_IN_WINDOW_START_HOUR = 23
LOCK_IN_WINDOW_START_MINUTE = 50
TIMEZONE_NAME = 'America/Argentina/Buenos_Aires'

# Autenticación
PIN_LENGTH = 4
SESSION_COOKIE_NAME = 'superx_session_token'

# Generación
ATTRIBUTE_BASE_MIN = 5
ATTRIBUTE_BASE_MAX = 10
DEFAULT_CANDIDATE_POOL_SIZE = 3

# UI
UI_COLOR_NOMINAL = "#56d59f"
UI_COLOR_LOCK_IN = "#f6c45b"
UI_COLOR_FROZEN = "#f06464"
LOG_CONTAINER_HEIGHT = 300

# IA
TEXT_MODEL_NAME = "gemini-2.5-flash"

# DB
DEFAULT_PLAYER_CREDITS = 1000
WORLD_STATE_SINGLETON_ID = 1

# Personajes
DEFAULT_RECRUIT_RANK = "Operativo"
COMMANDER_RANK = "Comandante"
COMMANDER_STATUS = "Activo"
COMMANDER_LOCATION = "Puente de Mando"
```

---

### core/constants.py
```python
RACES: Dict[str, Dict[str, Any]]
# {"Humano": {"desc": "...", "bonus": {"voluntad": 1}}, ...}

CLASSES: Dict[str, Dict[str, str]]
# {"Soldado": {"desc": "...", "bonus_attr": "fuerza"}, ...}

SKILL_MAPPING: Dict[str, Tuple[str, str]]
# {"Piloteo de naves pequeñas": ("agilidad", "tecnica"), ...}

POINTS_AVAILABLE_FOR_ATTRIBUTES: int = 60
ATTRIBUTE_SOFT_CAP: int = 15
ATTRIBUTE_COST_MULTIPLIER: int = 2
```

### core/rules.py
```python
def calculate_skills(attributes: Dict[str, int]) -> Dict[str, int]
def calculate_attribute_cost(start_val: int, target_val: int) -> int
def get_color_for_level(value: int) -> str
```

### core/models.py (Pydantic)
```python
class PlayerStatus(str, Enum)
class CharacterStatus(str, Enum)
class CharacterClass(str, Enum)

class CharacterAttributes(BaseModel)
class CharacterStats(BaseModel)
class PlayerResources(BaseModel)
class PlayerData(BaseModel)
class CommanderData(BaseModel)
class PlanetAsset(BaseModel)
class Building(BaseModel)
class ProductionSummary(BaseModel)
class EconomyTickResult(BaseModel)
```

### core/character_engine.py
```python
def generate_random_character(min_level=1, max_level=1, existing_names=None) -> Dict[str, Any]
def get_xp_for_level(level: int) -> int
def get_level_from_xp(xp: int) -> int
def calculate_level_progress(current_xp: int, stored_level: int = None) -> Dict[str, Any]
def apply_level_up(character_data: Dict[str, Any]) -> Tuple[Dict, Dict]
def add_xp(stats_json: Dict[str, Any], xp_amount: int) -> Dict[str, Any]
def calculate_recruitment_cost(character: Dict[str, Any]) -> int

# Constantes
XP_TABLE: Dict[int, int]
SKILL_POINTS_PER_LEVEL = 4
AVAILABLE_FEATS: List[str]
```

### core/mrg_engine.py
```python
class ResultType(Enum):
    CRITICAL_SUCCESS, TOTAL_SUCCESS, PARTIAL_SUCCESS,
    PARTIAL_FAILURE, TOTAL_FAILURE, CRITICAL_FAILURE

class BenefitType(Enum):
    EFFICIENCY, PRESTIGE, IMPETUS

class MalusType(Enum):
    OPERATIVE_DOWN, DISCREDIT, EXPOSURE

@dataclass
class MRGRoll
@dataclass
class MRGResult

def roll_2d50() -> MRGRoll
def calculate_asymptotic_bonus(merit_points: int) -> int
def determine_result_type(roll: MRGRoll, margin: int) -> ResultType
def resolve_action(merit_points: int, difficulty: int, action_description: str = "") -> MRGResult
```

### core/mrg_constants.py
```python
DICE_SIDES = 50
CRITICAL_FAILURE_MAX = 5
CRITICAL_SUCCESS_MIN = 96
MARGIN_TOTAL_SUCCESS = 25
MARGIN_PARTIAL_SUCCESS = 0
MARGIN_PARTIAL_FAILURE = -25

DIFFICULTY_TRIVIAL = 20
DIFFICULTY_EASY = 35
DIFFICULTY_NORMAL = 50
DIFFICULTY_HARD = 65
DIFFICULTY_VERY_HARD = 80
DIFFICULTY_HEROIC = 95
DIFFICULTY_LEGENDARY = 110
DIFFICULTY_PRESETS: Dict[str, int]

BENEFIT_EFFICIENCY_REFUND = 0.50
BENEFIT_PRESTIGE_GAIN = 0.05
MALUS_OPERATIVE_DOWN_TICKS = 2
```

### core/mrg_effects.py
```python
def apply_benefit(benefit: BenefitType, player_id: int, character_id: int, mission_energy_cost: int = 0) -> str
def apply_malus(malus: MalusType, player_id: int, character_id: int) -> str
def apply_partial_success_complication(result: MRGResult, player_id: int) -> None
```

### core/time_engine.py
```python
def get_server_time() -> datetime
def is_lock_in_window() -> bool
def check_and_trigger_tick() -> None
def debug_force_tick() -> None
def get_world_status_display() -> dict
```

### core/economy_engine.py
```python
def calculate_security_multiplier(infrastructure_defense: int) -> float
def calculate_income(population: int, security: float, happiness: float = 1.0) -> int
def calculate_building_maintenance(buildings: List[Dict]) -> Dict[str, int]
def calculate_planet_production(buildings: List[Dict]) -> ProductionSummary
def run_economy_tick_for_player(player_id: int) -> EconomyTickResult
def run_global_economy_tick() -> List[EconomyTickResult]
def get_planet_economy_summary(planet: Dict) -> Dict[str, Any]

@dataclass
class CascadeResult
@dataclass
class PlanetTickResult
```

### core/prestige_engine.py
```python
class FactionState(Enum):
    HEGEMONIC, NORMAL, IRRELEVANT, COLLAPSED

@dataclass
class PrestigeTransfer

def calculate_idp(attacker_prestige: float, defender_prestige: float) -> float
def calculate_transfer(base_event: float, attacker_prestige: float, defender_prestige: float) -> Tuple[float, float]
def determine_faction_state(prestige: float, is_hegemon: bool = False) -> FactionState
def check_hegemony_ascension(prestige: float, current_state: FactionState) -> bool
def check_hegemony_fall(prestige: float, current_state: FactionState) -> bool
def calculate_friction(factions: Dict[int, float]) -> Dict[int, float]
def apply_prestige_changes(factions: Dict[int, float], adjustments: Dict[int, float]) -> Dict[int, float]
def validate_zero_sum(factions: Dict[int, float], tolerance: float = 0.01) -> bool
def get_top_faction(factions: Dict[int, float]) -> Tuple[int, float]
def is_near_hegemony(prestige: float, threshold_distance: float = 3.0) -> bool
```

### core/world_models.py (Dataclasses)
```python
@dataclass Star
@dataclass Moon
@dataclass CelestialBody
@dataclass Planet(CelestialBody)
@dataclass AsteroidBelt(CelestialBody)
@dataclass System
@dataclass Galaxy
```

### core/world_constants.py
```python
STAR_TYPES: Dict[str, Dict]
METAL_RESOURCES: Dict[str, Dict]
BASE_TIER_COSTS: Dict[int, Dict]
INFRASTRUCTURE_MODULES: Dict[str, Dict]
BUILDING_TYPES: Dict[str, Dict]
BUILDING_SHUTDOWN_PRIORITY: Dict[str, int]
ECONOMY_RATES: Dict[str, float]
BROKER_PRICES: Dict[str, int]
```

### core/galaxy_generator.py
```python
class GalaxyGenerator:
    def __init__(self, seed: int = 42, num_systems: int = 30)
    def generate_galaxy(self) -> Galaxy

GALAXY: Galaxy  # Singleton
def get_galaxy() -> Galaxy
```

---

### data/database.py
```python
@dataclass
class ConnectionStatus

class ServiceContainer:  # Singleton
    @property supabase -> Any
    @property ai -> Any
    @property status -> ConnectionStatus
    def is_supabase_available() -> bool
    def is_ai_available() -> bool
    def inject_supabase(client) -> None  # Para testing
    def inject_ai(client) -> None  # Para testing

def get_service_container() -> ServiceContainer
def get_supabase() -> Any
def get_ai_client() -> Any

# Legacy (usar get_supabase() preferiblemente)
supabase = ...
ai_client = ...
```

### data/player_repository.py
```python
def get_all_players() -> List[Dict[str, Any]]
def get_player_by_id(player_id: int) -> Optional[Dict[str, Any]]
def get_player_by_name(name: str) -> Optional[Dict[str, Any]]
def get_player_by_session_token(token: str) -> Optional[Dict[str, Any]]
def create_session_token(player_id: int) -> str
def clear_session_token(player_id: int) -> None
def authenticate_player(name: str, pin: str) -> Optional[Dict[str, Any]]
def register_player_account(user_name: str, pin: str, faction_name: str, banner_file: Optional[IO]) -> Optional[Dict]
def get_player_finances(player_id: int) -> Dict[str, Any]
def get_player_resources(player_id: int) -> Dict[str, Any]  # Alias
def get_player_credits(player_id: int) -> int
def update_player_resources(player_id: int, updates: Dict) -> bool
def update_player_credits(player_id: int, new_credits: int) -> bool
def add_player_credits(player_id: int, amount: int) -> bool
def delete_player_account(player_id: int) -> bool
```

### data/character_repository.py
```python
def get_commander_by_player_id(player_id: int) -> Optional[Dict[str, Any]]
def create_commander(player_id: int, name: str, bio_data: Dict, attributes: Dict[str, int]) -> Optional[Dict]
def update_commander_profile(player_id: int, bio_data: Dict, attributes: Dict[str, int]) -> Optional[Dict]
def create_character(player_id: int, character_data: Dict) -> Optional[Dict]
def get_all_characters_by_player_id(player_id: int) -> List[Dict[str, Any]]
def update_character(character_id: int, data: Dict) -> Optional[Dict]
def get_character_by_id(character_id: int) -> Optional[Dict[str, Any]]
def update_character_xp(character_id: int, new_xp: int, player_id: int = None) -> Optional[Dict]
def add_xp_to_character(character_id: int, xp_amount: int, player_id: int = None) -> Optional[Dict]
def update_character_stats(character_id: int, new_stats_json: Dict, player_id: int = None) -> Optional[Dict]
def update_character_level(character_id: int, new_level: int, new_stats_json: Dict, player_id: int = None) -> Optional[Dict]
def recruit_character(player_id: int, character_data: Dict) -> Optional[Dict]  # Alias
```

### data/planet_repository.py
```python
def get_planet_asset(planet_id: int, player_id: int) -> Optional[Dict]
def get_planet_asset_by_id(planet_asset_id: int) -> Optional[Dict]
def get_all_player_planets(player_id: int) -> List[Dict]
def get_all_player_planets_with_buildings(player_id: int) -> List[Dict]
def create_planet_asset(planet_id: int, system_id: int, player_id: int, settlement_name: str = "Colonia Principal", initial_population: int = 1000) -> Optional[Dict]
def get_base_slots_info(planet_asset_id: int) -> Dict[str, int]
def upgrade_base_tier(planet_asset_id: int, player_id: int) -> bool
def upgrade_infrastructure_module(planet_asset_id: int, module_key: str, player_id: int) -> str
def get_planet_buildings(planet_asset_id: int) -> List[Dict]
def build_structure(planet_asset_id: int, player_id: int, building_type: str, tier: int = 1) -> Optional[Dict]
def demolish_building(building_id: int, player_id: int) -> bool
def get_luxury_extraction_sites_for_player(player_id: int) -> List[Dict]
def batch_update_planet_security(updates: List[Tuple[int, float]]) -> bool
def batch_update_building_status(updates: List[Tuple[int, bool]]) -> Tuple[int, int]
def update_planet_asset(planet_asset_id: int, updates: Dict) -> bool
```

### data/world_repository.py
```python
def get_world_state() -> Dict[str, Any]
def queue_player_action(player_id: int, action_text: str) -> bool
def try_trigger_db_tick(target_date_iso: str) -> bool
def force_db_tick() -> bool
def get_pending_actions_count(player_id: int) -> int
def get_all_pending_actions() -> List[Dict]
def mark_action_processed(action_id: int, result_status: str) -> None
def get_commander_location_display(commander_id: int) -> Dict[str, str]
def get_all_systems_from_db() -> List[Dict]
def get_system_by_id(system_id: int) -> Optional[Dict]
def get_planets_by_system_id(system_id: int) -> List[Dict]
def get_starlanes_from_db() -> List[Dict]
```

### data/log_repository.py
```python
def log_event(message: str, player_id: int = None, event_type: str = "GENERAL", is_error: bool = False) -> None
def get_recent_logs(player_id: int, limit: int = 20) -> List[Dict]
def clear_player_logs(player_id: int) -> bool
def get_global_logs(limit: int = 50) -> List[Dict]
```

---

### services/gemini_service.py
```python
@dataclass ActionResult
@dataclass TacticalContext

def resolve_player_action(action_text: str, player_id: int) -> Optional[Dict[str, Any]]
def check_ai_status() -> Dict[str, Any]
```

### services/ai_tools.py
```python
TOOL_DECLARATIONS: List[types.Tool]
TOOL_FUNCTIONS: Dict[str, Callable]

def get_player_status(player_id: int) -> str
def scan_system_data(system_identifier: str) -> str
def check_route_safety(origin_sys_id: int, target_sys_id: int) -> str
def execute_tool(function_name: str, arguments: Dict) -> str
```

### services/event_service.py
```python
def generate_tick_event(tick_number: int) -> str
```

---

### ui/state.py
```python
@dataclass SessionState

def initialize_session_state() -> None
def get_session_state() -> SessionState
def login_user(player_data: Dict, commander_data: Dict) -> None
def logout_user(cookie_manager=None) -> None
def start_registration() -> None
def cancel_registration() -> None
def next_registration_step() -> None
def prev_registration_step() -> None
def get_player() -> Optional[PlayerData]
def get_player_dict() -> Optional[Dict]
def get_commander() -> Optional[CommanderData]
def get_commander_dict() -> Optional[Dict]
def get_player_id() -> Optional[int]
def is_logged_in() -> bool
def update_player_resources(resources: Dict[str, int]) -> None
def refresh_player_data(new_data: Dict) -> None
def refresh_commander_data(new_data: Dict) -> None
```

---

### utils/security.py
```python
def hash_password(password: str) -> str
def verify_password(stored_password: str, provided_password: str) -> bool
```

### utils/helpers.py
```python
def encode_image(image_file: IO[bytes]) -> str
```

---

## 4. EJEMPLOS DE USO COMPLETOS

### Ejemplo: Crear un nuevo archivo en core/
```python
# core/mi_nuevo_modulo.py
from typing import Dict, Any
from .constants import RACES, SKILL_MAPPING  # Relativo - mismo paquete
from .rules import calculate_skills          # Relativo - mismo paquete
from data.log_repository import log_event    # Absoluto - otro paquete
from config.app_constants import DEFAULT_PLAYER_CREDITS  # Absoluto

def mi_funcion(player_id: int) -> Dict[str, Any]:
    log_event("Ejecutando mi función", player_id)
    return {"resultado": "ok"}
```

### Ejemplo: Crear un nuevo archivo en ui/
```python
# ui/mi_nueva_pagina.py
import streamlit as st
from .state import get_player, get_commander, is_logged_in  # Relativo
from data.player_repository import get_player_finances       # Absoluto
from data.character_repository import get_all_characters_by_player_id
from services.gemini_service import resolve_player_action
from core.time_engine import get_world_status_display

def render_mi_pagina():
    if not is_logged_in():
        st.error("Debes iniciar sesión")
        return

    player = get_player()
    finances = get_player_finances(player.id)
    st.write(f"Créditos: {finances['creditos']}")
```

### Ejemplo: Crear un nuevo archivo en data/
```python
# data/mi_nuevo_repository.py
from typing import Dict, Any, List, Optional
from .database import get_supabase  # Relativo - mismo paquete
from data.log_repository import log_event  # Absoluto (también funciona)
from core.rules import calculate_skills  # Absoluto - otro paquete

def _get_db():
    return get_supabase()

def mi_query(player_id: int) -> List[Dict]:
    try:
        response = _get_db().table("mi_tabla").select("*").eq("player_id", player_id).execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error: {e}", player_id, is_error=True)
        return []
```

---

## 5. ERRORES COMUNES A EVITAR

```python
# ERROR: Import desde paquete sin especificar módulo
from core import RACES  # MAL

# CORRECTO:
from core.constants import RACES  # BIEN

# ERROR: Import relativo fuera del paquete
from ..data.database import supabase  # MAL (desde core/)

# CORRECTO:
from data.database import get_supabase  # BIEN

# ERROR: Usar supabase directo sin importar
supabase.table(...)  # MAL - variable no definida

# CORRECTO:
from data.database import get_supabase
db = get_supabase()
db.table(...)  # BIEN
```
