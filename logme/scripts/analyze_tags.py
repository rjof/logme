import os
import sys
import sqlite3
import pandas as pd
import logging
import re
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
    total_tags = len(df)
    unique_tags = df['tag'].nunique()
    tag_counts = df['tag'].value_counts()

    print("\n" + "="*40)
    print("INSTAGRAM TAGS DESCRIPTIVE STATISTICS")
    print("="*40)
    print(f"Total tags recorded: {total_tags}")
    print(f"Unique tags:         {unique_tags}")
    print(f"Average tag frequency: {total_tags/unique_tags:.2f}")

    print("\nTOP 20 TAGS:")
    print(tag_counts.head(20).to_string())

    emoji_tags = df[df['tag'].apply(is_emoji)]
    print(f"\nEmoji-only tags: {len(emoji_tags)} ({len(emoji_tags)/total_tags*100:.1f}%)")
    if not emoji_tags.empty:
        print("Top Emojis:")
        print(emoji_tags['tag'].value_counts().head(10).to_string())

    # 4. Semantic Grouping (Option A)
    print("\n" + "="*40)
    print("SEMANTIC GROUPING (Option A)")
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

    # Filter to tags with frequency > 1 to reduce noise and computation
    frequent_tags_df = tag_counts[tag_counts > 1].reset_index()
    frequent_tags_df.columns = ['tag', 'count']
    
    tags_to_cluster = frequent_tags_df['tag'].tolist()
    
    if len(tags_to_cluster) < 5:
        print("Not enough frequent tags (count > 1) to perform meaningful clustering.")
        return

    print(f"Clustering {len(tags_to_cluster)} tags with frequency > 1...")

    # Load model (small and fast)
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(tags_to_cluster)

    # Simple K-Means clustering
    # We'll estimate the number of clusters as 1/5th of the tags, or at least 5
    n_clusters = max(5, len(tags_to_cluster) // 5)
    n_clusters = min(n_clusters, 50) # Cap at 50 for this prototype
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(embeddings)

    # Group tags by cluster
    clustered_tags = {}
    for i, cluster_id in enumerate(clusters):
        if cluster_id not in clustered_tags:
            clustered_tags[cluster_id] = []
        clustered_tags[cluster_id].append((tags_to_cluster[i], frequent_tags_df.iloc[i]['count']))

    # Print clusters
    print(f"\nIdentified {n_clusters} semantic groups:")
    
    # Sort clusters by total count of tags within them
    cluster_summaries = []
    for cid, tags in clustered_tags.items():
        total_count = sum(t[1] for t in tags)
        # Canonical label is the most frequent tag in the cluster
        canonical = max(tags, key=lambda x: x[1])[0]
        cluster_summaries.append({
            'cid': cid,
            'canonical': canonical,
            'total_count': total_count,
            'tags': tags
        })
    
    cluster_summaries.sort(key=lambda x: x['total_count'], reverse=True)

    for summary in cluster_summaries[:15]: # Show top 15 clusters
        tags_str = ", ".join([f"{t[0]}({t[1]})" for t in sorted(summary['tags'], key=lambda x: x[1], reverse=True)[:10]])
        print(f"\nGroup: [{summary['canonical'].upper()}] (Total frequency: {summary['total_count']})")
        print(f"Tags: {tags_str}" + ("..." if len(summary['tags']) > 10 else ""))

if __name__ == "__main__":
    analyze_tags()
