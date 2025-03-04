from exa_py import Exa
import os

def get_relevant_github_repository_content(query: str):
    exa = Exa(api_key=os.getenv("EXA_API_KEY"))

    results = exa.search_and_contents(
        query,
        text = True,
        category = "github",
        subpages = 1,
        subpage_target = "README",
        num_results = 4
    )

    formatted_results = "\n\n".join(
        f"Website {i+1}: {result.url}\n{result.text}\n{result.subpages[0]["title"]}\n{result.subpages[0]["text"]}"
        for i, result in enumerate(results.results)
    )

    return formatted_results
