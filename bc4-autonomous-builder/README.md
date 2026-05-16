# BC4 – Autonomous Builder

**Team:** Zakaria, Ozan
**Phase:** 4 – Umsetzung

## Zweck
Autonome Erstellung und Testung von Code oder Workflows bis zum Prototyp. Eine agentische Fabrik, die Tickets liest, Code generiert und in einer isolierten Sandbox validiert.

## Messages
- **Consumed:** Blueprint, Ticket-Set, API-Specs (aus BC3)
- **Produced:** Funktionaler Prototyp (ZIP, JSON oder Sandbox-URL), Test- & Deployment-Report, Dokumentation

## Arbeitspakete
- **AP 4.1** Agentic Coder Workflow (LangChain / AutoGen / CrewAI)
- **AP 4.2** Sandbox Execution Environment (Docker, isoliert)
- **AP 4.3** Auto-Testing & Feedback Loop (max. 3 Self-Correction-Versuche)
- **AP 4.4** Deployment & Reporting

## Schnittstellen
- **Input von BC3:** `/contracts/bc3-to-bc4/`
- **Output:** Prototyp produktiv in Sandbox
