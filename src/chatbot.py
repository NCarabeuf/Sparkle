import json
import os
import threading
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, QPoint, Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase, QPainter, QPixmap
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QLineEdit,
    QTextBrowser,
    QWidget,
)

from src.asset_manager import get_asset


def load_dotenv(env_path: Path | None = None):
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value[:1] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(name, value)


load_dotenv()

SPARKLE_API_URL = "https://api.groq.com/openai/v1/chat/completions"
SPARKLE_MODEL = "openai/gpt-oss-120b"
SPARKLE_USER_AGENT = "Sparkle/1.0"
SPARKLE_PERSONALITY = (
    "Tu es Sparkle, un petit compagnon de bureau sympathique. Réponds en français, brièvement et clairement. Tutois l'utilisateur. Fais énormément de blagues et de jeux de mots. L'utilisateur n'est PAS Sparkle, c'est ton prénom, ne l'indique pas au début de chaque réponse. Tes réponses doivent être les plus courtes possibles, efficaces, et rigoureuses."
)


def get_sparkle_font() -> QFont:
    font_path = (
        Path.home()
        / "AppData"
        / "Local"
        / "Microsoft"
        / "Windows"
        / "Fonts"
        / "minecraft_font.ttf"
    )
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id == -1:
        raise RuntimeError(f"Impossible de charger la police Minecraft : {font_path}")

    family = QFontDatabase.applicationFontFamilies(font_id)[0]
    return QFont(family, 8)


class ChatbotService(QObject):
    response_ready = Signal(str)
    answer_received = Signal()

    def __init__(self, conversation_header: str | None = None):
        super().__init__()
        self.endpoint = SPARKLE_API_URL
        self.model = os.getenv("SPARKLE_MODEL", "").strip() or SPARKLE_MODEL
        self.api_key = os.getenv("SPARKLE_API_KEY", "").strip()
        self.conversation_header = conversation_header or SPARKLE_PERSONALITY

    def ask(self, message: str):
        message = message.strip()
        if message:
            threading.Thread(
                target=self._request,
                args=(message,),
                daemon=True,
            ).start()

    def _request(self, message: str):
        if not self.api_key:
            self.response_ready.emit(
                "Ajoute ta clé Groq dans le fichier .env : "
                "SPARKLE_API_KEY=ta_cle_groq."
            )
            return

        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.conversation_header},
                {"role": "user", "content": message},
            ],
        }).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                # Cloudflare rejects the default Python-urllib signature.
                "User-Agent": SPARKLE_USER_AGENT,
            },
            method="POST",
        )
        has_answer = False
        try:
            with urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Le contenu de la réponse n'est pas du texte.")
            answer = content.strip()
            has_answer = bool(answer)
            if not answer:
                answer = "Je n'ai pas réussi à formuler une réponse."
        except HTTPError as error:
            with error:
                answer = self._http_error_answer(error)
        except TimeoutError:
            answer = (
                "Groq met trop longtemps à répondre ; réessaie dans quelques "
                "secondes."
            )
        except (OSError, URLError) as error:
            answer = (
                "Le service Groq est inaccessible. "
                f"Détail : {error}"
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            answer = f"La réponse de Groq est illisible. Détail : {error}"
        self.response_ready.emit(answer.replace(self.api_key, "[clé masquée]"))
        if has_answer:
            self.answer_received.emit()

    def _http_error_answer(self, error: HTTPError) -> str:
        body = error.read(8192).decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        details = data.get("error", {})
        if not isinstance(details, dict):
            details = {}
        message = details.get("message") or data.get("detail") or ""
        code = details.get("code") or data.get("error_code")

        if error.code == 401:
            answer = "La clé Groq est invalide (401). Vérifie SPARKLE_API_KEY dans .env."
        elif error.code == 403:
            if str(code) == "1010" or "1010" in body:
                answer = (
                    "Cloudflare bloque l'identification réseau de Sparkle (403/1010). "
                    "Ce refus ne signifie pas que ta clé Groq est invalide."
                )
            elif code == "model_permission_blocked_org":
                answer = (
                    f"Le modèle « {self.model} » est bloqué par ton organisation Groq. "
                    "Active-le dans https://console.groq.com/settings/limits."
                )
            elif code == "model_permission_blocked_project":
                answer = (
                    f"Le modèle « {self.model} » est bloqué par ton projet Groq. "
                    "Active-le dans https://console.groq.com/settings/project/limits."
                )
            else:
                answer = "Groq refuse l'accès (403). Vérifie les autorisations de ton compte."
        elif error.code == 429:
            answer = (
                "La limite gratuite Groq est momentanément atteinte. "
                "Réessaie dans quelques instants."
            )
        elif error.code == 404:
            answer = f"Le modèle Groq « {self.model} » est introuvable."
        else:
            answer = f"Groq a renvoyé HTTP {error.code}."

        if isinstance(message, str) and message:
            answer += f"\nDétail : {message[:600]}"
        return answer


class ChatBubble(QWidget):
    submitted = Signal(str)

    def __init__(self, parent=None, *, asset_folder="chatbox", editable=True,
                 sprite_prefix="chatbox"):
        super().__init__(parent)
        self.asset_folder = asset_folder
        self.sprite_prefix = sprite_prefix
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(192, 192)
        self.sparkle_font = get_sparkle_font()

        self.answer_label = QTextBrowser(self)
        self.answer_label.setFont(self.sparkle_font)
        self.answer_label.setPlainText("Écris-moi quelque chose...")
        self.answer_label.setStyleSheet(
            "color: #202020; background: transparent; border: none;"
            " padding: 0;"
        )
        self.answer_label.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.answer_label.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.input = QLineEdit(self)
        self.input.setFont(self.sparkle_font)
        self.input.setPlaceholderText("Parler à Sparkle...")
        self.input.setStyleSheet(
            "color: #202020; background: rgba(255,255,255,170);"
            " border: none; padding: 2px 4px;"
        )
        self.input.returnPressed.connect(self._submit)
        self.answer_label.setGeometry(22, 24, 148, 70)
        self.input.setGeometry(20, 98, 148, 22)
        if not editable:
            self.input.hide()
            self.answer_label.setGeometry(22, 24, 148, 124)

    def paintEvent(self, event):
        side = getattr(self, "side", "right")
        pixmap = QPixmap(str(get_asset(f"{self.asset_folder}/{self.sprite_prefix}_{side}.png")))
        painter = QPainter(self)
        painter.drawPixmap(0, 0, pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        ))
        painter.end()
        super().paintEvent(event)

    def _submit(self):
        message = self.input.text().strip()
        if message:
            self.input.clear()
            self.answer_label.setPlainText("Sparkle réfléchit...")
            self.submitted.emit(message)

    def show_for(self, sparkle):
        self.position_for(sparkle)
        self.show()
        self.raise_()
        if not self.input.isHidden():
            self.input.setFocus()

    def position_for(self, sparkle):
        screen = QGuiApplication.screenAt(sparkle.pos())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry()
        right_position = sparkle.mapToGlobal(
            QPoint(sparkle.width(), -self.height() - 8)
        )
        left_position = sparkle.mapToGlobal(
            QPoint(-self.width(), -self.height() - 8)
        )
        if right_position.x() + self.width() <= available.right() + 1:
            side = "right"
            position = right_position
        else:
            side = "left"
            position = left_position
        if getattr(self, "side", None) != side:
            self.side = side
            self.update()
        position.setX(max(available.left(), min(position.x(), available.right() - self.width() + 1)))
        position.setY(max(available.top(), min(position.y(), available.bottom() - self.height() + 1)))
        self.move(position)
