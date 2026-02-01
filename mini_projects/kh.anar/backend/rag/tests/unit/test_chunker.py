from rag.chunking.chunker import DeterministicChunker


def test_chunker_basic():
    text = """This is a test document. " * 200
    c = DeterministicChunker(chunk_size=100, chunk_overlap=10)
    chunks = c.chunk("doc1", text)
    # determinisztikus: ezekkel a paraméterekkel >1 darabra számítunk
    assert len(chunks) > 1
    # a daraboknak összefüggőknek és az overlap mértékével átfedőknek kell lenniük
    assert chunks[0].metadata["start"] == 0
    assert chunks[1].metadata["start"] == 100 - 10
    # az azonosítók determinisztikusak
    assert chunks[0].chunk_id == "doc1:0"
    assert chunks[1].chunk_id == "doc1:1"
