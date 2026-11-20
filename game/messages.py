"""Journal de messages (« Le gobelin vous attaque… ») et petits outils de texte."""

from __future__ import annotations

# On garde un historique limité : inutile de stocker 10 000 messages.
MAX_MESSAGES = 100

VOWELS = "aeiouyhéèêàâîïôû"


def elide(word: str, name: str) -> str:
    """Accole un petit mot (le, de…) à un nom, avec élision devant une voyelle.

    elide("le", "gobelin") → "le gobelin"
    elide("le", "orc")     → "l'orc"
    elide("de", "orc")     → "d'orc"
    (Simplification : tout « h » est traité comme muet.)
    """
    if name and name[0].lower() in VOWELS:
        return f"{word[:-1]}'{name}"
    return f"{word} {name}"


def capitalize(text: str) -> str:
    """Majuscule à la première lettre seulement (str.capitalize() baisserait le reste)."""
    return text[:1].upper() + text[1:]


class MessageLog:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def add(self, text: str) -> None:
        self.messages.append(text)
        # Quand on dépasse la limite, on oublie les plus anciens.
        if len(self.messages) > MAX_MESSAGES:
            del self.messages[0]

    def last(self, count: int) -> list[str]:
        """Les `count` derniers messages, du plus ancien au plus récent."""
        return self.messages[-count:]
