import streamlit as st
from game_engine import (
    supabase, 
    register_player_account, 
    create_commander_manual, 
    resolve_action, 
    verify_password,
    RACES,
    CLASSES
)

def run_test():
    """
    Test actualizado para el nuevo flujo:
    1. Registro de Cuenta (Player)
    2. Creación de Comandante (Character)
    3. Login y Acción
    """

    st.header("1. User Registration (Account)")
    player_data = None
    
    with st.spinner("Creating account..."):
        try:
            # Limpieza previa
            try:
                # Borrar personaje primero por la FK (Cascade debería encargarse, pero por seguridad)
                user_res = supabase.table("players").select("id").eq("nombre", "test_user").execute()
                if user_res.data:
                    pid = user_res.data[0]['id']
                    supabase.table("characters").delete().eq("player_id", pid).execute()
                    supabase.table("players").delete().eq("id", pid).execute()
            except Exception as e:
                st.warning(f"Cleanup warning: {e}")

            # Crear banner dummy
            with open("test_banner.png", "w") as f:
                f.write("test")

            # Paso 1: Crear Cuenta
            with open("test_banner.png", "rb") as f:
                player_data = register_player_account(
                    user_name="test_user",
                    pin="1234",
                    faction_name="Test Faction",
                    banner_file=f
                )

            if player_data:
                st.success("Account created successfully.")
                st.json(player_data)
            else:
                st.error("Account creation failed.")
                return
        except Exception as e:
            st.error(f"Error in Step 1: {e}")
            return

    # 2. Character Creation (Commander)
    st.header("2. Commander Creation")
    with st.spinner("Forging commander..."):
        try:
            # Datos simulados del Wizard
            bio_data = {
                "nombre": "test_user",
                "raza": "Humano",
                "clase": "Soldado",
                "edad": 30,
                "sexo": "Hombre",
                "rol": "Comandante",
                "historia": "Test bio"
            }
            
            # Atributos base
            attributes = {
                "fuerza": 10, "agilidad": 10, "intelecto": 10,
                "tecnica": 10, "presencia": 10, "voluntad": 10
            }
            
            # Aplicar bonos manualmente como hace el Wizard
            # Humano (+1 Voluntad)
            attributes["voluntad"] += 1
            # Soldado (+1 Fuerza)
            attributes["fuerza"] += 1
            
            success = create_commander_manual(
                player_id=player_data['id'],
                name=player_data['nombre'],
                bio_data=bio_data,
                attributes=attributes
            )
            
            if success:
                st.success("Commander created successfully.")
            else:
                st.error("Commander creation failed.")
                return
                
        except Exception as e:
            st.error(f"Error in Step 2: {e}")
            return

    # 3. Action Resolution
    st.header("3. Action Resolution")
    with st.spinner("Resolving action..."):
        try:
            result = resolve_action("Test action", player_data['id'])
            if result:
                st.success("Action resolved.")
                st.json(result)
            else:
                st.error("Action resolution failed.")
        except Exception as e:
            st.error(f"Error in Step 3: {e}")

if __name__ == "__main__":
    run_test()