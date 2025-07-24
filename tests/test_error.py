import re
import pytest

from .helpers import create_parser

def test_invalid_utf8():
    boundary = "--utf8boundary"
    lines = [
        f"--{boundary}".encode(),
        b"Content-Disposition: form-data; name=\"field1_\xff\"",
        b"",
        b"value1",
        f"--{boundary}--".encode(),
        b""
    ]
    payload = b"\r\n".join(lines)
    _, feed = create_parser(boundary)
    with pytest.raises(ValueError, match=re.compile(r"invalid utf-8 sequence", re.I)):
        feed(payload)

def test_missing_content_disposition():
    boundary = "--utf8boundary"
    lines = [
        f"--{boundary}".encode(),
        # b"Content-Disposition: form-data; name=\"field1_\xff\"",
        b"",
        b"",
        b"value1",
        f"--{boundary}--".encode(),
        b""
    ]
    payload = b"\r\n".join(lines)
    _, feed = create_parser(boundary)
    with pytest.raises(ValueError, match="Missing Content-Disposition header"):
        feed(payload)

def test_invalid_form_data():
    boundary = "--utf8boundary"
    lines = [
        f"--{boundary}".encode(),
        b"Content-Disposition: name=\"field1\"",
        b"",
        b"value1",
        f"--{boundary}--".encode(),
        b""
    ]
    payload = b"\r\n".join(lines)
    _, feed = create_parser(boundary)
    with pytest.raises(ValueError, match="Invalid multipart form-data"):
        feed(payload)

def test_missing_field_name():
    boundary = "--utf8boundary"
    lines = [
        f"--{boundary}".encode(),
        b"Content-Disposition: form-data; name=\"\"",
        b"",
        b"value1",
        f"--{boundary}--".encode(),
        b""
    ]
    payload = b"\r\n".join(lines)
    _, feed = create_parser(boundary)
    with pytest.raises(ValueError, match="Missing name in Content-Disposition"):
        feed(payload)

    lines = [
        f"--{boundary}".encode(),
        b"Content-Disposition: form-data",
        b"",
        b"value1",
        f"--{boundary}--".encode(),
        b""
    ]
    payload = b"\r\n".join(lines)
    _, feed = create_parser(boundary)
    with pytest.raises(ValueError, match="Missing name in Content-Disposition"):
        feed(payload)

    lines = [
        f"--{boundary}".encode(),
        b"Content-Disposition: form-data; filename=\"test.txt\"",
        b"",
        b"value1",
        f"--{boundary}--".encode(),
        b""
    ]
    payload = b"\r\n".join(lines)
    _, feed = create_parser(boundary)
    with pytest.raises(ValueError, match="Missing name in Content-Disposition"):
        feed(payload)
