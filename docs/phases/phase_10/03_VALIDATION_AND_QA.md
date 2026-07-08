# Phase 10 Validation and Quality Assurance

The generator performs the following checks:

1. Required Phase 02--09 summaries and report figures exist.
2. The generated DOCX is a valid OOXML ZIP package.
3. The DOCX contains `word/document.xml` and at least one embedded image.
4. The report has non-empty paragraphs and includes the AquaSkim project title.
5. The report build manifest stores SHA-256 hashes for every input summary and embedded PNG.
6. The submission manifest stores a checksum and file size for every packaged file.

For final visual review, open the DOCX in Microsoft Word. In the development environment, the report is rendered to PNG pages with LibreOffice before the patch is released.
