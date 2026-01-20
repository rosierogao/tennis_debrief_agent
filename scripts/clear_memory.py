from __future__ import annotations

from google.cloud import firestore


def main() -> None:
    client = firestore.Client()
    matches_ref = client.collection("matches")

    deleted = 0
    for doc in matches_ref.stream():
        doc.reference.delete()
        deleted += 1

    print(f"Deleted {deleted} match record(s).")


if __name__ == "__main__":
    main()
