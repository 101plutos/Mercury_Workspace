"""CHIRON — autonomer Curriculum-Learning-Agent.

CLI:
  python -m agents.chiron.main --paper <arxiv-id>
  python -m agents.chiron.main run
  python -m agents.chiron.main import
"""

import argparse
import sys

from . import db, import_yaml, reader, writer

# Hardcoded until Chunk 2 (scheduler.py)
TOPIC = {
    "code": "QF-101",
    "title": "Portfolio-Theorie (Markowitz Mean-Variance)",
    "pillar": "quant",
    "level": 1,
    "description": (
        "Mean-Variance-Optimierung: Rendite als Erwartungswert, Risiko als "
        "Varianz, Diversifikationseffekt über Korrelationen, Efficient "
        "Frontier, Tangency-Portfolio."
    ),
}

SOURCES = [
    {
        "type": "arxiv",
        "ref": "1511.00140",
        "title": "Conditional Value-at-Risk: Theory and Applications",
    }
]


def run_paper(paper_id):
    """End-to-end pipeline for a single arxiv paper via MiniMax M3."""
    print(f"🔍 CHIRON fetching arXiv paper {paper_id}...")

    source = {
        "type": "arxiv",
        "ref": paper_id,
        "title": f"arXiv:{paper_id}",
    }

    synthesis = reader.fetch_and_synthesize(source)
    synthesis["paper_id"] = paper_id

    topic = {
        "code": paper_id,
        "title": synthesis.get("core_insight", paper_id)[:80],
        "pillar": "research",
        "level": 1,
        "description": f"CHIRON walking skeleton note for arXiv {paper_id}",
    }

    result = writer.write_note(topic, synthesis)

    writer.log_jsonl(
        event_type="note_written",
        topic_code=paper_id,
        payload={
            "file_path": result["file_path"],
            "char_count": result["char_count"],
            "source": paper_id,
            "extract_chars": synthesis.get("extract_chars"),
            "model": "MiniMax-M3",
        },
    )

    # Also log to SQLite if DB is available
    try:
        conn = db.get_connection()
        db.init_db(conn)
        conn.close()
        writer.log_event(
            event_type="note_written",
            topic_code=paper_id,
            payload={
                "file_path": result["file_path"],
                "char_count": result["char_count"],
                "source": paper_id,
                "extract_chars": synthesis.get("extract_chars"),
                "model": "MiniMax-M3",
            },
        )
    except Exception as e:
        print(f"⚠️  SQLite log skipped: {e}")

    print(f"✅ CHIRON note written: {result['file_path']}")
    print(f"   Characters: {result['char_count']}")
    print(f"   Core insight: {synthesis.get('core_insight', 'N/A')[:120]}...")
    return result, synthesis


def run():
    conn = db.get_connection()
    db.init_db(conn)
    known = conn.execute(
        "SELECT 1 FROM topics WHERE code = ?", (TOPIC["code"],)
    ).fetchone()
    conn.close()
    if not known:
        print(f"Topic {TOPIC['code']} nicht in DB — erst 'chiron import' ausführen.")
        sys.exit(1)

    synthesis = reader.fetch_and_synthesize(SOURCES[0])
    result = writer.write_note(TOPIC, synthesis)
    writer.log_event(
        event_type="note_written",
        topic_code=TOPIC["code"],
        payload={
            "file_path": result["file_path"],
            "char_count": result["char_count"],
            "source": SOURCES[0]["ref"],
            "extract_chars": synthesis.get("extract_chars"),
        },
    )
    print(f"✅ CHIRON {TOPIC['code']} — Note geschrieben: {result['file_path']}")


def run_import():
    counts = import_yaml.import_curriculum()
    print(
        f"✅ CHIRON import — {counts['topics']} Topics, "
        f"{counts['sources']} Sources (idempotenter Upsert)"
    )


def main():
    parser = argparse.ArgumentParser(prog="chiron")
    parser.add_argument(
        "--paper",
        type=str,
        default=None,
        help="arXiv paper ID (e.g. 2506.12345) to synthesize via MiniMax M3",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Eine Lern-Session ausführen")
    sub.add_parser("import", help="curriculum.yaml -> SQLite (idempotent)")
    args, remaining = parser.parse_known_args()

    if args.paper:
        run_paper(args.paper)
    elif args.command == "run":
        run()
    elif args.command == "import":
        run_import()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()