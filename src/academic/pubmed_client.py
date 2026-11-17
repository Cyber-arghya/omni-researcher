"""PubMed NCBI Entrez e-utilities client for biomedical literature search."""

import logging

import httpx

from src.config import settings
from src.state.schemas import SearchResult

logger = logging.getLogger(__name__)

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


class PubMedClient:
    """Async client for searching PubMed and biomedical literature."""

    def __init__(self) -> None:
        self.email = settings.ncbi_pubmed_email
        self.api_key = settings.ncbi_pubmed_api_key

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Search PubMed and retrieve summary metadata."""
        params: dict[str, str | int] = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Step 1: ESearch to find PMIDs
                search_resp = await client.get(PUBMED_ESEARCH_URL, params=params)
                if search_resp.status_code != 200:
                    return []

                search_data = search_resp.json()
                id_list = search_data.get("esearchresult", {}).get("idlist", [])
                if not id_list:
                    return []

                # Step 2: ESummary to get paper titles & source info
                summary_params: dict[str, str] = {
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "json",
                }
                if self.api_key:
                    summary_params["api_key"] = self.api_key

                summary_resp = await client.get(PUBMED_ESUMMARY_URL, params=summary_params)
                if summary_resp.status_code != 200:
                    return []

                summary_data = summary_resp.json()
                results_dict = summary_data.get("result", {})

                results: list[SearchResult] = []
                for pmid in id_list:
                    doc = results_dict.get(pmid)
                    if not doc:
                        continue

                    title = doc.get("title", "Untitled")
                    source = doc.get("source", "")
                    pubdate = doc.get("pubdate", "")
                    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

                    snippet = f"Journal: {source} ({pubdate}). PMID: {pmid}"
                    results.append(
                        SearchResult(
                            title=f"[PubMed] {title}",
                            url=url,
                            snippet=snippet,
                            source_engine="pubmed",
                        )
                    )

                return results

        except Exception as e:
            logger.debug("PubMed search error for '%s': %s", query, str(e))
            return []
