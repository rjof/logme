import os
import sys
import sqlite3
import pandas as pd
import logging
import re
import unicodedata
from pathlib import Path

# Add project root to sys.path to allow imports from logme
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from logme import CONFIG_FILE_PATH
from logme.utils import Utils as u
from logme.storage.database import DatabaseHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def is_emoji(s):
    # Simple check for emojis (matches common emoji ranges)
    return bool(re.match(r'^[\U0001f300-\U0001f9ff\U0001f600-\U0001f64f]+$', s))

def normalize_text(text):
    """Normalize text to handle accents and casing."""
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # Remove accents/diacritics for better comparison (optional for embeddings but good for counts)
    text = "".join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    return text

def analyze_tags():
    # 1. Configuration Discovery
    try:
        db_path = u.get_database_path(CONFIG_FILE_PATH)
        if not db_path.exists():
            logger.error(f"Database not found at {db_path}")
            return
    except Exception as e:
        logger.error(f"Error finding database path: {e}")
        return

    try:
        src = "instagram"
        conf = u.get_source_conf(src, f'{src}_l1_to_tags_l2')
        table_name = conf.get("table_name", "instagram_tags_l2")
    except Exception:
        table_name = "instagram_tags_l2"
        logger.warning(f"Could not find configuration for {src}_l1_to_tags_l2. Defaulting to {table_name}")

    logger.info(f"Analyzing tags from table '{table_name}' in database {db_path}")

    # 2. Load Data
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    except Exception as e:
        logger.error(f"Error reading table {table_name}: {e}")
        return
    finally:
        conn.close()

    if df.empty:
        logger.info("No data found in the tags table.")
        return

    # 3. Descriptive Statistics
    # For stats, we use the raw tags but we'll also show unique normalized tags
    total_tags = len(df)
    unique_tags = df['tag'].nunique()
    
    # Create normalized column for better grouping in stats
    df['tag_norm'] = df['tag'].apply(normalize_text)
    unique_tags_norm = df['tag_norm'].nunique()
    
    tag_counts = df['tag'].value_counts()

    print("\n" + "="*40)
    print("INSTAGRAM TAGS DESCRIPTIVE STATISTICS")
    print("="*40)
    print(f"Total tags recorded: {total_tags}")
    print(f"Unique tags (raw):    {unique_tags}")
    print(f"Unique tags (norm):   {unique_tags_norm}")
    print(f"Average tag frequency: {total_tags/unique_tags:.2f}")

    print("\nTOP 20 TAGS (Raw):")
    print(tag_counts.head(20).to_string())

    emoji_tags = df[df['tag'].apply(is_emoji)]
    print(f"\nEmoji-only tags: {len(emoji_tags)} ({len(emoji_tags)/total_tags*100:.1f}%)")
    if not emoji_tags.empty:
        print("Top Emojis:")
        print(emoji_tags['tag'].value_counts().head(10).to_string())

    # 4. Semantic Grouping (Multilingual Option A)
    print("\n" + "="*40)
    print("MULTILINGUAL SEMANTIC GROUPING")
    print("="*40)

    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.cluster import KMeans
        import numpy as np
    except ImportError:
        print("\n[!] Required libraries for semantic grouping are missing.")
        print("Please install them using:")
        print("pip install sentence-transformers scikit-learn")
        return

    # For clustering, we use the unique normalized tags to avoid redundant vectors
    # and we focus on those appearing more than once to reduce noise
    norm_counts = df['tag_norm'].value_counts()
    frequent_norm = norm_counts[norm_counts > 1].reset_index()
    frequent_norm.columns = ['tag_norm', 'count']
    
    tags_to_cluster = frequent_norm['tag_norm'].tolist()
    
    if len(tags_to_cluster) < 5:
        print("Not enough frequent tags (count > 1) to perform meaningful clustering.")
        return

    print(f"Clustering {len(tags_to_cluster)} unique concepts across languages...")

    # Load MULTILINGUAL model
    # paraphrase-multilingual-MiniLM-L12-v2 supports 50+ languages including Spanish and English
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    embeddings = model.encode(tags_to_cluster)

    # Simple K-Means clustering
    n_clusters = max(5, len(tags_to_cluster) // 6)
    n_clusters = min(n_clusters, 60) # Slightly higher cap for multilingual diversity
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(embeddings)

    # Group tags by cluster
    clustered_tags = {}
    for i, cluster_id in enumerate(clusters):
        if cluster_id not in clustered_tags:
            clustered_tags[cluster_id] = []
        
        # Find raw tags that map to this normalized tag for display
        raw_tags = df[df['tag_norm'] == tags_to_cluster[i]]['tag'].unique().tolist()
        raw_tags_str = "/".join(raw_tags)
        
        clustered_tags[cluster_id].append((raw_tags_str, frequent_norm.iloc[i]['count']))

    # Print clusters
    print(f"\nIdentified {n_clusters} cross-lingual semantic groups:")
    
    cluster_summaries = []
    for cid, tags in clustered_tags.items():
        total_count = sum(t[1] for t in tags)
        # Canonical label is the most frequent normalized concept
        canonical = max(tags, key=lambda x: x[1])[0]
        cluster_summaries.append({
            'cid': cid,
            'canonical': canonical,
            'total_count': total_count,
            'tags': tags
        })
    
    cluster_summaries.sort(key=lambda x: x['total_count'], reverse=True)

    for summary in cluster_summaries[:20]: # Show top 20 clusters
        tags_str = ", ".join([f"{t[0]}({t[1]})" for t in sorted(summary['tags'], key=lambda x: x[1], reverse=True)[:10]])
        print(f"\nGroup: [{summary['canonical'].upper()}] (Total freq: {summary['total_count']})")
        print(f"Tags: {tags_str}" + ("..." if len(summary['tags']) > 10 else ""))

if __name__ == "__main__":
    analyze_tags()

if __name__ == "__main__":
    analyze_tags()
