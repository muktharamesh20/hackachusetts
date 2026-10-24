"""The text format stored inside a PantrySort food QR code.

A QR code only carries a short string, so the format is compact (smaller
payload -> lower-density QR -> more reliable decoding from a simulated camera).
The label is self-contained: besides the sku it can carry the facts the robot
needs to sort and account for the item, so a scan works even for products the
local catalog doesn't know.

Format (version 1)::

    PS1|sku=BEANS-BLK-CAN|exp=2027-04-12|lot=A1|cat=canned|cal=330|alg=none

* ``PS1``  - magic/version prefix, so the robot ignores QR codes that aren't ours.
* ``sku``  - required; key into the food catalog.
* ``exp``  - optional ISO date; expiry is per physical unit, so it lives on the label.
* ``lot``  - optional donation/lot identifier.
* ``cat``  - optional FoodCategory value (e.g. ``dry_goods``).
* ``cal``  - optional kcal per unit (non-negative integer).
* ``alg``  - optional allergens, ``.``-separated (``milk.wheat``); ``none`` = no allergens.

Unknown ``key=value`` fields are preserved in ``extra`` for forward compatibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

PAYLOAD_PREFIX = "PS1"
_FIELD_SEP = "|"
_KV_SEP = "="
# Restrict values to a conservative charset so they can never break the format.
_VALUE_RE = re.compile(r"^[A-Za-z0-9._\-]+$")
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_RESERVED = frozenset({"sku", "exp", "lot", "cat", "cal", "alg"})
_ALLERGEN_SEP = "."
_NO_ALLERGENS = "none"


class PayloadError(ValueError):
    """Raised when a QR string is not a valid PantrySort payload."""


@dataclass(frozen=True)
class FoodQrPayload:
    sku: str
    expiration_date: date | None = None
    lot: str | None = None
    category: str | None = None              # FoodCategory value
    unit_calories: int | None = None         # kcal per unit
    allergens: tuple[str, ...] | None = None  # None = not on the label, () = none
    extra: dict[str, str] = field(default_factory=dict)

    def encode(self) -> str:
        """Serialize to the QR text, validating every field."""
        fields: dict[str, str] = {"sku": self.sku}
        if self.expiration_date is not None:
            fields["exp"] = self.expiration_date.isoformat()
        if self.lot is not None:
            fields["lot"] = self.lot
        if self.category is not None:
            fields["cat"] = self.category
        if self.unit_calories is not None:
            if self.unit_calories < 0:
                raise PayloadError("cal must be non-negative")
            fields["cal"] = str(int(self.unit_calories))
        if self.allergens is not None:
            for a in self.allergens:
                if not a or _ALLERGEN_SEP in a or a == _NO_ALLERGENS:
                    raise PayloadError(f"invalid allergen {a!r}")
            fields["alg"] = _ALLERGEN_SEP.join(self.allergens) or _NO_ALLERGENS
        for key, value in self.extra.items():
            if key in fields or key in _RESERVED:
                raise PayloadError(f"extra field {key!r} collides with a reserved field")
            fields[key] = value

        parts = [PAYLOAD_PREFIX]
        for key, value in fields.items():
            _validate_key(key)
            _validate_value(key, value)
            parts.append(f"{key}{_KV_SEP}{value}")
        return _FIELD_SEP.join(parts)

    @classmethod
    def parse(cls, text: str) -> FoodQrPayload:
        """Parse QR text. Raises ``PayloadError`` if it isn't a valid PS1 payload."""
        if not isinstance(text, str) or not text:
            raise PayloadError("empty QR payload")

        parts = text.strip().split(_FIELD_SEP)
        if parts[0] != PAYLOAD_PREFIX:
            raise PayloadError(f"not a PantrySort payload (prefix {parts[0]!r})")

        fields: dict[str, str] = {}
        for part in parts[1:]:
            key, sep, value = part.partition(_KV_SEP)
            if not sep:
                raise PayloadError(f"malformed field {part!r}")
            _validate_key(key)
            _validate_value(key, value)
            if key in fields:
                raise PayloadError(f"duplicate field {key!r}")
            fields[key] = value

        sku = fields.pop("sku", None)
        if not sku:
            raise PayloadError("payload is missing required field 'sku'")

        exp: date | None = None
        if "exp" in fields:
            raw = fields.pop("exp")
            try:
                exp = date.fromisoformat(raw)
            except ValueError as exc:
                raise PayloadError(f"invalid exp date {raw!r}") from exc

        lot = fields.pop("lot", None)
        category = fields.pop("cat", None)

        cal: int | None = None
        if "cal" in fields:
            raw = fields.pop("cal")
            if not raw.isdigit():
                raise PayloadError(f"invalid cal {raw!r} (expected a non-negative integer)")
            cal = int(raw)

        allergens: tuple[str, ...] | None = None
        if "alg" in fields:
            raw = fields.pop("alg")
            parts = () if raw == _NO_ALLERGENS else tuple(raw.split(_ALLERGEN_SEP))
            if any(not a for a in parts):
                raise PayloadError(f"invalid alg {raw!r}")
            allergens = parts

        return cls(sku=sku, expiration_date=exp, lot=lot, category=category,
                   unit_calories=cal, allergens=allergens, extra=fields)


def _validate_key(key: str) -> None:
    if not _KEY_RE.match(key):
        raise PayloadError(f"invalid field name {key!r}")


def _validate_value(key: str, value: str) -> None:
    if not _VALUE_RE.match(value):
        raise PayloadError(
            f"invalid value for {key!r}: {value!r} (allowed: letters, digits, '.', '_', '-')"
        )
