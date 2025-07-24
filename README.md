# fast-multipart ⚡

> **Lightning-fast multipart parsing for Python** - An enhanced successor to `pymulter`

## 🚀 Performance

`fast-multipart` significantly outperforms the standard `multipart` library across all file sizes:

| File Size         | Library        | Avg Time | Avg Throughput | Performance Gain |
| ----------------- | -------------- | -------- | -------------- | ---------------- |
| **Small (413 B)** | fast-multipart | 0.0006s  | 623.1 KB/s     | **4.1x faster**  |
|                   | multipart      | 0.0026s  | 152.6 KB/s     |                  |
| **Medium (8 MB)** | fast-multipart | 0.0055s  | 1.4 GB/s       | **3.0x faster**  |
|                   | multipart      | 0.0165s  | 483.6 MB/s     |                  |
| **Large (80 MB)** | fast-multipart | 0.0433s  | 1.8 GB/s       | **2.4x faster**  |
|                   | multipart      | 0.1039s  | 770.2 MB/s     |                  |
| **XL (200 MB)**   | fast-multipart | 0.0956s  | 2.0 GB/s       | **2.6x faster**  |
|                   | multipart      | 0.2463s  | 812.0 MB/s     |                  |
| **2XL (1000 MB)** | fast-multipart | 0.4324s  | 2.3 GB/s       | **2.9x faster**  |
|                   | multipart      | 1.2743s  | 784.8 MB/s     |                  |

## ✨ Key Features

- **Up to 4.1x Faster**: Significant performance gains over pure Python parsers
- **Streaming Parser**: Process large files chunk-by-chunk
- **Callback-Based**: Handle fields and data as they arrive
- **Type-Safe**: Full type hints support for better development experience

## 📦 Installation

```bash
# Recommended: using uv
uv add fast-multipart

# Or with pip
pip install fast-multipart
```

## 🎯 Quick Start

```python
from fast_multipart import MultipartParser, FieldPart

def on_field(field: FieldPart) -> None:
    print(f"Field: {field.name}")
    if field.filename:
        print(f"Filename: {field.filename}")
    print(f"Content-Type: {field.content_type}")

def on_field_data(data: bytes) -> None:
    # Process chunk of field data
    print(f"Received {len(data)} bytes")

def on_field_end() -> None:
    print("Field completed")

# Create parser with boundary from Content-Type header
boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
parser = MultipartParser(
    boundary=boundary,
    on_field=on_field,
    on_field_data=on_field_data,
    on_field_end=on_field_end
)

# Feed data to parser
with open('multipart_data.bin', 'rb') as f:
    while chunk := f.read(8192):
        parser.feed(chunk)

parser.close()
```

For more info, feel free to check out the [tests](tests/test_parser.py) file.

## 🔧 API Reference

### `MultipartParser`

The core streaming parser for multipart data.

```python
MultipartParser(
    boundary: str,                              # Boundary string from Content-Type
    on_field: Callable[[FieldPart], Any],      # Called when new field starts
    on_field_data: Callable[[bytes], Any],     # Called for each data chunk
    on_field_end: Callable[[], Any],           # Called when field ends
    buffer_cap: Optional[int] = 8912           # Internal buffer size
)
```

### `FieldPart`

Contains metadata for each multipart field.

```python
class FieldPart:
    name: str                           # Field name
    filename: Optional[str]             # Original filename (if file upload)
    content_type: Optional[str]         # MIME type
    headers: dict[str, str]            # All field headers
```
