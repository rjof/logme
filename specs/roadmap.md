# Roadmap

The development of `logme` follows a phased approach, prioritizing the stability of core features before expanding the ecosystem.

## Phase 1: Stabilization & Refactoring (Current Focus)
- **Standardize Processing:** Refactor existing sources (Instagram, Duolingo, aTimeLogger) to follow the uniform processing pattern established by the Multi_Timer source.
- **Robustness:** Implement better error handling, logging, and retry mechanisms for fragile scrapers (Instagram/Selenium).
- **Offline Mode:** Complete the implementation of offline processing for Instagram posts to allow metadata extraction without active internet connections.
- **Data Quality:** Add automated checks to ensure integrity between Medallion layers (Raw -> L1 -> L2).

## Phase 2: Visualization & Analysis
- **Personal Dashboard:** Develop a visual interface using Shiny or Express to provide a high-level overview of personal logs.
- **Semantic Tagging:** Mature the Instagram tag analysis tool to provide automatic concept mapping and "family tree" visualizations.
- **Rule Engine:** Implement a simple notification system based on data trends (e.g., "Third day without exercise" alerts).
- **Anki Integration:** Automate the creation of Anki flashcards from Koreader clippings and highlights.

## Phase 3: Source Expansion
- **Entertainment:** Integrate Spotify (listening history) and Podcast Addict.
- **Communication:** Add WhatsApp chat history ingestion and analysis (e.g., response time metrics).
- **Health & Wearables:** Integrate data from Redmi Watch, Mi Band, and Google Maps Timeline.
- **Reading:** Enhance Koreader statistics and clipping ingestion.

## Phase 4: Intelligence & Scalability
- **Database Migration:** Prepare for and potentially execute a migration to a more robust database (e.g., PostgreSQL) as data volume grows.
- **GPT-Powered Insights:** Integrate LLMs for automated book summaries, question generation from notes, and conversational queries over the personal data lake.
- **Open-Source Hardening:** Refactor the codebase to make it easier for third-party contributors to add new source connectors.
