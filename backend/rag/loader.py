from pathlib import Path


def load_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if suffix == ".docx":
        from docx import Document
        return "\n".join(paragraph.text for paragraph in Document(path).paragraphs)
    raise ValueError(f"不支持的知识文档格式: {suffix}")


def load_directory(directory: Path) -> list[tuple[str, str]]:
    if not directory.exists():
        return []
    documents = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".pdf", ".docx"}:
            documents.append((path.name, load_document(path)))
    return documents
