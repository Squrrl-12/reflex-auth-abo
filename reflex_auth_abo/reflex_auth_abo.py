# myapp/myapp.py
import os
import reflex as rx
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"],
)


# ─────────────────────────────────────────
# STATE
# ─────────────────────────────────────────

class AuthState(rx.State):
    user_email: str = ""
    is_logged_in: bool = False
    error: str = ""
    success: str = ""

    def clear_messages(self):
        """Beim Laden von Login-/Registrierungsseite alte Meldungen löschen."""
        self.error = ""
        self.success = ""

    # ── Login ───────────────────────────
    def sign_in(self, form_data: dict):
        self.error = ""
        self.success = ""
        try:
            response = supabase.auth.sign_in_with_password({
                "email": form_data["email"],
                "password": form_data["password"],
            })
            if response.user:
                self.user_email = response.user.email
                self.is_logged_in = True
                return rx.redirect("/dashboard")
        except Exception as e:
            self.error = "Login fehlgeschlagen: " + str(e)

    # ── Registrierung ───────────────────
    def sign_up(self, form_data: dict):
        self.error = ""
        self.success = ""

        email = form_data.get("email", "").strip()
        password = form_data.get("password", "")
        password_repeat = form_data.get("password_repeat", "")

        # Eingaben prüfen
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
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
            })

            # Supabase gibt bei bereits registrierter E-Mail (und aktivierter
            # E-Mail-Bestätigung) einen User mit leerer identities-Liste zurück.
            if response.user and response.user.identities == []:
                self.error = "Diese E-Mail ist bereits registriert."
                return

            if response.session:
                # E-Mail-Bestätigung ist in Supabase deaktiviert → direkt eingeloggt
                self.user_email = response.user.email
                self.is_logged_in = True
                return rx.redirect("/dashboard")

            # E-Mail-Bestätigung ist aktiviert → Nutzer muss Mail bestätigen
            self.success = (
                "Registrierung erfolgreich! Bitte bestätige deine E-Mail-Adresse "
                "über den Link, den wir dir geschickt haben, und melde dich dann an."
            )
        except Exception as e:
            self.error = "Registrierung fehlgeschlagen: " + str(e)

    # ── Logout / Schutz ─────────────────
    def sign_out(self):
        supabase.auth.sign_out()
        self.user_email = ""
        self.is_logged_in = False
        return rx.redirect("/login")

    def check_auth(self):
        """Wird beim Laden jeder geschützten Seite aufgerufen."""
        if not self.is_logged_in:
            return rx.redirect("/login")


# ─────────────────────────────────────────
# GEMEINSAME BAUSTEINE
# ─────────────────────────────────────────

def message_boxes() -> rx.Component:
    """Zeigt Fehler- und Erfolgsmeldungen an."""
    return rx.fragment(
        rx.cond(
            AuthState.error != "",
            rx.callout(
                AuthState.error,
                color_scheme="red",
                icon="triangle_alert",
            ),
        ),
        rx.cond(
            AuthState.success != "",
            rx.callout(
                AuthState.success,
                color_scheme="green",
                icon="check",
            ),
        ),
    )


# ─────────────────────────────────────────
# SEITE 1: LOGIN
# ─────────────────────────────────────────

def login_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                rx.heading("Anmelden", size="6"),
                message_boxes(),
                rx.form(
                    rx.vstack(
                        rx.input(
                            name="email",
                            placeholder="E-Mail",
                            type="email",
                            width="100%",
                        ),
                        rx.input(
                            name="password",
                            placeholder="Passwort",
                            type="password",
                            width="100%",
                        ),
                        rx.button("Anmelden", type="submit", width="100%"),
                        spacing="3",
                    ),
                    on_submit=AuthState.sign_in,
                    width="100%",
                ),
                rx.hstack(
                    rx.text("Noch kein Konto?", size="2"),
                    rx.link("Jetzt registrieren", href="/register", size="2"),
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


# ─────────────────────────────────────────
# SEITE 2: REGISTRIERUNG
# ─────────────────────────────────────────

def register_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                rx.heading("Registrieren", size="6"),
                message_boxes(),
                rx.form(
                    rx.vstack(
                        rx.input(
                            name="email",
                            placeholder="E-Mail",
                            type="email",
                            required=True,
                            width="100%",
                        ),
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


# ─────────────────────────────────────────
# SEITE 3: DASHBOARD (geschützt)
# ─────────────────────────────────────────

def dashboard() -> rx.Component:
    return rx.vstack(

        # ── Navbar ──────────────────────────
        rx.hstack(
            rx.heading("Mein Dashboard", size="5"),
            rx.spacer(),
            rx.text(AuthState.user_email, color_scheme="gray", size="2"),
            rx.button(
                "Abmelden",
                on_click=AuthState.sign_out,
                variant="outline",
                size="2",
            ),
            width="100%",
            padding="1rem 2rem",
            border_bottom="1px solid #eee",
        ),

        # ── Inhalt ──────────────────────────
        rx.box(
            rx.vstack(
                rx.heading(
                    f"Willkommen, {AuthState.user_email}!",
                    size="7",
                ),
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
        on_mount=AuthState.check_auth,  # Schutz: prüft, ob eingeloggt
    )


# ─────────────────────────────────────────
# APP
# ─────────────────────────────────────────

app = rx.App()
app.add_page(login_page, route="/login")   # wird von sign_out/check_auth benutzt
app.add_page(register_page, route="/")
app.add_page(dashboard, route="/dashboard")
