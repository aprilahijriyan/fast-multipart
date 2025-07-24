# test_parser.py
import mimetypes
from typing import Optional, TypedDict, cast

from fast_multipart import MultipartParser, FieldPart

import pytest

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


def make_multipart_body(boundary, fields) -> bytes:
    # fields: list of (name, filename, content_type, value)
    lines: list[str] = []
    for name, filename, content_type, value in fields:
        lines.append(f"--{boundary}")
        disp = f'form-data; name="{name}"'
        if filename:
            disp += f'; filename="{filename}"'
        lines.append(f"Content-Disposition: {disp}")
        if content_type:
            lines.append(f"Content-Type: {content_type}")
        elif not content_type and filename:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            lines.append(f"Content-Type: {content_type}")
        lines.append("")
        # Pastikan value bertipe str
        if isinstance(value, bytes):
            value = value.decode()
        lines.append(value)
    lines.append(f"--{boundary}--")
    lines.append("")
    return "\r\n".join(lines).encode()


def test_single_text_field():
    """
    Menguji parsing untuk satu field teks sederhana.
    """
    boundary = "--boundary"
    payload = make_multipart_body(
        boundary, [
            ("text_field", None, None, b"ini adalah nilainya"),
            ("blank_field", None, None, b""),
        ]
    )
    forms, feed = create_parser(boundary)
    feed(payload)
    assert forms
    text_field = forms["text_field"]
    part, data = text_field["part"], text_field["data"]
    assert part
    assert part.name == "text_field"
    assert part.content_type is None
    assert part.filename is None
    assert data == b"ini adalah nilainya"

    assert forms
    blank_field = forms["blank_field"]
    part, data = blank_field["part"], blank_field["data"]
    assert part
    assert data == b""
    with pytest.raises(RuntimeError, match="Cannot receive new data, parser is already closed."):
        feed(b"")

# --- Test Case Kompleks: Beberapa Field & Unggahan File ---


def test_multiple_fields_and_file_upload():
    """
    Menguji parsing untuk beberapa field, termasuk satu field file.
    """
    boundary = "--fileboundary"
    payload = make_multipart_body(
        boundary,
        [
            ("text1", None, None, b"PPPPPP."),
            ("file1", "test.text", "text/plain", b"Isi dari file teks."),
        ],
    )

    forms, feed = create_parser(boundary)
    feed(payload)
    assert forms
    text1 = forms["text1"]
    part, data = text1["part"], text1["data"]
    assert part
    assert part.name == "text1"
    assert part.content_type is None
    assert part.filename is None
    assert data == b"PPPPPP."

    file1 = forms["file1"]
    part, data = file1["part"], file1["data"]
    assert part
    assert part.name == "file1"
    assert part.content_type == "text/plain"
    assert part.filename == "test.text"
    assert data == b"Isi dari file teks."
    with pytest.raises(RuntimeError, match="Cannot receive new data, parser is already closed."):
        feed(b"")

# --- Test Case Data Terpotong (Chunked) ---


def test_chunked_feed():
    """
    Menguji bahwa parser dapat menangani data yang di-feed per byte.
    """
    boundary = "--chunkedboundary"
    payload = make_multipart_body(
        boundary, [("chunked_field", None, None, b"ini adalah nilainya")]
    )
    forms, feed = create_parser(boundary)
    feed(payload[:10])
    assert not forms
    feed(payload[10:])
    assert forms
    chunked_field = forms["chunked_field"]
    part, data = chunked_field["part"], chunked_field["data"]
    assert part
    assert part.name == "chunked_field"
    assert part.content_type is None
    assert part.filename is None
    assert data == b"ini adalah nilainya"
    with pytest.raises(RuntimeError, match="Cannot receive new data, parser is already closed."):
        feed(b"")

def test_crlf():
    boundary = "--crlfboundary"
    crlf_field_value = b"\r\n" * 997
    cr_field_value = b"\r" * 998
    lf_field_value = b"\n" * 999
    mix_field_value = crlf_field_value + crlf_field_value + lf_field_value
    payload = make_multipart_body(
        boundary,
        [
            ("crlf_field", "crlf.bin", None, crlf_field_value),
            ("cr_field", "cr.bin", None, cr_field_value),
            ("lf_field", "lf.bin", None, lf_field_value),
            ("mix_field", "mix.bin", None, mix_field_value),
        ],
    )
    forms, feed = create_parser(boundary)
    chunk_size = 37 
    
    for i in range(0, len(payload), chunk_size):
        chunk = payload[i:i + chunk_size]
        # Kirim setiap potongan data ke parser
        feed(chunk)

    assert forms
    crlf_field = forms["crlf_field"]
    part, data = crlf_field["part"], crlf_field["data"]
    assert part
    assert data == crlf_field_value
    
    cr_field = forms["cr_field"]
    part, data = cr_field["part"], cr_field["data"]
    assert part
    assert data == cr_field_value

    lf_field = forms["lf_field"]
    part, data = lf_field["part"], lf_field["data"]
    assert part
    assert data == lf_field_value

    mix_field = forms["mix_field"]
    part, data = mix_field["part"], mix_field["data"]
    assert part
    assert data == mix_field_value

    with pytest.raises(RuntimeError, match="Cannot receive new data, parser is already closed."):
        feed(b"")
