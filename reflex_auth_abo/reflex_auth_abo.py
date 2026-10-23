import os
import reflex as rx
from supabase import create_client
from dotenv import load_dotenv
 
# .env nur lokal laden; auf Render kommen die Variablen aus dem Dashboard
if os.getenv("REFLEX_ENV") != "prod" and os.getenv("RENDER") is None:
    load_dotenv()
 
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")
 
ACCESS_TOKEN_KEY = "supabase_access_token"
REFRESH_TOKEN_KEY = "supabase_refresh_token"
 
 
def make_supabase_client():
    # Neuer Client pro Aufruf: keine geteilte Session zwischen Nutzern
    return create_client(SUPABASE_URL, SUPABASE_KEY)
 
 
class AuthState(rx.State):
    user_email: str = ""
    is_logged_in: bool = False
    error: str = ""
    success: str = ""
 
    # Im Browser gespeichert, damit die Sitzung Neustarts des Servers überlebt
    access_token: str = rx.LocalStorage("", name=ACCESS_TOKEN_KEY)
    refresh_token: str = rx.LocalStorage("", name=REFRESH_TOKEN_KEY)
 
    def clear_messages(self):
        self.error = ""
        self.success = ""
 
    # ── Hilfsfunktionen ─────────────────
    def _set_tokens(self, access: str | None, refresh: str | None):
        self.access_token = access or ""
        self.refresh_token = refresh or ""
 
    def _clear_auth(self):
        self._set_tokens(None, None)
        self.user_email = ""
        self.is_logged_in = False
 
    # ── Login ───────────────────────────
    def sign_in(self, form_data: dict):
        self.error = ""
        self.success = ""
        self._clear_auth()
 
        try:
            supabase = make_supabase_client()
            response = supabase.auth.sign_in_with_password(
                {"email": form_data["email"], "password": form_data["password"]}
            )
 
            session = getattr(response, "session", None)
            if not session or not session.access_token:
                self.error = "Login fehlgeschlagen: keine Session erhalten."
                return
 
            # Token validieren und E-Mail holen
            user_resp = supabase.auth.get_user(session.access_token)
            user = getattr(user_resp, "user", None)
            if not user or not getattr(user, "email", None):
                self.error = "Login fehlgeschlagen: Token ungültig."
                return
 
            self._set_tokens(session.access_token, session.refresh_token)
            self.user_email = user.email
            self.is_logged_in = True
            return rx.redirect("/dashboard")
 
        except Exception as e:
            self.error = "Login fehlgeschlagen: " + str(e)
 
    # ── Registrierung ───────────────────
    def sign_up(self, form_data: dict):
        self.error = ""
        self.success = ""
        self._clear_auth()
 
        email = form_data.get("email", "").strip()
        password = form_data.get("password", "")
        password_repeat = form_data.get("password_repeat", "")
 
        if not email or not password:
            self.error = "Bitte E-Mail und Passwort eingeben."
            return
        if len(password) < 6:
            self.error = "Das Passwort muss mindestens 6 Zeichen lang sein."
            return
        if password != password_repeat:
            self.error = "Die Passwörter stimmen nicht überein."
            return
 
        try:
            supabase = make_supabase_client()
            response = supabase.auth.sign_up({"email": email, "password": password})
 
            # Bereits registrierte E-Mail (bei aktivierter E-Mail-Bestätigung)
            if getattr(response, "user", None) and getattr(response.user, "identities", None) == []:
                self.error = "Diese E-Mail ist bereits registriert."
                return
 
            # E-Mail-Bestätigung deaktiviert: Session kommt sofort zurück
            session = getattr(response, "session", None)
            if session and session.access_token:
                self._set_tokens(session.access_token, session.refresh_token)
                self.user_email = response.user.email if response.user and response.user.email else email
                self.is_logged_in = True
                return rx.redirect("/dashboard")
 
            # Sonst: Bestätigung per E-Mail nötig
            self.success = (
                "Registrierung erfolgreich! Bitte bestätige deine E-Mail-Adresse "
                "über den Link, den wir dir geschickt haben, und melde dich dann an."
            )
 
        except Exception as e:
            self.error = "Registrierung fehlgeschlagen: " + str(e)
 
    # ── Logout ──────────────────────────
    def sign_out(self):
        access, refresh = self.access_token, self.refresh_token
 
        # Lokal immer abmelden
        self._clear_auth()
        self.error = ""
        self.success = ""
 
        # Zusätzlich die Supabase-Session beenden (nur diese Sitzung)
        if access and refresh:
            try:
                supabase = make_supabase_client()
                supabase.auth.set_session(access, refresh)
                supabase.auth.sign_out({"scope": "local"})
            except Exception as e:
                # erscheint in den Logs, statt verschluckt zu werden
                print(f"Server-side sign_out failed: {e}")
 
        return rx.redirect("/login")
 
    # ── Schutz geschützter Seiten ───────
    def check_auth(self):
        supabase = make_supabase_client()
 
        # 1) Access-Token prüfen
        if self.access_token:
            try:
                resp = supabase.auth.get_user(self.access_token)
                user = getattr(resp, "user", None)
                if user and getattr(user, "email", None):
                    self.user_email = user.email
                    self.is_logged_in = True
                    return
            except Exception:
                pass  # abgelaufen oder ungültig -> Schritt 2
 
        # 2) Mit dem Refresh-Token ein neues Token holen
        if self.refresh_token:
            try:
                resp = supabase.auth.refresh_session(self.refresh_token)
                session = getattr(resp, "session", None)
                user = getattr(resp, "user", None)
                if session and user and getattr(user, "email", None):
                    self._set_tokens(session.access_token, session.refresh_token)
                    self.user_email = user.email
                    self.is_logged_in = True
                    return
            except Exception:
                pass
 
        # 3) Nichts hat geklappt -> abmelden und zum Login
        self._clear_auth()
        return rx.redirect("/login")
 
 
# ─────────────────────────────────────────
# GEMEINSAME BAUSTEINE
# ─────────────────────────────────────────
 
def message_boxes() -> rx.Component:
    return rx.fragment(
        rx.cond(
            AuthState.error != "",
            rx.callout(AuthState.error, color_scheme="red", icon="triangle_alert"),
        ),
        rx.cond(
            AuthState.success != "",
            rx.callout(AuthState.success, color_scheme="green", icon="check"),
        ),
    )
 
 
# ─────────────────────────────────────────
# SEITEN
# ─────────────────────────────────────────
 
def login_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                rx.heading("Anmelden", size="6"),
                message_boxes(),
                rx.form(
                    rx.vstack(
                        rx.input(name="email", placeholder="E-Mail", type="email", width="100%"),
                        rx.input(name="password", placeholder="Passwort", type="password", width="100%"),
                        rx.button("Anmelden", type="submit", width="100%"),
                        spacing="3",
                    ),
                    on_submit=AuthState.sign_in,
                    width="100%",
                ),
                rx.hstack(
                    rx.text("Noch kein Konto?", size="2"),
                    rx.link("Jetzt registrieren", href="/", size="2"),
                    spacing="2",
                ),
                width="320px",
                spacing="4",
            ),
            padding="2rem",
        ),
        height="100vh",
        on_mount=AuthState.clear_messages,
    )
 
 
def register_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                rx.heading("Registrieren", size="6"),
                message_boxes(),
                rx.form(
                    rx.vstack(
                        rx.input(name="email", placeholder="E-Mail", type="email", required=True, width="100%"),
                        rx.input(
                            name="password",
                            placeholder="Passwort (min. 6 Zeichen)",
                            type="password",
                            required=True,
                            width="100%",
                        ),
                        rx.input(
                            name="password_repeat",
                            placeholder="Passwort wiederholen",
                            type="password",
                            required=True,
                            width="100%",
                        ),
                        rx.button("Konto erstellen", type="submit", width="100%"),
                        spacing="3",
                    ),
                    on_submit=AuthState.sign_up,
                    reset_on_submit=True,
                    width="100%",
                ),
                rx.hstack(
                    rx.text("Bereits ein Konto?", size="2"),
                    rx.link("Zum Login", href="/login", size="2"),
                    spacing="2",
                ),
                width="320px",
                spacing="4",
            ),
            padding="2rem",
        ),
        height="100vh",
        on_mount=AuthState.clear_messages,
    )
 
 
def dashboard_content() -> rx.Component:
    """Der eigentliche Dashboard-Inhalt (wird erst nach bestätigtem Login angezeigt)."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Mein Dashboard", size="5"),
            rx.spacer(),
            rx.text(AuthState.user_email, color_scheme="gray", size="2"),
            rx.button("Abmelden", on_click=AuthState.sign_out, variant="outline", size="2"),
            width="100%",
            padding="1rem 2rem",
            border_bottom="1px solid #eee",
        ),
        rx.box(
            rx.vstack(
                rx.heading(f"Willkommen, {AuthState.user_email}!", size="7"),
                rx.text("Du bist erfolgreich eingeloggt.", color_scheme="gray"),
                rx.divider(),
                rx.hstack(
                    rx.card(
                        rx.vstack(
                            rx.text("Umsatz", size="2", color_scheme="gray"),
                            rx.heading("€1.240", size="6"),
                        ),
                        padding="1.5rem",
                    ),
                    rx.card(
                        rx.vstack(
                            rx.text("Nutzer", size="2", color_scheme="gray"),
                            rx.heading("38", size="6"),
                        ),
                        padding="1.5rem",
                    ),
                    rx.card(
                        rx.vstack(
                            rx.text("Aktive Abos", size="2", color_scheme="gray"),
                            rx.heading("12", size="6"),
                        ),
                        padding="1.5rem",
                    ),
                    spacing="4",
                    flex_wrap="wrap",
                ),
                spacing="6",
                align_items="start",
            ),
            padding="2rem",
            width="100%",
        ),
        width="100%",
        spacing="0",
    )
 
 
def dashboard() -> rx.Component:
    # Bis check_auth den Login bestätigt hat, wird nur ein Ladekreis gezeigt.
    return rx.cond(
        AuthState.is_logged_in,
        dashboard_content(),
        rx.center(rx.spinner(size="3"), height="100vh"),
    )
 
 
# ─────────────────────────────────────────
# APP UND SEITEN
# ─────────────────────────────────────────
 
app = rx.App()
app.add_page(login_page, route="/login")   # wird von sign_out/check_auth benutzt
app.add_page(register_page, route="/")
app.add_page(dashboard, route="/dashboard", on_load=AuthState.check_auth)
