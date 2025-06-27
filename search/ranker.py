def rank_results(results):
    """
    Rank search results in decreasing order of relevance (score).
    Args:
        results (list): List of result dicts, each with a 'score' key.
    Returns:
        List of ranked results.
    """
    return sorted(results, key=lambda x: x.get('score', 0), reverse=True)
