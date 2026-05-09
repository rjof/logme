# Tech Stack

The `logme` project is built with a focus on local-first data management, modularity, and future scalability.

## Core Language & Frameworks
- **Python 3.x:** The primary language for ingestion, processing, and analysis.
- **Typer:** Used for building a clean, intuitive Command Line Interface (CLI).
- **SQLAlchemy:** SQL Toolkit and Object Relational Mapper (ORM), used to provide database abstraction and facilitate future migrations.

## Data Storage & Architecture
- **SQLite:** Currently used as the primary data store for its simplicity and "zero-configuration" local-first approach.
- **Medallion Architecture:**
    - **Raw:** Unmodified data ingested directly from sources.
    - **L1 (Integration):** Cleaned and typed data.
    - **L2 (Processing):** Semantically enriched or aggregated data for analysis.

## Ingestion & Integration
- **Instaloader & Selenium:** For Instagram data retrieval.
- **Duolingo-api:** Unofficial API for Duolingo achievement tracking.
- **Requests:** For general API interactions (aTimeLogger, etc.).
- **Dropbox/Google Drive APIs:** For cloud-based file synchronization and storage.

## Analysis & Machine Learning
- **Pandas & NumPy:** For data manipulation and statistical analysis.
- **Scikit-learn:** For clustering and classification (e.g., semantic tag grouping).
- **Sentence-Transformers:** For generating embeddings to facilitate semantic analysis.

## Frontend & Visualization (Planned)
- **Shiny (R) or Express (Node.js):** Evaluating these for a future visual dashboard to display statistics and trends.

## DevOps & Tooling
- **Pytest:** For unit and integration testing.
- **python-dotenv:** For managing environment variables and credentials.
- **Config.ini:** For user-specific configuration of local paths and source settings.
