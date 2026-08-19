import pandas as pd
import os
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

script_dir = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(script_dir, "../data/raw/All Pet Supplies.csv")
MODEL_DIR = os.path.join(script_dir, "../app/models/recsys")

def main():
    print(f"Loading dataset from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    
    # 1. Clean the text data (we'll use 'name')
    print("Preprocessing text data...")
    df['name'] = df['name'].fillna('')
    
    # 2. Initialize TF-IDF Vectorizer
    # We remove english stop words (like 'and', 'the', etc.)
    print("Vectorizing product names using TF-IDF...")
    tfidf = TfidfVectorizer(stop_words='english')
    
    # Fit and transform the data
    tfidf_matrix = tfidf.fit_transform(df['name'])
    
    # 3. Compute the Cosine Similarity Matrix
    print("Computing Cosine Similarity Matrix...")
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
    
    # 4. Save the model artifacts for FastAPI
    print("Saving model artifacts...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    # Save the dataframe (so we can look up product names by index)
    # We'll save a lightweight version to save memory
    df_light = df[['name', 'sub_category', 'image', 'link', 'discount_price', 'ratings']].reset_index(drop=True)
    df_light.to_pickle(os.path.join(MODEL_DIR, "products_df.pkl"))
    
    # Save the similarity matrix
    with open(os.path.join(MODEL_DIR, "cosine_sim.pkl"), "wb") as f:
        pickle.dump(cosine_sim, f)
        
    print(f"Success! Model artifacts saved to {MODEL_DIR}")
    
    # Let's test the recommendation engine locally
    test_product = df_light['name'].iloc[0]
    print(f"\n--- Testing Recommendations for: '{test_product}' ---")
    
    # Get the index of the product
    idx = 0
    # Get pairwise similarity scores for all products
    sim_scores = list(enumerate(cosine_sim[idx]))
    # Sort them based on similarity score (descending)
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    # Get the top 5 most similar products (excluding itself)
    top_5_indices = [i[0] for i in sim_scores[1:6]]
    
    for i in top_5_indices:
        print(f"-> {df_light['name'].iloc[i]} (Score: {sim_scores[1:6][top_5_indices.index(i)][1]:.2f})")

if __name__ == "__main__":
    main()
