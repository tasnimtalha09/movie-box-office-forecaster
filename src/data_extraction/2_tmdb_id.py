## This scrapper was built with the help of AI

def fetch_tmdb_id(dataset, dataset_name):
    # Import required libraries
    import pandas as pd
    import requests
    import time
    import random
    import os
    import re
    from tqdm import tqdm

    # 1. creating a unique Movie_ID which will help in merging later
    dataset["Movie_ID"] = pd.factorize(dataset["Release"])[0] + 1

    # 2. Creating a list of unique movies
    unique_movies = dataset[["Movie_ID", "Release"]].drop_duplicates().reset_index(drop=True)

    # 2.5 TITLE CLEANING FUNCTION (improved: handles "40th Anniversary", glued years, ordinals, IMAX, etc.)
    def clean_movie_title(title):
        """Clean movie titles for better TMDB matching"""
        if pd.isna(title) or title == "":
            return ""

        t = str(title).strip()

        # Normalize common unicode and collapse spaces
        t = re.sub(r'\u2019', "'", t)
        t = re.sub(r'\s+', ' ', t).strip()

        # 0) Insert space between letters and attached year/ordinal (e.g., "Pool2021" -> "Pool 2021", "Future40th" -> "Future 40th")
        t = re.sub(r'([A-Za-z])(\d{4})', r'\1 \2', t)  # letters + 4-digit year
        t = re.sub(r'([A-Za-z])(\d{1,2}(?:st|nd|rd|th))', r'\1 \2', t, flags=re.IGNORECASE)  # letters + ordinal

        # 1) Remove parenthetical content like "(Re-release)" or "(IMAX)"
        t = re.sub(r'\(.*?\)', '', t)

        # 2) Remove common suffixes and anniversary patterns
        suffix_patterns = [
            r'\b\d{4}\s*Re-release\b',                       # "2016 Re-release"
            r'\b\d{4}\s*IMAX Release\b',
            r'\b\d{4}\s*3D Release\b',
            r'\b\d{1,2}(?:st|nd|rd|th)\s*Anniversary\b',     # "40th Anniversary"
            r'\b\d{1,2}(?:st|nd|rd|th)\s*Anniversary\s*Edition\b',
            r'\b\d{4}\s*Anniversary\b',
            r'\bAnniversary\b',
            r'\bAnniversary\s*Edition\b',
            r'\bSpecial Edition\b',
            r'\bDirector\'s Cut\b',
            r'\bIMAX\b',
            r'\bIMAX Release\b',
            r'\bRe-release\b',
            r'\bReissue\b'
        ]
        for pat in suffix_patterns:
            t = re.sub(pat, '', t, flags=re.IGNORECASE)

        # 3) Remove stray years (optional) that remain alone (e.g., trailing " 2016")
        t = re.sub(r'\b(18|19|20)\d{2}\b', '', t)

        # 4) Normalize punctuation:
        #    Keep apostrophes and ampersands, remove other punctuation that often breaks search.
        #    If you want to preserve dots in "E.T." change this line accordingly.
        t = re.sub(r'[^\w\s\'&\-]', ' ', t)

        # 5) Collapse multiple spaces and strip
        t = re.sub(r'\s+', ' ', t).strip()

        # 6) Final trim of leading/trailing punctuation or stray hyphens
        t = re.sub(r'^[\-\_:;,\s]+|[\-\_:;,\s]+$', '', t).strip()

        return t

    # Apply title cleaning
    unique_movies["Original_Release"] = unique_movies["Release"]
    unique_movies["Cleaned_Release"] = unique_movies["Release"].apply(clean_movie_title)

    print(f"📋 Processing {len(unique_movies)} unique movies for TMDB IDs...")
    print("Sample title cleaning:")
    for i in range(min(5, len(unique_movies))):
        orig = unique_movies.iloc[i]["Original_Release"]
        clean = unique_movies.iloc[i]["Cleaned_Release"]
        if orig != clean:
            print(f"  '{orig}' → '{clean}'")

    # 3. Running the script that will fetch the TMDB_ID (safe version)
    API_KEY = "421f11c4237f095cebba1f0a5c4935dc"
    BASE_URL = "https://api.themoviedb.org/3"
    SEARCH_URL = f"{BASE_URL}/search/movie"

    CACHE_FN = "tmdb_cache.csv"
    SAVE_EVERY = 100
    SLEEP_BASE = 0.25
    MAX_ATTEMPTS = 5
    MAX_BACKOFF = 30

    # load cache if exists
    if os.path.exists(CACHE_FN):
        try:
            cache_df = pd.read_csv(CACHE_FN, dtype = {"title": str, "tmdb_id": "Int64"})
            cache_map = dict(zip(cache_df["title"].astype(str), cache_df["tmdb_id"]))
        except Exception:
            cache_map = {}
    else:
        cache_map = {}

    session = requests.Session()
    session.params = {"api_key": API_KEY}

    def tmdb_search_movie_safe(title):
        title = str(title).strip()
        if title == "" or title.lower() == "nan":
            return None

        # fast path: cached
        if title in cache_map:
            return cache_map[title]

        params = {"query": title, "include_adult": False}

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                resp = session.get(SEARCH_URL, params = params, timeout=15)

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait = int(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, MAX_BACKOFF)
                    wait += random.uniform(0, 0.5)
                    print(f"[429] Rate limited for '{title}', waiting {wait:.1f}s")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                tmdb_id = int(results[0]["id"]) if results else None

                cache_map[title] = tmdb_id
                return tmdb_id

            except requests.RequestException as e:
                wait = min(2 ** attempt, MAX_BACKOFF) + random.uniform(0, 0.6)
                if attempt == MAX_ATTEMPTS:
                    print(f"❌ Failed to fetch TMDB id for '{title}' after {MAX_ATTEMPTS} attempts")
                time.sleep(wait)
                continue

        cache_map[title] = None
        return None

    # Use CLEANED titles for TMDB search
    titles = unique_movies["Cleaned_Release"].astype(str).tolist()
    tmdb_results = []

    successful = 0
    failed = 0

    for idx, t in enumerate(tqdm(titles, desc="TMDB lookups")):
        tmdb_id = tmdb_search_movie_safe(t)
        tmdb_results.append(tmdb_id)

        if tmdb_id is not None:
            successful += 1
        else:
            failed += 1

        time.sleep(SLEEP_BASE + random.uniform(0, 0.15))

        if (idx + 1) % SAVE_EVERY == 0 or (idx + 1) == len(titles):
            cache_rows = [{"title": k, "tmdb_id": (v if v is not None else "")} for k, v in cache_map.items()]
            pd.DataFrame(cache_rows).to_csv(CACHE_FN, index=False)
            print(f"Flushed cache to {CACHE_FN} ({len(cache_map)} entries)")

    # attach tmdb ids to unique_movies and merge back to main dataframe
    unique_movies["tmdb_id"] = pd.Series(tmdb_results, dtype = "Int64")

    # Progress summary
    print(f"✅ TMDB matching complete!")
    print(f"   Successful matches: {successful}")
    print(f"   Failed matches: {failed}")
    print(f"   Success rate: {successful/(successful+failed)*100:.1f}%")

    dataset_merged = pd.merge(
        left = dataset,
        right = unique_movies[["Movie_ID", "Release", "tmdb_id"]],  # Use original Release for merging
        on = ["Movie_ID", "Release"],
        how = "left"
    )
    dataset_merged.drop(columns = ["Movie_ID"], inplace = True)

    # save master and cache for safety
    try:
        dataset_merged.to_csv(f"{dataset_name}.csv", index = False, date_format = "%Y-%m-%d")
        cache_rows = [{"title": k, "tmdb_id": (v if v is not None else "")} for k, v in cache_map.items()]
        pd.DataFrame(cache_rows).to_csv(CACHE_FN, index = False)
        print(f"Saved {dataset_name}.csv and tmdb_cache.csv")
    except Exception as e:
        print(f"Warning: failed to write {dataset_name}.csv or cache:", e)

    return dataset_merged