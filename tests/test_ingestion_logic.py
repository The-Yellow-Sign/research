from pathlib import Path

from src.domain.services.chunking import (
    build_header_path,
    build_vector_text,
    infer_service_from_path,
    parse_frontmatter,
    process_markdown_ast,
)


def test_parse_frontmatter_valid():
    text = "---\nservice: nginx\ntitle: Nginx Setup\n---\nActual content."
    frontmatter, content = parse_frontmatter(text)
    assert frontmatter == {"service": "nginx", "title": "Nginx Setup"}
    assert content == "Actual content."

def test_parse_frontmatter_none():
    text = "Just some content."
    frontmatter, content = parse_frontmatter(text)
    assert frontmatter == {}
    assert content == "Just some content."

def test_infer_service_from_path():
    # Test skipping folders like 'docs'
    path = Path("docs/nginx/install.md")
    service = infer_service_from_path(path)
    assert service == "nginx"

    # Test general fallback/root skip
    path = Path("general.md")
    service = infer_service_from_path(path)
    assert service is None

def test_build_header_path():
    meta = {"header_1": "Setup", "header_2": "Ubuntu", "source_file": "nginx.md"}
    path = build_header_path(meta)
    assert path == "Setup > Ubuntu"

    meta_no_headers = {"source_file": "nginx.md"}
    path = build_header_path(meta_no_headers)
    assert path == "File: nginx.md"

def test_process_markdown_ast_code_and_table():
    text = """# Section

Here is code:

```python
print("hello")
```

And a table:

| a | b |
|---|---|
| 1 | 2 |
"""
    new_text, blocks = process_markdown_ast(text)

    assert ">>>CODE_BLOCK_0_python<<<" in new_text
    assert ">>>TABLE_BLOCK_1<<<" in new_text
    assert len(blocks) == 2
    assert blocks[0].block_type == "code"
    assert blocks[0].content == 'print("hello")\n'
    assert blocks[1].block_type == "table"

def test_build_vector_text():
    service = "nginx"
    header = "Setup"
    text = "Run apt install."
    vector = build_vector_text(service, header, text)
    assert vector == "nginx > Setup : Run apt install."
