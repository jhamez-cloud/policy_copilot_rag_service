`report.doc` is a real Word 97–2003 OLE document generated from a short DOCX
with LibreOffice. It contains a heading and the sentence “Quarterly revenue
grew by 25 percent.” It exercises the LibreOffice fallback because antiword
0.37 rejects some short Word text streams. Production conversion only needs
antiword and/or LibreOffice; the test fixture needs no external download.

PDF, DOCX, PPTX and CSV fixtures are generated in memory by
`tests/test_document_formats.py`, using the same installed parser libraries.
When LibreOffice is available, the test also converts a generated PPTX into
legacy PPT to exercise the full upload conversion path.
