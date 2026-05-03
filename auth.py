"""SiteOracle auth — uses Stripe as the source of truth for subscriptions.

No database, no webhooks. Just ask Stripe: "does this email have an active sub?"
"""

import os
import stripe
import streamlit as st

# Stripe payment links (for upgrade buttons)
STRIPE_LINK_PRO = "https://buy.stripe.com/00w4gA9Te1CQ4u290o9Ve04"
STRIPE_LINK_AGENCY = "https://buy.stripe.com/14A28s3uQ0yMf8G1xW9Ve05"

# Plan names — must match what you set in Stripe product catalog
_PLAN_MAP = {
    "SiteOracle Pro": "pro",
    "SiteOracle Agency": "agency",
}


def _get_stripe():
    """Initialize Stripe with the secret key from env."""
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        return None
    stripe.api_key = key
    return stripe


def check_subscription(email: str) -> dict:
    """Look up a customer by email in Stripe and return their plan status.

    Returns:
        {"plan": "free" | "pro" | "agency", "status": "active" | "none", "customer_id": str | None}
    """
    s = _get_stripe()
    if not s or not email:
        return {"plan": "free", "status": "none", "customer_id": None}

    try:
        # Search for customer by email
        customers = s.Customer.list(email=email.strip().lower(), limit=1)
        if not customers.data:
            return {"plan": "free", "status": "none", "customer_id": None}

        customer = customers.data[0]

        # Get active subscriptions for this customer
        subs = s.Subscription.list(
            customer=customer.id,
            status="active",
            limit=5,
        )

        if not subs.data:
            # Check for trialing subs too
            subs = s.Subscription.list(
                customer=customer.id,
                status="trialing",
                limit=5,
            )

        if not subs.data:
            return {"plan": "free", "status": "none", "customer_id": customer.id}

        # Find the highest tier active subscription
        best_plan = "free"
        for sub in subs.data:
            for item in sub["items"]["data"]:
                product_id = item["price"]["product"]
                # Fetch product name
                product = s.Product.retrieve(product_id)
                plan = _PLAN_MAP.get(product.name, "free")
                if plan == "agency":
                    best_plan = "agency"
                elif plan == "pro" and best_plan != "agency":
                    best_plan = "pro"

        return {"plan": best_plan, "status": "active", "customer_id": customer.id}

    except Exception as e:
        # Don't break the app if Stripe is down — just treat as free
        st.warning(f"Could not verify subscription: {e}")
        return {"plan": "free", "status": "none", "customer_id": None}


def get_user_plan() -> str:
    """Get the current user's plan from session state. Returns 'free', 'pro', or 'agency'."""
    return st.session_state.get("user_plan", "free")


def is_pro_or_above() -> bool:
    """Check if user has Pro or Agency plan."""
    return get_user_plan() in ("pro", "agency")


def is_agency() -> bool:
    """Check if user has Agency plan."""
    return get_user_plan() == "agency"


def render_sidebar_auth():
    """Render the authentication sidebar — email input + plan status."""
    with st.sidebar:
        st.markdown("### 🔐 Your Account")

        # If already logged in, show status
        if st.session_state.get("user_email"):
            plan = get_user_plan()
            plan_colors = {"free": "#94a3b8", "pro": "#ff6b6b", "agency": "#e3b341"}
            plan_labels = {"free": "Free", "pro": "⚡ Pro", "agency": "🏢 Agency"}

            st.markdown(f"""
            <div style="background: #1e293b; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                <div style="font-size: 13px; color: #94a3b8;">Logged in as</div>
                <div style="font-size: 14px; font-weight: 600; color: #f1f5f9;">{st.session_state.user_email}</div>
                <div style="margin-top: 8px;">
                    <span style="background: {plan_colors[plan]}22; color: {plan_colors[plan]};
                                 padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 700;">
                        {plan_labels[plan]}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if plan == "free":
                st.markdown(f"[⚡ Upgrade to Pro]({STRIPE_LINK_PRO})")
            elif plan == "pro":
                st.markdown(f"[🏢 Upgrade to Agency]({STRIPE_LINK_AGENCY})")

            if st.button("Log out", use_container_width=True):
                del st.session_state["user_email"]
                del st.session_state["user_plan"]
                if "user_customer_id" in st.session_state:
                    del st.session_state["user_customer_id"]
                st.rerun()

        else:
            st.caption("Enter your email to unlock paid features.")
            email = st.text_input("Email", placeholder="you@example.com", key="login_email", label_visibility="collapsed")

            if st.button("Log in", type="primary", use_container_width=True) and email:
                with st.spinner("Checking subscription..."):
                    result = check_subscription(email)

                st.session_state["user_email"] = email.strip().lower()
                st.session_state["user_plan"] = result["plan"]
                if result["customer_id"]:
                    st.session_state["user_customer_id"] = result["customer_id"]
                st.rerun()

            st.markdown("---")
            st.caption("No account yet? Just run a free scan — no login needed.")
            st.markdown(f"[⚡ Get Pro — $49/mo]({STRIPE_LINK_PRO})")
            st.markdown(f"[🏢 Get Agency — $149/mo]({STRIPE_LINK_AGENCY})")


def render_upgrade_card(feature_name: str = "This feature"):
    """Show a styled upgrade card when a free user tries to access a Pro feature."""
    st.markdown(f"""
    <div class="upgrade-card">
        <h2>🔒 {feature_name} — Pro Feature</h2>
        <p>Upgrade to SiteOracle Pro to unlock {feature_name.lower()}, unlimited scans, AI deep analysis, and more.</p>
        <a href="{STRIPE_LINK_PRO}" target="_blank"
           style="display: inline-block; background: #ff5555; color: white; padding: 10px 24px;
                  border-radius: 8px; text-decoration: none; font-weight: 700; margin-top: 8px;">
            ⚡ Get Pro — $49/mo
        </a>
    </div>
    """, unsafe_allow_html=True)
