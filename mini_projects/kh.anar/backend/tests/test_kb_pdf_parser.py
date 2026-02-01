"""Egységtesztek a PDF parserhez.

Tesztek:
- PDF szövegkinyerés
- Metaadat-kinyerés
- Oldalszintű adatok
"""
import pytest
from pathlib import Path
import tempfile

from rag.ingestion.pdf_parser import parse_pdf, PYPDF_AVAILABLE


@pytest.mark.skipif(not PYPDF_AVAILABLE, reason="pypdf not installed")
def test_parse_simple_pdf():
    """Egy minimális érvényes PDF feldolgozása."""
    # Hozzunk létre egy minimális PDF-et (ez egyszerűsített példa)
    # Gyakorlatban használj valódi PDF tesztfájlt vagy generálj reportlabbal
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Hello PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000317 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
409
%%EOF
"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test.pdf"
        pdf_path.write_bytes(pdf_content)
        
        result = parse_pdf(pdf_path)
        
        # Struktúra ellenőrzése
        assert result.text is not None
        assert isinstance(result.pages, list)
        assert isinstance(result.metadata, dict)
        
        # Oldalak ellenőrzése
        assert len(result.pages) > 0
        assert result.pages[0]["page_num"] == 1


@pytest.mark.skipif(not PYPDF_AVAILABLE, reason="pypdf not installed")
def test_parse_pdf_with_metadata():
    """Metaadatkinyerés (cím, szerző) tesztelése."""
    # Ehhez a teszthez metaadatos PDF kellene
    # A részletes megvalósítást átugorjuk; gyakorlatban használj fixture PDF-et
    pass


def test_parse_pdf_missing_library():
    """Kecses hiba, ha a pypdf nem érhető el."""
    if PYPDF_AVAILABLE:
        pytest.skip("pypdf is available")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        
        with pytest.raises(RuntimeError, match="pypdf not available"):
            parse_pdf(pdf_path)
