"""
Diagnostic-only script (not part of the production pipeline). Covers tasks
#41-#45 (knowledge-graph-section pre-build testing) in one pass, since all
five need the same live API access:

  1. Filename -> HydraDB source ID mapping: does context.list()'s .title
     (or .metadata) hold the exact filename string used elsewhere as
     source_title (e.g. "peloton_2022-02-08_8k.md")?
  2. context.relations(id=<source_id>) shape: how many relations per doc,
     what GraphEntity.type values appear, are context/temporal_details/
     confidence populated?
  3. Multi-document merge: pull relations for all 5 real documents cited by
     the Feb 2022 event (from outputs/timeline_cache.json) and check whether
     the same entity (e.g. "Peloton") comes back with a consistent name
     string across documents, or needs normalization before node-merging.
  4. Truncation/pagination: is_truncated / next_cursor on the densest doc.
  5. Determinism: call relations() twice for the same source_id and diff.

Reads HYDRA_DB_API_KEY / HYDRA_DB_TENANT_ID from .env. Run locally — the
sandbox can't reach api.hydradb.com.
"""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    from hydra_db import HydraDB
except ImportError:
    sys.exit("hydra_db SDK not installed. Run: pip install hydradb-sdk")

API_KEY = os.environ.get("HYDRA_DB_API_KEY")
TENANT_ID = os.environ.get("HYDRA_DB_TENANT_ID", "stock-market-decoder")
SUB_TENANT_ID = "default"

if not API_KEY:
    sys.exit("HYDRA_DB_API_KEY not set in .env")

client = HydraDB(token=API_KEY)

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "outputs" / "_knowledge_graph_relations_test_results.json"
CACHE_PATH = REPO_ROOT / "outputs" / "timeline_cache.json"

# The real Feb 2022 event cites 5 documents across two filing dates — the
# richest multi-document case in the dataset, and the one that prompted the
# "one Click to decode" merge fix. Falls back to a hardcoded list if the
# cache isn't present/shaped as expected.
FALLBACK_FEB_2022_DOCS = [
    "peloton_2022-02-05_8k.md",
    "peloton_2022-02-05_board-pr.md",
    "peloton_2022-02-08_8k.md",
    "peloton_2022-02-08_restructuring-pr.md",
    "peloton_2022-02-08_shareholder-letter.md",
]


def log(msg):
    print(f"[test_knowledge_graph_relations] {msg}", flush=True)


def load_feb_2022_docs():
    try:
        cache = json.loads(CACHE_PATH.read_text())
        months = cache.get("months", cache) if isinstance(cache, dict) else cache
        if isinstance(months, dict):
            months = months.get("months", [])
        for m in months:
            if str(m.get("month", "")) == "2022-02" and m.get("event"):
                docs = sorted({
                    d for g in m["event"].get("evidence", []) for d in g.get("documents", [])
                })
                if docs:
                    log(f"Loaded Feb 2022 doc list from timeline_cache.json: {docs}")
                    return docs
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        log(f"Couldn't load timeline_cache.json ({e}), using fallback doc list.")
    return FALLBACK_FEB_2022_DOCS


def list_sources():
    """context.list() -> raw dicts per hydra_db's own type definition
    (List[Dict[str, Any]], confirmed in list_source_list_response.py —
    NOT a parsed pydantic model like the query()/relations() responses)."""
    result = client.context.list(
        tenant_id=TENANT_ID,
        sub_tenant_id=SUB_TENANT_ID,
        type="knowledge",
    )
    return result.data.sources or []


def get_relations(source_id, limit=200):
    result = client.context.relations(
        tenant_id=TENANT_ID,
        sub_tenant_id=SUB_TENANT_ID,
        id=source_id,
        type="knowledge",
        limit=limit,
    )
    return result.data


def triplet_to_dict(t):
    return {
        "chunk_id": t.chunk_id,
        "source": {"name": t.source.name, "type": t.source.type, "entity_id": t.source.entity_id} if t.source else None,
        "target": {"name": t.target.name, "type": t.target.type, "entity_id": t.target.entity_id} if t.target else None,
        "relations": [
            {
                "canonical_predicate": r.canonical_predicate,
                "raw_predicate": r.raw_predicate,
                "context": r.context,
                "temporal_details": r.temporal_details,
                "confidence": r.confidence,
            }
            for r in (t.relations or [])
        ],
    }


def main():
    results = {}

    # --- Task 41: filename -> source ID mapping ------------------------
    log("=== Task 41: filename -> source ID mapping ===")
    sources = list_sources()
    log(f"context.list() returned {len(sources)} sources total.")

    docs_needed = load_feb_2022_docs()
    filename_to_id = {}
    mapping_rows = []
    for doc in sources:
        title = doc.get("title")
        metadata = doc.get("metadata") or {}
        additional_metadata = doc.get("additional_metadata") or {}
        candidates = {title, metadata.get("source_title"), additional_metadata.get("source_title")}
        matched_filename = next((f for f in docs_needed if f in candidates), None)
        if matched_filename:
            filename_to_id[matched_filename] = doc.get("id")
            mapping_rows.append({
                "filename": matched_filename,
                "id": doc.get("id"),
                "title": title,
                "metadata_source_title": metadata.get("source_title"),
                "additional_metadata_source_title": additional_metadata.get("source_title"),
            })

    for row in mapping_rows:
        log(f"  {row['filename']} -> id={row['id']} | title={row['title']!r} | "
            f"metadata.source_title={row['metadata_source_title']!r} | "
            f"additional_metadata.source_title={row['additional_metadata_source_title']!r}")

    missing = [f for f in docs_needed if f not in filename_to_id]
    if missing:
        log(f"  COULD NOT MAP: {missing} — inspect a raw source dict below to find the right field.")
        if sources:
            log(f"  Sample raw source dict keys: {list(sources[0].keys())}")
            log(f"  Sample raw source dict: {json.dumps(sources[0], indent=2, default=str)[:1500]}")

    results["task_41_filename_to_id"] = {
        "n_sources_total": len(sources),
        "mapping": mapping_rows,
        "missing": missing,
    }

    if not filename_to_id:
        log("No documents mapped to source IDs — cannot proceed with tasks 42-45. Stopping here.")
        RESULTS_PATH.parent.mkdir(exist_ok=True)
        RESULTS_PATH.write_text(json.dumps(results, indent=2, default=str))
        log(f"Saved partial results to {RESULTS_PATH}")
        return

    # --- Task 42: inspect relations() shape for one document -----------
    log("=== Task 42: relations() shape for one document ===")
    first_filename, first_id = next(iter(filename_to_id.items()))
    log(f"Using {first_filename} (id={first_id})")
    one_doc_data = get_relations(first_id)
    one_doc_triplets = [triplet_to_dict(t) for t in (one_doc_data.relations or [])]
    entity_types = Counter()
    predicates = Counter()
    context_populated = 0
    temporal_populated = 0
    for t in one_doc_triplets:
        if t["source"]:
            entity_types[t["source"]["type"]] += 1
        if t["target"]:
            entity_types[t["target"]["type"]] += 1
        for r in t["relations"]:
            predicates[r["canonical_predicate"]] += 1
            if r["context"]:
                context_populated += 1
            if r["temporal_details"]:
                temporal_populated += 1

    log(f"  n_triplets={len(one_doc_triplets)} is_truncated={one_doc_data.is_truncated} "
        f"next_cursor={one_doc_data.next_cursor}")
    log(f"  entity types seen: {dict(entity_types)}")
    log(f"  top predicates: {predicates.most_common(10)}")
    log(f"  relations with non-empty context: {context_populated}, with temporal_details: {temporal_populated}")
    if one_doc_triplets:
        log(f"  sample triplet: {json.dumps(one_doc_triplets[0], indent=2, default=str)}")

    results["task_42_single_doc_shape"] = {
        "filename": first_filename,
        "n_triplets": len(one_doc_triplets),
        "is_truncated": one_doc_data.is_truncated,
        "entity_types": dict(entity_types),
        "top_predicates": predicates.most_common(10),
        "sample_triplets": one_doc_triplets[:5],
    }

    # --- Task 43: multi-document merge ----------------------------------
    log("=== Task 43: multi-document merge (Feb 2022, all mapped docs) ===")
    per_doc_triplets = {}
    for filename, source_id in filename_to_id.items():
        data = get_relations(source_id)
        per_doc_triplets[filename] = [triplet_to_dict(t) for t in (data.relations or [])]
        log(f"  {filename}: {len(per_doc_triplets[filename])} triplets, is_truncated={data.is_truncated}")

    all_names = defaultdict(set)  # lowercased name -> set of exact name strings seen
    name_to_docs = defaultdict(set)
    all_triplets = []
    for filename, triplets in per_doc_triplets.items():
        for t in triplets:
            all_triplets.append(t)
            for entity_key in ("source", "target"):
                entity = t[entity_key]
                if entity and entity["name"]:
                    all_names[entity["name"].lower()].add(entity["name"])
                    name_to_docs[entity["name"]].add(filename)

    total_unique_nodes_by_lowercase = len(all_names)
    inconsistent_casing = {k: v for k, v in all_names.items() if len(v) > 1}
    peloton_variants = {k: v for k, v in all_names.items() if "peloton" in k}

    log(f"  total triplets across all docs: {len(all_triplets)}")
    log(f"  unique node names (case-insensitive): {total_unique_nodes_by_lowercase}")
    log(f"  names with inconsistent casing across docs: {inconsistent_casing}")
    log(f"  'peloton'-containing name variants seen: {peloton_variants}")
    entities_in_multiple_docs = {k: v for k, v in name_to_docs.items() if len(v) > 1}
    log(f"  entities appearing in >1 document (exact-name match): {list(entities_in_multiple_docs.keys())}")

    # Full registry: every one of the 56 unique nodes, not just the filtered
    # subsets above — needed to manually review which SHOULD have merged
    # (same real-world entity, different surface string) vs. correctly
    # stayed separate (genuinely different entities that happen to share a
    # word, e.g. "Peloton" the company vs. "Peloton Guide" the product).
    name_to_type = {}
    for t in all_triplets:
        for entity_key in ("source", "target"):
            entity = t[entity_key]
            if entity and entity["name"]:
                name_to_type.setdefault(entity["name"], entity["type"])

    full_registry = sorted(
        (
            {
                "name": name,
                "type": name_to_type.get(name),
                "documents": sorted(docs),
                "doc_count": len(docs),
            }
            for name, docs in name_to_docs.items()
        ),
        key=lambda r: (-r["doc_count"], r["type"] or "", r["name"]),
    )
    log(f"  full node registry ({len(full_registry)} nodes) saved to results JSON.")

    results["task_43_multi_doc_merge"] = {
        "n_docs": len(per_doc_triplets),
        "triplets_per_doc": {f: len(t) for f, t in per_doc_triplets.items()},
        "total_triplets": len(all_triplets),
        "unique_nodes_case_insensitive": total_unique_nodes_by_lowercase,
        "inconsistent_casing_variants": {k: list(v) for k, v in inconsistent_casing.items()},
        "peloton_name_variants": {k: list(v) for k, v in peloton_variants.items()},
        "entities_in_multiple_docs": {k: list(v) for k, v in entities_in_multiple_docs.items()},
        "full_node_registry": full_registry,
        "all_triplets": all_triplets,
    }

    # --- Task 44: truncation/pagination on the densest doc --------------
    log("=== Task 44: truncation check on densest doc ===")
    densest_filename = max(per_doc_triplets, key=lambda f: len(per_doc_triplets[f]))
    densest_id = filename_to_id[densest_filename]
    densest_data = get_relations(densest_id, limit=200)
    log(f"  densest doc: {densest_filename} -> {len(densest_data.relations or [])} triplets at limit=200, "
        f"is_truncated={densest_data.is_truncated}, next_cursor={densest_data.next_cursor}")
    results["task_44_truncation"] = {
        "densest_filename": densest_filename,
        "n_triplets_at_limit_200": len(densest_data.relations or []),
        "is_truncated": densest_data.is_truncated,
        "next_cursor": densest_data.next_cursor,
    }

    # --- Task 45: determinism --------------------------------------------
    log("=== Task 45: determinism check (same doc, twice) ===")
    run_a = get_relations(first_id)
    run_b = get_relations(first_id)
    triplets_a = [triplet_to_dict(t) for t in (run_a.relations or [])]
    triplets_b = [triplet_to_dict(t) for t in (run_b.relations or [])]
    same = triplets_a == triplets_b
    log(f"  run 1: {len(triplets_a)} triplets, run 2: {len(triplets_b)} triplets, identical={same}")
    if not same:
        log(f"  DIFFERS — relations() may not be fully deterministic. Compare saved results for details.")
    results["task_45_determinism"] = {
        "filename": first_filename,
        "n_triplets_run_1": len(triplets_a),
        "n_triplets_run_2": len(triplets_b),
        "identical": same,
        "run_1": triplets_a,
        "run_2": triplets_b,
    }

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2, default=str))
    log(f"Saved full results to {RESULTS_PATH}")

    log("=== SUMMARY ===")
    log(f"41 mapping: {len(filename_to_id)}/{len(docs_needed)} docs mapped to source IDs" + (" — OK" if not missing else " — INCOMPLETE, see above"))
    log(f"42 shape: entity types = {list(entity_types.keys())}, sample predicates = {[p for p, _ in predicates.most_common(5)]}")
    log(f"43 merge: {len(all_triplets)} total triplets, {total_unique_nodes_by_lowercase} unique nodes"
        + (f", {len(inconsistent_casing)} name(s) need case normalization" if inconsistent_casing else ", no casing issues found"))
    log(f"44 truncation: densest doc is_truncated={densest_data.is_truncated}")
    log(f"45 determinism: {'STABLE' if same else 'NOT STABLE — investigate before relying on this endpoint'}")


if __name__ == "__main__":
    main()
