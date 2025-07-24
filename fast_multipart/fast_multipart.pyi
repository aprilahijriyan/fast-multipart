from typing import Any, Callable, Optional

class FieldPart:
    name: str
    filename: Optional[str]
    content_type: Optional[str]
    headers: dict[str, str]

OnFieldHandler = Callable[[FieldPart], Any]
OnFieldDataHandler = Callable[[bytes], Any]
OnFieldEndHandler = Callable[[], Any]

class MultipartParser:
    def __init__(
        self,
        boundary: str,
        on_field: OnFieldHandler,
        on_field_data: OnFieldDataHandler,
        on_field_end: OnFieldEndHandler,
        *,
        buffer_cap: Optional[int] = 8912,
    ) -> None: ...
    def feed(
        self,
        data: bytes,
    ) -> None: ...
    def close(self) -> bool: ...
