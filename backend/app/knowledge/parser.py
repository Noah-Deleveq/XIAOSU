"""文档解析：Markdown / TXT / PDF / Word → 纯文本"""
import io


def parse_text(name: str, content: bytes) -> str:
    """按扩展名解析文件内容为纯文本"""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext in ("md", "txt"):
        return content.decode("utf-8", errors="replace")
    if ext == "pdf":
        return _parse_pdf(content)
    if ext in ("docx", "doc"):
        return _parse_docx(content)
    raise ValueError(f"不支持的格式: {ext}")


def _parse_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    return "\n\n".join(parts)


def _parse_docx(content: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
