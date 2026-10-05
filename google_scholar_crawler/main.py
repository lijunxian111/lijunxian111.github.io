from scholarly import scholarly, ProxyGenerator
import json
from datetime import datetime, timezone
import os
import sys
import signal


SCHOLAR_ID = os.environ["GOOGLE_SCHOLAR_ID"]


def timeout_handler(signum, frame):
    raise TimeoutError("Google Scholar request timed out.")


# Prevent GitHub Actions from hanging for hours.
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(15 * 60)  # 15-minute hard timeout


def setup_proxy():
    """
    Try to use a free proxy.

    Google Scholar frequently blocks GitHub Actions IPs.
    If no working free proxy is found, fall back to direct access.
    """
    try:
        print("Trying to configure a free proxy...")
        pg = ProxyGenerator()

        if pg.FreeProxies():
            scholarly.use_proxy(pg, pg)
            print("Free proxy configured successfully.")
        else:
            print("No working free proxy found. Falling back to direct access.")

    except Exception as e:
        print(f"Proxy setup failed: {e}")
        print("Falling back to direct access.")


def main():
    setup_proxy()

    print(f"Fetching Google Scholar profile: {SCHOLAR_ID}")

    try:
        author = scholarly.search_author_id(SCHOLAR_ID)

        if not author:
            raise RuntimeError("Google Scholar returned an empty author profile.")

        print("Author profile found. Fetching citation data...")

        author = scholarly.fill(
            author,
            sections=["basics", "indices", "counts", "publications"]
        )

        if "name" not in author:
            raise RuntimeError(
                "Invalid Google Scholar response. "
                "The request may have been blocked."
            )

        print(f"Author: {author['name']}")
        print(f"Total citations: {author.get('citedby', 'unknown')}")

        author["updated"] = datetime.now(timezone.utc).isoformat()

        publications = author.get("publications", [])

        author["publications"] = {
            v["author_pub_id"]: v
            for v in publications
            if "author_pub_id" in v
        }

        os.makedirs("results", exist_ok=True)

        # Complete Scholar data
        with open(
            "results/gs_data.json",
            "w",
            encoding="utf-8"
        ) as outfile:
            json.dump(
                author,
                outfile,
                ensure_ascii=False,
                indent=2
            )

        # Total citation badge
        shieldio_data = {
            "schemaVersion": 1,
            "label": "citations",
            "message": str(author.get("citedby", 0)),
        }

        with open(
            "results/gs_data_shieldsio.json",
            "w",
            encoding="utf-8"
        ) as outfile:
            json.dump(
                shieldio_data,
                outfile,
                ensure_ascii=False
            )

        # Citation badge for every publication
        for pub_id, info in author["publications"].items():

            pub_data = {
                "schemaVersion": 1,
                "label": "citations",
                "message": str(info.get("num_citations", 0)),
            }

            filename = f"results/{pub_id}_shieldsio.json"

            with open(
                filename,
                "w",
                encoding="utf-8"
            ) as outfile:
                json.dump(
                    pub_data,
                    outfile,
                    ensure_ascii=False
                )

        print(
            f"Successfully generated citation data for "
            f"{len(author['publications'])} publications."
        )

    except TimeoutError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(
            f"ERROR: Failed to fetch Google Scholar data: "
            f"{type(e).__name__}: {e}",
            file=sys.stderr
        )
        sys.exit(1)

    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
