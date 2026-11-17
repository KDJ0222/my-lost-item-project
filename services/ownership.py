from hashlib import sha256
from hmac import compare_digest
from typing import Annotated

from fastapi import Header, HTTPException

from models import Item
from schemas import ItemRead


OwnerToken = Annotated[str | None, Header(alias="X-Owner-Token", min_length=32, max_length=128)]


def token_hash(token: str | None) -> str | None:
    return sha256(token.encode()).hexdigest() if token else None


def owns_item(item: Item, token: str | None) -> bool:
    return bool(item.owner_token_hash and token and compare_digest(item.owner_token_hash, token_hash(token)))


def require_owner(item: Item, token: str | None):
    if not owns_item(item, token):
        raise HTTPException(403, "이 브라우저에서 등록한 물품만 변경하거나 삭제할 수 있습니다.")


def item_response(item: Item, token: str | None) -> ItemRead:
    return ItemRead.model_validate(item).model_copy(update={"is_mine": owns_item(item, token)})
