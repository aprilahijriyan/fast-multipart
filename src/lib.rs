use memchr::memmem;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use std::collections::HashMap;

#[pyclass]
#[derive(Debug, Clone)]
pub struct FieldPart {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub filename: Option<String>,
    #[pyo3(get)]
    pub content_type: Option<String>,
    #[pyo3(get)]
    pub headers: HashMap<String, String>,
}

#[derive(Debug, Clone, Copy, PartialEq)]
enum ParserState {
    Preamble,
    Header,
    Body,
    Done,
}

const CRLF: &[u8] = b"\r\n";
const BODY_SEPARATOR: &[u8] = b"\r\n\r\n";
const MULTIPART_PREFIX: &[u8] = b"--";

fn find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    memmem::find(haystack, needle)
}

fn parse_headers(data: &[u8]) -> PyResult<FieldPart> {
    let mut headers = HashMap::new();
    let header_str = match std::str::from_utf8(data) {
        Ok(s) => s,
        Err(e) => {
            return Err(PyValueError::new_err(format!(
                "Invalid UTF-8 in headers: {}",
                e
            )))
        }
    };

    for line in header_str.lines() {
        if let Some((key, value)) = line.split_once(':') {
            headers.insert(key.trim().to_lowercase(), value.trim().to_string());
        }
    }

    let disposition = match headers.get("content-disposition") {
        Some(d) => d,
        None => return Err(PyValueError::new_err("Missing Content-Disposition header")),
    };

    let mut name = None;
    let mut filename = None;
    let mut is_form_data = None;

    for part in disposition.split(';') {
        let part = part.trim();
        if part == "form-data" {
            is_form_data = Some(true);
        } else if let Some(val) = part.strip_prefix("name=\"") {
            name = Some(val.trim_end_matches('\"').to_string());
        } else if let Some(val) = part.strip_prefix("filename=\"") {
            filename = Some(val.trim_end_matches('\"').to_string());
        }
    }
    if is_form_data.is_none() {
        return Err(PyValueError::new_err("Invalid multipart form-data"));
    }

    let name = match name {
        Some(n) => {
            let field_name = n.trim();
            if field_name.len() < 1 {
                return Err(PyValueError::new_err("Missing name in Content-Disposition"));
            }
            field_name.to_string()
        }
        None => return Err(PyValueError::new_err("Missing name in Content-Disposition")),
    };

    Ok(FieldPart {
        name,
        filename,
        content_type: headers.get("content-type").cloned(),
        headers,
    })
}

#[pyclass]
pub struct MultipartParser {
    full_boundary: Vec<u8>,
    part_boundary: Vec<u8>,
    final_boundary: Vec<u8>,
    buffer: Vec<u8>,
    cursor: usize,
    state: ParserState,
    on_field: PyObject,
    on_field_data: PyObject,
    on_field_end: PyObject,
}

#[pymethods]
impl MultipartParser {
    #[new]
    #[pyo3(signature = (boundary, on_field, on_field_data, on_field_end, *, buffer_cap = None))]
    fn new(
        boundary: &str,
        on_field: &Bound<'_, PyAny>,
        on_field_data: &Bound<'_, PyAny>,
        on_field_end: &Bound<'_, PyAny>,
        buffer_cap: Option<usize>,
    ) -> Self {
        let full_boundary = [MULTIPART_PREFIX, boundary.as_bytes()].concat();
        let part_boundary = [CRLF, &full_boundary].concat();
        let final_boundary = [part_boundary.as_slice(), MULTIPART_PREFIX].concat();

        Self {
            full_boundary,
            part_boundary,
            final_boundary,
            buffer: Vec::with_capacity(buffer_cap.unwrap_or(8912)),
            cursor: 0,
            state: ParserState::Preamble,
            on_field: on_field.clone().into(),
            on_field_data: on_field_data.clone().into(),
            on_field_end: on_field_end.clone().into(),
        }
    }

    pub fn feed(&mut self, py: Python, data: &[u8]) -> PyResult<()> {
        if self.state == ParserState::Done {
            return Err(PyRuntimeError::new_err(
                "Cannot receive new data, parser is already closed.",
            ));
        }

        self.buffer.extend_from_slice(data);

        loop {
            let initial_cursor = self.cursor;

            match self.state {
                ParserState::Preamble => {
                    if let Some(pos) = find(&self.buffer[self.cursor..], &self.full_boundary) {
                        self.cursor += pos + self.full_boundary.len();
                        self.state = ParserState::Header;
                    } else {
                        break;
                    }
                }
                ParserState::Header => {
                    let unprocessed = &self.buffer[self.cursor..];
                    let mut start = 0;
                    if unprocessed.starts_with(CRLF) {
                        start += CRLF.len();
                    }

                    if let Some(pos) = find(&unprocessed[start..], BODY_SEPARATOR) {
                        let header_data = &unprocessed[start..start + pos];
                        let part = parse_headers(header_data)?;
                        self.on_field.call1(py, (part,))?;

                        self.cursor += start + pos + BODY_SEPARATOR.len();
                        self.state = ParserState::Body;
                    } else {
                        break;
                    }
                }
                ParserState::Body => {
                    let unprocessed = &self.buffer[self.cursor..];
                    // Search for the next occurrence of a boundary start.
                    if let Some(pos) = find(unprocessed, &self.part_boundary) {
                        // A boundary was found. Check if it's the final one.
                        if unprocessed[pos..].starts_with(&self.final_boundary) {
                            // It's the FINAL boundary.
                            if pos > 0 {
                                let data_slice = &unprocessed[..pos];
                                self.on_field_data
                                    .call1(py, (PyBytes::new(py, data_slice),))?;
                            }
                            self.on_field_end.call0(py)?;
                            self.cursor += pos + self.final_boundary.len();
                            self.state = ParserState::Done;
                        } else {
                            // It's a regular PART boundary.
                            if pos > 0 {
                                let data_slice = &unprocessed[..pos];
                                self.on_field_data
                                    .call1(py, (PyBytes::new(py, data_slice),))?;
                            }
                            self.on_field_end.call0(py)?;
                            self.cursor += pos + self.part_boundary.len();
                            self.state = ParserState::Header;
                        }
                    } else {
                        // No full boundary found in the current buffer.
                        // Process a chunk of data, leaving a margin for a partial boundary.
                        let reserve_len = self.part_boundary.len() - 1;
                        let chunk_len = if unprocessed.len() > reserve_len {
                            unprocessed.len() - reserve_len
                        } else {
                            0
                        };

                        if chunk_len > 0 {
                            let data_slice = &unprocessed[..chunk_len];
                            self.on_field_data
                                .call1(py, (PyBytes::new(py, data_slice),))?;
                            self.cursor += chunk_len;
                        }
                        // We need more data to find a boundary, so we break the loop.
                        break;
                    }
                }
                ParserState::Done => break,
            }

            if self.cursor == initial_cursor {
                break;
            }
        }

        if self.cursor > 0 {
            self.buffer.drain(..self.cursor);
            self.cursor = 0;
        }

        Ok(())
    }

    pub fn close(&mut self) -> PyResult<()> {
        self.state = ParserState::Done;
        self.buffer.clear();
        self.cursor = 0;
        Ok(())
    }
}

#[pymodule]
fn fast_multipart(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<MultipartParser>()?;
    m.add_class::<FieldPart>()?;
    Ok(())
}
