import streamlit as st
from game_engine import supabase, generate_random_character, resolve_action, verify_password

def run_test():
    """
    This test will check the following:
    1. User Registration: It will create a new user with a faction and a banner.
    2. User Login: It will log in with the newly created user.
    3. Action Resolution: It will perform an action with the logged-in user.
    """

    # 1. User Registration
    st.header("1. User Registration")
    with st.spinner("Registering a new user..."):
        try:
            # Check if the user already exists and delete it
            try:
                supabase.table("players").delete().eq("nombre", "test_user").execute()
            except Exception:
                pass

            # Create a dummy banner file
            with open("test_banner.png", "w") as f:
                f.write("test")

            with open("test_banner.png", "rb") as f:
                new_player = generate_random_character(
                    player_name="test_user",
                    password="password",
                    faction_name="Test Faction",
                    banner_file=f,
                )

            if new_player:
                st.success("User registered successfully.")
                st.json(new_player)
            else:
                st.error("User registration failed.")
                return
        except Exception as e:
            st.error(f"An error occurred during user registration: {e}")
            return

    # 2. User Login
    st.header("2. User Login")
    with st.spinner("Logging in..."):
        try:
            response = supabase.table("players").select("*").eq("nombre", "test_user").single().execute()
            player_data = response.data
            if player_data and verify_password(player_data['password'], "password"):
                st.success("User logged in successfully.")
                st.json(player_data)
            else:
                st.error("User login failed.")
                return
        except Exception as e:
            st.error(f"An error occurred during user login: {e}")
            return

    # 3. Action Resolution
    st.header("3. Action Resolution")
    with st.spinner("Resolving an action..."):
        try:
            result = resolve_action("Test action", player_data['id'])
            if result:
                st.success("Action resolved successfully.")
                st.json(result)
            else:
                st.error("Action resolution failed.")
                return
        except Exception as e:
            st.error(f"An error occurred during action resolution: {e}")
            return

if __name__ == "__main__":
    run_test()
