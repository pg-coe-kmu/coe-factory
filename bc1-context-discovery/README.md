# BC1 – Interactive Context Discovery

**Team:** Simeon, Richard (Tech: Zakaria)
**Phase:** 1 – Analyse

## Zweck
KI-gestützter Chatbot-Agent als zentrales Interface, um unstrukturierte Informationen (Gespräche, Dokumente, Schaubilder) in ein strukturiertes Prozess- und Unternehmensmodell zu übersetzen.

## Messages
- **Consumed:** Sprachnachrichten (Voice-to-Text), Chat-Interaktion, Dokumente (PDF, Word, Excel), Bilder/Fotos
- **Produced:** Strukturiertes Unternehmens- & Prozessprofil, Confidence Report, Detaillierte Prozessdokumentation

## Arbeitspakete
- **AP 1.1** Chat-Interface & Multimodaler Ingest (Streamlit/React, Whisper, GPT-4o Vision)
- **AP 1.2** PII-Filter & Data Privacy (GDPR-Gate)
- **AP 1.3** Prozess-Extraktion & JSON-Compiler + Completeness-Check
- **AP 1.4** Dokumentations-Generator (Markdown/PDF)

## Schnittstellen
- **Output an BC2:** Strukturiertes Prozessprofil (siehe `/contracts/bc1-to-bc2/`)
