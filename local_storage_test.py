import streamlit as st
from streamlit_local_storage import LocalStorage

st.title("Local Storage Test")

# Initialize LocalStorage object
local = LocalStorage()

KEY = "my_test_value"

# Load from browser storage
stored_value = local.getItem(KEY)

st.write("📥 Stored value:", stored_value)

# Enter new value
new_value = st.text_input("Enter value to store:", stored_value or "")

# Save
if st.button("Save to LocalStorage"):
    local.setItem(KEY, new_value)
    st.success("Saved! Refresh the page to check persistence.")
