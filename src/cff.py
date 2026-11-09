import json
import os
import threading
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QLabel, QLineEdit

from src.chatbot import ChatBubble


CONNECTIONS_URL = "https://transport.opendata.ch/v1/connections"
LOCATIONS_URL = "https://transport.opendata.ch/v1/locations"
STATION_NOT_FOUND = "Sparkle n'a pas trouvé cette station !"


class StationNotFoundError(ValueError):
    pass


def request_json(endpoint, params):
    request = Request(
        f"{endpoint}?{urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": "Sparkle/1.0"},
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def normalize_station(name):
    name = unicodedata.normalize("NFKD", name.casefold())
    return " ".join("".join(char for char in name if not unicodedata.combining(char)).split())


@lru_cache(maxsize=128)
def resolve_station(name):
    data = request_json(LOCATIONS_URL, {"query": name, "type": "station"})
    if not isinstance(data, dict) or not isinstance(data.get("stations"), list):
        raise ValueError("Liste des gares absente de la réponse.")
    normalized = normalize_station(name)
    for station in data["stations"]:
        if not isinstance(station, dict) or not station.get("id"):
            continue
        if (str(station["id"]) == name
                or normalize_station(station.get("name") or "") == normalized):
            return str(station["id"])
    # Do not silently replace a misspelled station with an unrelated suggestion.
    raise StationNotFoundError(STATION_NOT_FOUND)


def parse_time(value):
    if not value:
        return None
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("L'horaire reçu ne précise pas le fuseau horaire.")
    return result


@dataclass(frozen=True)
class TrainDeparture:
    origin: str
    destination: str
    line: str
    departure: datetime
    expected_departure: datetime
    arrival: datetime | None
    platform: str | None
    transfers: int

    def display_text(self, *, include_route=True):
        now = datetime.now(self.departure.tzinfo)
        time_format = "%H:%M" if self.departure.date() == now.date() else "%d/%m %H:%M"
        arrival_time = self.arrival.strftime("%H:%M") if self.arrival else "--:--"
        platform = f"Voie {self.platform}" if self.platform else "Voie non annoncée"
        lines = [
            f"{self.departure.strftime(time_format)} - {arrival_time}",
            f"{self.line} - {platform}",
        ]
        if include_route:
            lines.insert(0, f"{self.origin} > {self.destination}")
        delay = round((self.expected_departure - self.departure).total_seconds() / 60)
        if delay > 0:
            lines.append(f"Retard +{delay} min")
        if self.transfers:
            suffix = "s" if self.transfers > 1 else ""
            lines.append(f"{self.transfers} changement{suffix}")
        return "\n".join(lines)


def select_next_train(data, now=None):
    """Choose one upcoming train by actual departure, not API result order."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(data, dict) or not isinstance(data.get("connections"), list):
        raise ValueError("Liste des correspondances absente de la réponse.")
    trains = []
    for connection in data["connections"]:
        if not isinstance(connection, dict) or connection.get("cancelled"):
            continue
        sections = connection.get("sections") or []
        section = next((item for item in sections if item.get("journey")), None)
        if section is None:
            continue
        journey = section["journey"]
        if str(journey.get("category", "")).upper() in {"BUS", "B", "TRAM", "T", "SHIP"}:
            continue
        stop = section.get("departure") or connection.get("from") or {}
        if stop.get("cancelled"):
            continue
        prognosis = stop.get("prognosis") or {}
        departure = parse_time(stop.get("departure"))
        if departure is None:
            continue
        expected = parse_time(prognosis.get("departure"))
        if expected is None:
            expected = departure + timedelta(minutes=float(stop.get("delay") or 0))
        if expected < now:
            continue
        destination = connection.get("to") or {}
        arrival_prognosis = destination.get("prognosis") or {}
        category = str(journey.get("category") or "Train")
        number = str(journey.get("number") or "")
        line = number if number.startswith(category) else category + number
        trains.append(TrainDeparture(
            origin=(stop.get("station") or {}).get("name") or "Départ",
            destination=(destination.get("station") or {}).get("name") or "Destination",
            line=line,
            departure=departure,
            expected_departure=expected,
            arrival=parse_time(arrival_prognosis.get("arrival") or destination.get("arrival")),
            platform=prognosis.get("platform") or stop.get("platform"),
            transfers=int(connection.get("transfers") or 0),
        ))
    return min(trains, key=lambda train: train.expected_departure, default=None)


def fetch_next_train(origin: str, destination: str):
    data = request_json(CONNECTIONS_URL, {
        "from": resolve_station(origin),
        "to": resolve_station(destination),
        "transportations[]": "train",
        "limit": 16,
    })
    return select_next_train(data)


class CffService(QObject):
    response_ready = Signal(str)
    itinerary_received = Signal()
    _request_finished = Signal(int, str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._request_id = 0
        self._pending = None
        self._request_finished.connect(self._finish_request)

    @Slot(str, str)
    def refresh(self, origin, destination):
        self.cancel()
        origin, destination = origin.strip(), destination.strip()
        if not origin or not destination:
            self.response_ready.emit("Saisis les deux gares.")
            return
        request = (self._request_id, origin, destination)
        if self._busy:
            self._pending = request
        else:
            self._start_request(request)

    @Slot()
    def cancel(self):
        self._request_id += 1
        self._pending = None

    def _start_request(self, request):
        self._busy = True
        threading.Thread(target=self._request, args=request, daemon=True).start()

    def _request(self, request_id, origin, destination):
        has_itinerary = False
        try:
            train = fetch_next_train(origin, destination)
            answer = train.display_text(include_route=False) if train else "Aucun prochain train trouvé pour ce trajet."
            has_itinerary = train is not None
        except StationNotFoundError:
            answer = STATION_NOT_FOUND
        except HTTPError as error:
            with error:
                if error.code == 429:
                    answer = "Trop de demandes d'horaires. Réessaie dans quelques instants."
                elif error.code in (400, 404):
                    answer = "Trajet introuvable. Vérifie les deux noms de gare."
                else:
                    answer = f"Les horaires sont indisponibles (HTTP {error.code})."
        except TimeoutError:
            answer = "Les horaires mettent trop longtemps à arriver. Réessaie."
        except (OSError, URLError):
            answer = "Impossible de joindre le service des horaires. Vérifie ta connexion."
        except (ValueError, TypeError, KeyError, AttributeError):
            answer = "Impossible de lire les horaires reçus. Réessaie dans quelques instants."
        self._request_finished.emit(request_id, answer, has_itinerary)

    @Slot(int, str, bool)
    def _finish_request(self, request_id, answer, has_itinerary=False):
        self._busy = False
        if request_id == self._request_id:
            self.response_ready.emit(answer)
            if has_itinerary:
                self.itinerary_received.emit()
        pending = self._pending
        self._pending = None
        if pending is not None:
            self._start_request(pending)


class CffBubble(ChatBubble):
    search_requested = Signal(str, str)
    search_invalidated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, asset_folder="cff", editable=False,
                         sprite_prefix="chatbox_train")
        self.origin_input = QLineEdit(self)
        self.destination_input = QLineEdit(self)
        self.station_separator = QLabel(">", self)
        self.station_separator.setFont(self.sparkle_font)
        self.station_separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.station_separator.setStyleSheet("color: #202020; background: transparent;")
        self.origin_input.setGeometry(18, 12, 72, 20)
        self.station_separator.setGeometry(90, 12, 12, 20)
        self.destination_input.setGeometry(102, 12, 72, 20)
        for field, placeholder, accessible_name in (
            (self.origin_input, "Départ", "Gare de départ"),
            (self.destination_input, "Arrivée", "Gare d'arrivée"),
        ):
            field.setFont(self.sparkle_font)
            field.setPlaceholderText(placeholder)
            field.setAccessibleName(accessible_name)
            field.setStyleSheet(
                "color: #202020; background: rgba(255,255,255,200);"
                " border: 1px solid #999; padding: 1px 2px;"
            )
        self.setTabOrder(self.origin_input, self.destination_input)
        # Existing .env stations only prefill the editable fields.
        self.origin_input.setText(os.getenv("NEAREST_STATION", "").strip())
        self.destination_input.setText(os.getenv("FINAL_STATION", "").strip())
        self.answer_label.setGeometry(22, 38, 148, 62)
        self.answer_label.setPlainText("Saisis les deux gares.")
        self.setToolTip("Horaires : opentransportdata.swiss, via transport.opendata.ch")
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(700)
        self.search_timer.timeout.connect(self._search)
        for field in (self.origin_input, self.destination_input):
            field.textChanged.connect(self._stations_changed)
            field.returnPressed.connect(self._search)

    def _stations_changed(self):
        self.search_timer.stop()
        self.search_invalidated.emit()
        self.origin_input.setToolTip(self.origin_input.text())
        self.destination_input.setToolTip(self.destination_input.text())
        self.answer_label.setPlainText("Saisis les deux gares.")
        if (self.isVisible() and self.origin_input.text().strip()
                and self.destination_input.text().strip()):
            self.answer_label.clear()
            self.search_timer.start()

    def _search(self):
        self.search_timer.stop()
        origin = self.origin_input.text().strip()
        destination = self.destination_input.text().strip()
        if not self.isVisible() or not origin or not destination:
            return
        self.answer_label.setPlainText("Recherche du prochain train...")
        self.search_requested.emit(origin, destination)

    def show_for(self, sparkle):
        super().show_for(sparkle)
        if not self.origin_input.text().strip():
            self.origin_input.setFocus()
        else:
            self.destination_input.setFocus()
        self._search()

    def hideEvent(self, event):
        self.search_timer.stop()
        self.search_invalidated.emit()
        super().hideEvent(event)
