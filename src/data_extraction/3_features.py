## This scrapper was built with the help of AI

# defining the scraper
def enrich_tmdb_details_with_imdb(
    fact,
    tmdb_id_col = "TMDB_ID",
    cache_fn = "tmdb_movie_details_cache.csv",
    save_every = 100,
    sleep_base = 0.25,
    max_attempts = 5,
    max_backoff = 30
):
    
    # Import required libraries
    import pandas as pd
    import requests
    import time
    import random
    import os
    from tqdm import tqdm

    # Storing the keys
    tmdb_api_key = "421f11c4237f095cebba1f0a5c4935dc"
    omdb_api_key = "27eef253"

    # --- 1. Prepare IDs ---
    fact = master.copy()
    fact[tmdb_id_col] = fact[tmdb_id_col].astype(int)

    unique_ids = fact[tmdb_id_col].drop_duplicates().tolist()
    print(f"🔍 Fetching details for {len(unique_ids)} unique TMDB IDs")

    # --- 2. Load cache ---
    if os.path.exists(cache_fn):
        try:
            cache_df = pd.read_csv(cache_fn, dtype=str)
            cache_map = {
                str(row["TMDB_ID"]): {
                    "genres": row.get("genres"),
                    "runtime": row.get("runtime"),
                    "country": row.get("country"),
                    "rating": row.get("rating"),
                    "budget": row.get("budget"),
                    "imdb_rating": row.get("imdb_rating"),
                    "actor_1": row.get("actor_1"),
                    "actor_2": row.get("actor_2"),
                    "actor_3": row.get("actor_3"),
                    "director": row.get("director"),

                    # NEW FIELDS:
                    "imdb_id": row.get("imdb_id"),
                    "popularity": row.get("popularity"),
                    "is_franchise": row.get("is_franchise"),
                }
                for _, row in cache_df.iterrows()
            }
        except Exception:
            cache_map = {}
    else:
        cache_map = {}

    session = requests.Session()
    movie_url = "https://api.themoviedb.org/3/movie/{}"
    external_url = "https://api.themoviedb.org/3/movie/{}/external_ids"
    credits_url = "https://api.themoviedb.org/3/movie/{}/credits"
    session.params = {"api_key": tmdb_api_key}

    # --- 3. Helper: get IMDb rating ---
    def fetch_imdb_rating(imdb_id):
        if not imdb_id:
            return None

        url = "https://www.omdbapi.com/"
        params = {"apikey": omdb_api_key, "i": imdb_id}

        try:
            r = requests.get(url = url, params = params, timeout = 10)
            r.raise_for_status()
            data = r.json()
            rating = data.get("imdbRating")
            return rating if rating not in ("N/A", None) else None
        except:
            return None

    # --- 4. Helper: safe TMDB fetch (includes credits + new fields) ---
    def fetch_one_movie(tmdb_id):
        tmdb_id_str = str(tmdb_id)

        # Instant cache return
        if tmdb_id_str in cache_map:
            return cache_map[tmdb_id_str]

        # 4A. Fetch main movie details from TMDB
        url = movie_url.format(tmdb_id)
        params = {"append_to_response": "release_dates"}

        for attempt in range(1, max_attempts + 1):
            try:
                resp = session.get(url = url, params = params, timeout = 15)

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait = (
                        int(retry_after)
                        if retry_after and retry_after.isdigit()
                        else min(2 ** attempt, max_backoff)
                    )
                    wait += random.uniform(0, 0.5)
                    print(f"[429] TMDB rate limited for {tmdb_id}, waiting {wait:.1f}s")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                # Extract TMDB fields
                genres = [g["name"] for g in data.get("genres", [])]
                runtime = data.get("runtime")
                budget = data.get("budget")

                countries = data.get("production_countries", [])
                country = countries[0]["name"] if countries else None

                # NEW: popularity
                popularity = data.get("popularity", None)

                # NEW: franchise indicator
                is_franchise = True if data.get("belongs_to_collection") else False

                # U.S. MPAA rating
                rating = None
                try:
                    rels = data.get("release_dates", {}).get("results", [])
                    for entry in rels:
                        if entry.get("iso_3166_1") == "US":
                            for info in entry.get("release_dates", []):
                                if info.get("certification"):
                                    rating = info["certification"]
                                    break
                except:
                    pass

                # 4B. Get IMDb ID via TMDB external_ids
                try:
                    ext = session.get(external_url.format(tmdb_id), timeout = 10).json()
                    imdb_id = ext.get("imdb_id")
                except:
                    imdb_id = None

                # 4C. Fetch IMDb rating if available
                imdb_rating = fetch_imdb_rating(imdb_id)

                # 4D. Fetch credits (actors and director)
                actor_1 = actor_2 = actor_3 = director = None
                try:
                    cred = session.get(credits_url.format(tmdb_id), timeout = 15).json()
                    cast = cred.get("cast", []) or []

                    if cast:
                        actor_1 = cast[0].get("name")
                    if len(cast) > 1:
                        actor_2 = cast[1].get("name")
                    if len(cast) > 2:
                        actor_3 = cast[2].get("name")

                    crew = cred.get("crew", []) or []
                    for member in crew:
                        if member.get("job", "").lower() == "director":
                            director = member.get("name")
                            break
                except:
                    pass

                result = {
                    "genres": ", ".join(genres) if genres else "",
                    "runtime": runtime,
                    "country": country,
                    "rating": rating,
                    "budget": budget,
                    "imdb_rating": imdb_rating,
                    "actor_1": actor_1,
                    "actor_2": actor_2,
                    "actor_3": actor_3,
                    "director": director,

                    # NEW FIELDS
                    "imdb_id": imdb_id,
                    "popularity": popularity,
                    "is_franchise": is_franchise,
                }

                cache_map[tmdb_id_str] = result
                return result

            except Exception as e:
                wait = min(2 ** attempt, max_backoff) + random.uniform(0, 0.6)
                if attempt == max_attempts:
                    print(f"❌ TMDB fetch failed for ID {tmdb_id}: {e}")
                time.sleep(wait)

        # fallback
        result = {
            "genres": "",
            "runtime": None,
            "country": None,
            "rating": None,
            "budget": None,
            "imdb_rating": None,
            "actor_1": None,
            "actor_2": None,
            "actor_3": None,
            "director": None,
            "imdb_id": None,
            "popularity": None,
            "is_franchise": None
        }
        cache_map[tmdb_id_str] = result
        return result

    # --- 5. Loop over all IDs ---
    results = {}
    for idx, mid in enumerate(tqdm(unique_ids, desc = "TMDB + IMDb Enrichment")):
        details = fetch_one_movie(mid)
        results[mid] = details

        time.sleep(sleep_base + random.uniform(0, 0.15))

        if (idx + 1) % save_every == 0 or (idx + 1) == len(unique_ids):
            df_cache = pd.DataFrame([{"TMDB_ID": k, **v} for k, v in cache_map.items()])
            df_cache.to_csv(cache_fn, index=False)
            print(f"💾 Cache saved ({len(df_cache)} entries).")

    # --- 6. Convert results to DataFrame & merge ---
    details_df = pd.DataFrame([{"TMDB_ID": mid, **details} for mid, details in results.items()])
    fact_enriched = fact.merge(details_df, on = "TMDB_ID", how = "left")

    print("✨ Enrichment complete.")
    return fact_enriched