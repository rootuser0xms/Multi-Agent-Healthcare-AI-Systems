from tools.pubmed_tool import search_pubmed
from tools.audit_log import log_action

class ResearchAgent:
    """
    Agent 1: looks up recent, real medical literature via PubMed.
    Scope: read-only access to PubMed's public API. No patient data,
    no other agent's tools
    """

    def __init__(self, name="ResearchAgent"):
        self.name = name

    def handle(self, query, max_results=50):
        """
        Given a natural-language research query, fetch real PubMed articles.
        Returns a structured result dict - this is what an orchestrator
        or another agent would receive back.
        """
        log_action(self.name, "search_pubmed", {"query": query, "max_results": max_results})

        articles = search_pubmed(query, max_results=max_results)

        result = {
            "query": query,
            "num_results": len(articles),
            "articles": articles,
        }

        log_action(
            self.name, "search_pubmed_complete",
            {"query": query},
            result_summary=f"{len(articles)} articles found"
        )

        return result


if __name__ == "__main__":
    agent = ResearchAgent()
    result = agent.handle("agentic AI clinical decision support", max_results=50)

    print(f"Query: {result['query']}")
    print(f"Found {result['num_results']} articles:\n")
    for a in result["articles"]:
        print(f"- {a['title']} ({a['pubdate']}, {a['journal']}) — {a['url']}")