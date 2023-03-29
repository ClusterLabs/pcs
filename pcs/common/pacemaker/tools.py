def is_negative_score(score: str) -> bool:
    return score.startswith("-")


def abs_score(score: str) -> str:
    """
    return absolute value of score
    """
    if is_negative_score(score):
        return score[1:]
    return score
