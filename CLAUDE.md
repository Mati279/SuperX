# SuperX - Directivas para IA

## REGLAS DE IMPORT (CRÍTICO)

### Entre módulos diferentes: ABSOLUTOS desde raíz
```python
from core.rules import calculate_skills
from data.database import get_supabase
from config.app_constants import SESSION_COOKIE_NAME
from services.gemini_service import resolve_player_action
```

### Dentro del mismo paquete: RELATIVOS con `.`
```python
# Desde core/mrg_effects.py:
from .mrg_engine import MRGResult, ResultType
from .mrg_constants import DIFFICULTY_NORMAL

# Desde ui/auth_page.py:
from .state import login_user, start_registration

# Desde data/character_repository.py:
from .database import supabase
```

## ESTRUCTURA DEL PROYECTO

```
SuperX/
├── config/
│   ├── settings.py          # get_secret(), SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY
│   └── app_constants.py     # Constantes globales (UI, auth, tiempo, IA)
├── core/
│   ├── constants.py          # RACES, CLASSES, SKILL_MAPPING
│   ├── rules.py              # calculate_skills(), calculate_attribute_cost(), get_color_for_level()
│   ├── models.py             # PlayerData, CommanderData, PlayerResources, etc. (Pydantic)
│   ├── character_engine.py   # generate_random_character(), apply_level_up(), add_xp()
│   ├── economy_engine.py     # run_economy_tick_for_player(), calculate_income()
│   ├── mrg_engine.py         # resolve_action(), ResultType, BenefitType, MalusType
│   ├── mrg_constants.py      # DIFFICULTY_*, constantes MRG
│   ├── mrg_effects.py        # apply_benefit(), apply_malus()
│   ├── time_engine.py        # check_and_trigger_tick(), is_lock_in_window(), get_world_status_display()
│   ├── prestige_engine.py    # calculate_idp(), calculate_friction(), FactionState
│   ├── prestige_constants.py # HEGEMONY_THRESHOLD, FRICTION_RATE, etc.
│   ├── world_models.py       # Galaxy, System, Star, Planet, Moon (dataclasses)
│   ├── world_constants.py    # BUILDING_TYPES, ECONOMY_RATES, STAR_TYPES
│   └── galaxy_generator.py   # GalaxyGenerator, get_galaxy(), GALAXY
├── data/
│   ├── database.py           # get_supabase(), get_ai_client(), ServiceContainer, supabase (legacy)
│   ├── player_repository.py  # get_player_by_id(), authenticate_player(), register_player_account()
│   ├── character_repository.py # get_commander_by_player_id(), create_character(), update_character()
│   ├── planet_repository.py  # get_all_player_planets(), build_structure(), get_planet_buildings()
│   ├── world_repository.py   # get_world_state(), queue_player_action(), get_all_systems_from_db()
│   └── log_repository.py     # log_event(), get_recent_logs(), clear_player_logs()
├── services/
│   ├── gemini_service.py     # resolve_player_action(), check_ai_status()
│   ├── ai_tools.py           # TOOL_DECLARATIONS, execute_tool()
│   └── event_service.py      # generate_tick_event()
├── ui/
│   ├── state.py              # initialize_session_state(), login_user(), logout_user(), get_player()
│   ├── auth_page.py          # render_auth_page()
│   ├── main_game_page.py     # render_main_game_page()
│   └── [otras páginas]
└── utils/
    ├── security.py           # hash_password(), verify_password()
    └── helpers.py            # encode_image()
```

## EJEMPLOS DE IMPORTS POR CAPA

### Desde UI
```python
from .state import login_user, get_player, get_commander
from data.player_repository import authenticate_player
from data.character_repository import get_commander_by_player_id
from services.gemini_service import resolve_player_action
from config.app_constants import SESSION_COOKIE_NAME
```

### Desde Data
```python
from .database import get_supabase, supabase
from data.log_repository import log_event
from core.rules import calculate_skills
from utils.security import hash_password
```

### Desde Core
```python
from .constants import RACES, CLASSES, SKILL_MAPPING
from .mrg_constants import DIFFICULTY_NORMAL
from data.log_repository import log_event
from data.character_repository import update_character
```

### Desde Services
```python
from data.database import get_service_container
from data.log_repository import log_event
from core.mrg_engine import resolve_action, ResultType
from config.app_constants import TEXT_MODEL_NAME
```

## NOTAS IMPORTANTES

1. Los `__init__.py` están VACÍOS - no re-exportan nada
2. Siempre importar directamente del módulo específico
3. `supabase` en data/database.py es variable legacy - preferir `get_supabase()`
4. Los modelos Pydantic están en `core/models.py`
5. Los dataclasses de mundo están en `core/world_models.py`
