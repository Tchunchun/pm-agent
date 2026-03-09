"""
Login page — renders the Google Sign-In UI when user is not authenticated.
"""

import streamlit as st


def render_login_page(auth_url: str, error: str = "") -> None:
    """
    Render a centered login page with a Google Sign-In button.

    Args:
        auth_url: The Google OAuth2 consent URL
        error: Optional error message to display
    """
    # Inject login page CSS
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # Centered layout
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div class="login-container">
                <div class="login-card">
                    <div class="login-logo">🧭</div>
                    <div class="login-title">PM Agent</div>
                    <div class="login-subtitle">
                        AI-powered strategy copilot for<br>
                        Technical Program Managers
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if error:
            st.error(error)

        # Google Sign-In button using Streamlit link_button
        st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)

        # Centered button using columns
        bcol1, bcol2, bcol3 = st.columns([1, 2, 1])
        with bcol2:
            st.link_button(
                "🔵  Sign in with Google",
                auth_url,
                use_container_width=True,
            )

        st.markdown(
            """
            <div class="login-footer">
                Sign in with your Google account to get started.<br>
                <span class="login-footer-muted">Your data stays local and private.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


_LOGIN_CSS = """
<style>
.login-container {
    display: flex;
    justify-content: center;
    padding-top: 8vh;
}

.login-card {
    text-align: center;
    padding: 40px 32px 24px;
}

.login-logo {
    font-size: 3.5rem;
    margin-bottom: 12px;
}

.login-title {
    font-family: var(--font-sans, "Inter", sans-serif);
    font-size: 2rem;
    font-weight: 700;
    color: var(--color-text, #1e293b);
    margin-bottom: 8px;
}

.login-subtitle {
    font-family: var(--font-sans, "Inter", sans-serif);
    font-size: 1rem;
    font-weight: 400;
    color: var(--color-text-secondary, #475569);
    line-height: 1.6;
    margin-bottom: 24px;
}

.login-footer {
    text-align: center;
    font-family: var(--font-sans, "Inter", sans-serif);
    font-size: 0.8rem;
    color: var(--color-text-secondary, #475569);
    line-height: 1.6;
    margin-top: 20px;
}

.login-footer-muted {
    color: var(--color-text-muted, #94a3b8);
    font-size: 0.75rem;
}

/* Style the Streamlit link button to look like Google Sign-In */
div[data-testid="stLinkButton"] a {
    background-color: var(--color-accent, #3b82f6) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 10px 24px !important;
    font-family: var(--font-sans, "Inter", sans-serif) !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    transition: background-color 0.15s ease !important;
}

div[data-testid="stLinkButton"] a:hover {
    background-color: var(--color-accent-hover, #2563eb) !important;
}
</style>
"""
