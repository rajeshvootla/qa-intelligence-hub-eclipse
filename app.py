import streamlit as st

st.set_page_config(page_title="QA Intelligence Hub - Eclipse", page_icon="🧭", layout="wide")
st.title("🧭 QA Intelligence Hub – Eclipse")
st.markdown(
    """
Welcome! Use the sidebar to open a tool.

- **Test Case Generator** – convert manual test cases (pasted text or TestRail CSV export)
  into automated **Playwright + pytest** tests, save them into the `automation/` framework and run them.
"""
)
st.page_link("pages/1_Test_Case_Generator.py", label="Open Test Case Generator", icon="🧪")
