-- WARNING: This schema is for context only and is not meant to be run.

-- Table order and constraints may not be valid for execution.

-- NOTE: This schema may be outdated. Consult with the owner. 


CREATE TABLE public.action_queue (

  id integer NOT NULL DEFAULT nextval('action_queue_id_seq'::regclass),

  player_id integer,

  action_text text NOT NULL,

  status text DEFAULT 'PENDING'::text,

  created_at timestamp with time zone DEFAULT now(),

  processed_at timestamp with time zone,

  CONSTRAINT action_queue_pkey PRIMARY KEY (id),

  CONSTRAINT action_queue_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id)

);

CREATE TABLE public.active_missions (

  id integer NOT NULL DEFAULT nextval('active_missions_id_seq'::regclass),

  player_id integer NOT NULL,

  type character varying NOT NULL,

  status character varying DEFAULT 'in_progress'::character varying,

  difficulty integer DEFAULT 50,

  remaining_days integer NOT NULL,

  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT active_missions_pkey PRIMARY KEY (id)

);

CREATE TABLE public.character_knowledge (

  id integer NOT NULL DEFAULT nextval('character_knowledge_id_seq'::regclass),

  character_id integer NOT NULL,

  player_id integer NOT NULL,

  knowledge_level text NOT NULL,

  updated_at timestamp with time zone DEFAULT now(),

  CONSTRAINT character_knowledge_pkey PRIMARY KEY (id)

);

CREATE TABLE public.characters (

  id integer NOT NULL DEFAULT nextval('characters_id_seq'::regclass),

  player_id integer,

  nombre text NOT NULL,

  rango text DEFAULT 'Comandante'::text,

  xp integer DEFAULT 0,

  es_comandante boolean DEFAULT false,

  stats_json jsonb,

  fecha_creacion timestamp with time zone DEFAULT now(),

  recruited_at_tick integer DEFAULT 0,

  apellido text DEFAULT ''::text,

  faction_id integer,

  class_id integer DEFAULT 0,

  level integer DEFAULT 1,

  is_npc boolean DEFAULT false,

  loyalty integer DEFAULT 100 CHECK (loyalty >= 0 AND loyalty <= 100),

  location_planet_id integer,

  location_sector_id integer,

  portrait_url text,

  last_processed_tick integer DEFAULT 0,

  location_system_id integer,

  estado_id integer DEFAULT 1,

  rol integer,

  CONSTRAINT characters_pkey PRIMARY KEY (id),

  CONSTRAINT characters_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id)

);

CREATE TABLE public.economic_config (

  key text NOT NULL,

  value_float double precision,

  value_int integer,

  value_text text,

  description text,

  CONSTRAINT economic_config_pkey PRIMARY KEY (key)

);

CREATE TABLE public.entities (

  id integer NOT NULL DEFAULT nextval('entities_id_seq'::regclass),

  nombre text NOT NULL,

  tipo text NOT NULL DEFAULT 'Operativo'::text,

  stats_json jsonb,

  estado text DEFAULT 'Activo'::text,

  ubicacion text,

  CONSTRAINT entities_pkey PRIMARY KEY (id)

);

CREATE TABLE public.faction_assets (

  id integer NOT NULL DEFAULT nextval('faction_assets_id_seq'::regclass),

  player_id integer NOT NULL,

  location_id character varying NOT NULL,

  type character varying NOT NULL,

  active_pops integer DEFAULT 0,

  security_level double precision DEFAULT 0.5,

  upkeep_cost integer DEFAULT 10,

  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT faction_assets_pkey PRIMARY KEY (id)

);

CREATE TABLE public.factions (

  id integer NOT NULL DEFAULT nextval('factions_id_seq'::regclass),

  nombre text NOT NULL UNIQUE,

  descripcion text,

  prestigio numeric NOT NULL DEFAULT 14.29 CHECK (prestigio >= 0::numeric AND prestigio <= 100::numeric),

  es_hegemon boolean DEFAULT false,

  hegemonia_contador integer DEFAULT 0 CHECK (hegemonia_contador >= 0),

  color_hex text DEFAULT '#888888'::text,

  banner_url text,

  created_at timestamp with time zone DEFAULT now(),

  updated_at timestamp with time zone DEFAULT now(),

  CONSTRAINT factions_pkey PRIMARY KEY (id)

);

CREATE TABLE public.freeze_votes (

  player_id integer NOT NULL,

  vote_type text NOT NULL,

  voted_at timestamp with time zone DEFAULT now(),

  CONSTRAINT freeze_votes_pkey PRIMARY KEY (player_id),

  CONSTRAINT freeze_votes_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id)

);

CREATE TABLE public.game_config (

  key text NOT NULL,

  value text NOT NULL,

  CONSTRAINT game_config_pkey PRIMARY KEY (key)

);

CREATE TABLE public.game_state (

  id integer NOT NULL DEFAULT 1 CHECK (id = 1),

  current_tick bigint NOT NULL DEFAULT 1,

  last_tick_at timestamp with time zone NOT NULL DEFAULT now(),

  CONSTRAINT game_state_pkey PRIMARY KEY (id)

);

CREATE TABLE public.generated_images (

  id integer NOT NULL DEFAULT nextval('generated_images_id_seq'::regclass),

  player_id integer,

  prompt text NOT NULL,

  image_url text NOT NULL,

  created_at timestamp with time zone DEFAULT now(),

  CONSTRAINT generated_images_pkey PRIMARY KEY (id),

  CONSTRAINT generated_images_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id)

);

CREATE TABLE public.logs (

  id integer NOT NULL DEFAULT nextval('logs_id_seq'::regclass),

  turno integer DEFAULT 1,

  player_id integer,

  evento_texto text NOT NULL,

  prompt_imagen text,

  fecha_evento timestamp with time zone DEFAULT now(),

  CONSTRAINT logs_pkey PRIMARY KEY (id),

  CONSTRAINT logs_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id)

);

CREATE TABLE public.luxury_extraction_sites (

  id integer NOT NULL DEFAULT nextval('luxury_extraction_sites_id_seq'::regclass),

  planet_asset_id integer,

  player_id integer,

  resource_key text NOT NULL,

  resource_category text NOT NULL,

  extraction_rate integer DEFAULT 1,

  is_active boolean DEFAULT true,

  pops_required integer DEFAULT 500,

  building_id integer,

  created_at timestamp with time zone DEFAULT now(),

  CONSTRAINT luxury_extraction_sites_pkey PRIMARY KEY (id),

  CONSTRAINT luxury_extraction_sites_building_id_fkey FOREIGN KEY (building_id) REFERENCES public.planet_buildings(id)

);

CREATE TABLE public.market_orders (

  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,

  player_id bigint NOT NULL,

  resource_type text NOT NULL,

  amount integer NOT NULL,

  price_per_unit integer NOT NULL,

  status text NOT NULL DEFAULT 'PENDING'::text,

  created_at_tick integer NOT NULL,

  processed_at_tick integer,

  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),

  CONSTRAINT market_orders_pkey PRIMARY KEY (id)

);

CREATE TABLE public.planet_assets (

  id integer NOT NULL DEFAULT nextval('planet_assets_id_seq'::regclass),

  player_id integer,

  system_id integer,

  planet_id integer,

  nombre_asentamiento text DEFAULT 'Colonia'::text,

  tipo text DEFAULT 'Base'::text,

  nivel integer DEFAULT 1,

  population double precision DEFAULT 0.0,

  pops_activos double precision DEFAULT 0.0,

  pops_desempleados double precision DEFAULT 0.0,

  infraestructura_defensiva integer DEFAULT 0,

  recursos_almacenados jsonb,

  created_at timestamp with time zone DEFAULT now(),

  base_tier integer DEFAULT 1,

  CONSTRAINT planet_assets_pkey PRIMARY KEY (id),

  CONSTRAINT planet_assets_planet_id_fkey FOREIGN KEY (planet_id) REFERENCES public.planets(id),

  CONSTRAINT planet_assets_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id),

  CONSTRAINT planet_assets_system_id_fkey FOREIGN KEY (system_id) REFERENCES public.systems(id)

);

CREATE TABLE public.planet_buildings (

  id integer NOT NULL DEFAULT nextval('planet_buildings_id_seq'::regclass),

  planet_asset_id integer,

  player_id integer,

  building_type text NOT NULL,

  building_tier integer DEFAULT 1,

  is_active boolean DEFAULT true,

  pops_required integer,

  energy_consumption integer DEFAULT 0,

  built_at_tick integer DEFAULT 1,

  created_at timestamp with time zone DEFAULT now(),

  sector_id bigint,

  CONSTRAINT planet_buildings_pkey PRIMARY KEY (id),

  CONSTRAINT planet_buildings_sector_id_fkey FOREIGN KEY (sector_id) REFERENCES public.sectors(id)

);

CREATE TABLE public.planets (

  id integer NOT NULL DEFAULT nextval('planets_id_seq'::regclass),

  system_id integer NOT NULL,

  name text NOT NULL,

  orbital_ring integer NOT NULL,

  biome text NOT NULL,

  mass_class text DEFAULT 'Estándar'::text,

  population double precision DEFAULT 0.0,

  base_defense integer DEFAULT 0,

  security double precision DEFAULT 0.0,

  is_habitable boolean DEFAULT false,

  is_known boolean DEFAULT false,

  is_disputed boolean DEFAULT false,

  max_sectors integer DEFAULT 4,

  slots integer DEFAULT 0,

  orbital_owner_id bigint,

  surface_owner_id bigint,

  created_at timestamp with time zone DEFAULT now(),

  security_breakdown jsonb DEFAULT '{}'::jsonb,

  CONSTRAINT planets_pkey PRIMARY KEY (id),

  CONSTRAINT planets_orbital_owner_id_fkey FOREIGN KEY (orbital_owner_id) REFERENCES public.players(id),

  CONSTRAINT planets_surface_owner_id_fkey FOREIGN KEY (surface_owner_id) REFERENCES public.players(id),

  CONSTRAINT planets_system_id_fkey FOREIGN KEY (system_id) REFERENCES public.systems(id)

);

CREATE TABLE public.player_exploration (

  id integer NOT NULL DEFAULT nextval('player_exploration_id_seq'::regclass),

  player_id integer,

  system_id integer,

  scan_level integer DEFAULT 0,

  updated_at timestamp with time zone DEFAULT now(),

  CONSTRAINT player_exploration_pkey PRIMARY KEY (id),

  CONSTRAINT player_exploration_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id),

  CONSTRAINT player_exploration_system_id_fkey FOREIGN KEY (system_id) REFERENCES public.systems(id)

);

CREATE TABLE public.player_sector_knowledge (

  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,

  player_id bigint NOT NULL,

  sector_id bigint NOT NULL,

  discovered_at timestamp with time zone DEFAULT now(),

  CONSTRAINT player_sector_knowledge_pkey PRIMARY KEY (id),

  CONSTRAINT player_sector_knowledge_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id),

  CONSTRAINT player_sector_knowledge_sector_id_fkey FOREIGN KEY (sector_id) REFERENCES public.sectors(id)

);

CREATE TABLE public.players (

  id integer NOT NULL DEFAULT nextval('players_id_seq'::regclass),

  nombre text NOT NULL UNIQUE,

  pin text NOT NULL,

  faccion_nombre text NOT NULL,

  banner_url text,

  session_token text,

  creditos integer DEFAULT 0,

  materiales integer DEFAULT 0,

  componentes integer DEFAULT 0,

  celulas_energia integer DEFAULT 0,

  influencia integer DEFAULT 0,

  prestige integer DEFAULT 0,

  recursos_lujo jsonb DEFAULT '{}'::jsonb,

  fecha_registro timestamp with time zone DEFAULT now(),

  datos integer DEFAULT 0,

  CONSTRAINT players_pkey PRIMARY KEY (id)

);

CREATE TABLE public.prestige_history (

  id integer NOT NULL DEFAULT nextval('prestige_history_id_seq'::regclass),

  tick integer NOT NULL,

  attacker_faction_id integer,

  defender_faction_id integer,

  amount numeric NOT NULL,

  idp_multiplier numeric,

  reason text,

  created_at timestamp with time zone DEFAULT now(),

  CONSTRAINT prestige_history_pkey PRIMARY KEY (id),

  CONSTRAINT prestige_history_attacker_faction_id_fkey FOREIGN KEY (attacker_faction_id) REFERENCES public.factions(id),

  CONSTRAINT prestige_history_defender_faction_id_fkey FOREIGN KEY (defender_faction_id) REFERENCES public.factions(id)

);

CREATE TABLE public.sectors (

  id bigint NOT NULL,

  planet_id integer,

  name text NOT NULL,

  sector_type text NOT NULL,

  max_slots integer DEFAULT 2,

  resource_category text,

  luxury_resource text,

  is_known boolean DEFAULT false,

  created_at timestamp with time zone DEFAULT now(),

  system_id integer,

  CONSTRAINT sectors_pkey PRIMARY KEY (id),

  CONSTRAINT sectors_system_id_fkey FOREIGN KEY (system_id) REFERENCES public.systems(id),

  CONSTRAINT sectors_planet_id_fkey FOREIGN KEY (planet_id) REFERENCES public.planets(id)

);

CREATE TABLE public.ships (

  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,

  player_id bigint,

  nombre text NOT NULL,

  clase text,

  tipo_casco text,

  ubicacion_system_id bigint,

  capitan_id bigint,

  estado text DEFAULT 'Operativa'::text,

  integridad integer DEFAULT 100,

  fuel_actual integer DEFAULT 100,

  modulos jsonb DEFAULT '{}'::jsonb,

  cargo jsonb DEFAULT '{}'::jsonb,

  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()),

  CONSTRAINT ships_pkey PRIMARY KEY (id)

);

CREATE TABLE public.starlanes (

  id integer NOT NULL DEFAULT nextval('starlanes_id_seq'::regclass),

  system_a_id integer,

  system_b_id integer,

  distancia double precision DEFAULT 1.0,

  tipo text DEFAULT 'Ruta Comercial Estable'::text,

  nivel_riesgo double precision DEFAULT 0.0,

  estado_activo boolean DEFAULT true,

  CONSTRAINT starlanes_pkey PRIMARY KEY (id),

  CONSTRAINT starlanes_system_a_id_fkey FOREIGN KEY (system_a_id) REFERENCES public.systems(id),

  CONSTRAINT starlanes_system_b_id_fkey FOREIGN KEY (system_b_id) REFERENCES public.systems(id)

);

CREATE TABLE public.stellar_buildings (

  id integer NOT NULL DEFAULT nextval('stellar_buildings_id_seq'::regclass),

  sector_id integer NOT NULL,

  player_id integer NOT NULL,

  building_type text NOT NULL,

  is_active boolean DEFAULT true,

  created_at timestamp with time zone DEFAULT now(),

  CONSTRAINT stellar_buildings_pkey PRIMARY KEY (id),

  CONSTRAINT stellar_buildings_sector_id_fkey FOREIGN KEY (sector_id) REFERENCES public.sectors(id),

  CONSTRAINT stellar_buildings_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id)

);

CREATE TABLE public.system_knowledge (

  id integer NOT NULL DEFAULT nextval('system_knowledge_id_seq'::regclass),

  system_id integer NOT NULL,

  faction_id integer NOT NULL,

  knowledge_level text NOT NULL DEFAULT 'Básico'::text,

  discovered_at timestamp with time zone DEFAULT now(),

  updated_at timestamp with time zone DEFAULT now(),

  CONSTRAINT system_knowledge_pkey PRIMARY KEY (id),

  CONSTRAINT system_knowledge_system_id_fkey FOREIGN KEY (system_id) REFERENCES public.systems(id),

  CONSTRAINT system_knowledge_faction_id_fkey FOREIGN KEY (faction_id) REFERENCES public.factions(id)

);

CREATE TABLE public.systems (

  id integer NOT NULL DEFAULT nextval('systems_id_seq'::regclass),

  name text NOT NULL,

  x double precision NOT NULL,

  y double precision NOT NULL,

  star_type text,

  created_at timestamp with time zone DEFAULT now(),

  description text DEFAULT ''::text,

  controlling_player_id bigint,

  security double precision DEFAULT 0.0,

  security_breakdown jsonb DEFAULT '{}'::jsonb,

  CONSTRAINT systems_pkey PRIMARY KEY (id)

);

CREATE TABLE public.world_state (

  id integer NOT NULL DEFAULT nextval('world_state_id_seq'::regclass),

  last_tick_processed_at timestamp with time zone NOT NULL DEFAULT (now() - '1 day'::interval),

  is_frozen boolean DEFAULT false,

  current_tick integer DEFAULT 1,

  created_at timestamp with time zone DEFAULT now(),

  CONSTRAINT world_state_pkey PRIMARY KEY (id)

);