import mimetypes
from fast_multipart import MultipartParser, FieldPart
from typing import Optional, TypedDict, cast
def make_multipart_body(
    boundary,
    fields: list[tuple[str, Optional[str], Optional[str], bytes, Optional[dict]]],
) -> bytes:
    # fields: list of (name, filename, content_type, value)
    lines: list[str] = []
    for name, filename, content_type, value, hdrs in fields:
        lines.append(f"--{boundary}")
        disp = f'form-data; name="{name}"'
        if filename:
            disp += f'; filename="{filename}"'
        lines.append(f"Content-Disposition: {disp}")
        if content_type:
            lines.append(f"Content-Type: {content_type}")
        elif not content_type and filename:
            content_type = (
                mimetypes.guess_type(filename)[0] or "application/octet-stream"
            )
            lines.append(f"Content-Type: {content_type}")
        if hdrs:
            for k, v in hdrs.items():
                lines.append(f"{k}: {v}")
        lines.append("")
        # Pastikan value bertipe str
        if isinstance(value, bytes):
            value = value.decode()
        lines.append(value)
    lines.append(f"--{boundary}--")
    lines.append("")
    return "\r\n".join(lines).encode()

class FormPart(TypedDict):
    part: Optional[FieldPart]
    data: bytes


def create_parser(boundary: str):
    forms: dict[str, FormPart] = {}
    current_field: FormPart = {"part": None, "data": b""}

    def on_field(part: FieldPart):
        current_field["part"] = part

    def on_field_data(data: bytes):
        current_field["data"] += data

    def on_field_end():
        nonlocal current_field
        part = cast(FieldPart, current_field["part"])
        forms[part.name] = current_field.copy()
        current_field = {"part": None, "data": b""}

    parser = MultipartParser(
        boundary,
        on_field=on_field,
        on_field_data=on_field_data,
        on_field_end=on_field_end,
    )
    return forms, parser.feed
