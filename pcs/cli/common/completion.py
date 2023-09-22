from typing import Mapping

from pcs.common.types import StringSequence

SuggestionTree = Mapping[str, "SuggestionTree"]


def has_applicable_environment(environment: Mapping[str, str]) -> bool:
    """
    Check if environment variables for shell command completion are set

    environment -- very likely os.environ
    """
    if not all(
        key in environment
        for key in [
            "COMP_WORDS",
            "COMP_LENGTHS",
            "COMP_CWORD",
            "PCS_AUTO_COMPLETE",
        ]
    ):
        return False
    if environment["PCS_AUTO_COMPLETE"].strip() in ("0", ""):
        return False
    try:
        int(environment["COMP_CWORD"])
    except ValueError:
        return False
    return True


def make_suggestions(
    environment: Mapping[str, str], suggestion_tree: SuggestionTree
) -> str:
    """
    Suggest possible shell command completions

    environment -- very likely os.environ
    suggestion_tree -- {'acl': {'role': {'create': ...}}}...
    """
    if not has_applicable_environment(environment):
        raise EnvironmentError("Environment is not completion ready")

    try:
        typed_word_list = _split_words(
            environment["COMP_WORDS"],
            environment["COMP_LENGTHS"].split(" "),
        )
    except EnvironmentError:
        return ""

    return "\n".join(
        _find_suggestions(
            suggestion_tree, typed_word_list, int(environment["COMP_CWORD"])
        )
    )


def _split_words(joined_words: str, word_lengths: StringSequence) -> list[str]:
    cursor_position = 0
    words_string_len = len(joined_words)
    word_list = []
    for length in word_lengths:
        try:
            next_position = cursor_position + int(length)
        except ValueError as e:
            raise EnvironmentError(
                f"Length of word '{length}' is not digit"
            ) from e
        if next_position > words_string_len:
            raise EnvironmentError(
                "Expected lengths are bigger than word lengths"
            )
        if (
            next_position != words_string_len
            and not joined_words[next_position].isspace()
        ):
            raise EnvironmentError("Words separator is not expected space")

        word_list.append(joined_words[cursor_position:next_position])
        cursor_position = next_position + 1

    if words_string_len > next_position:
        raise EnvironmentError("Expected lengths are smaller then word lengths")

    return word_list


def _find_suggestions(
    suggestion_tree: SuggestionTree,
    typed_word_list: StringSequence,
    word_under_cursor_idx: int,
) -> list[str]:
    if not 1 <= word_under_cursor_idx <= len(typed_word_list):
        return []

    if len(typed_word_list) == word_under_cursor_idx:
        # not started type the last word yet
        word_under_cursor = ""
    else:
        word_under_cursor = typed_word_list[word_under_cursor_idx]

    words_for_current_cursor_position = _get_subcommands(
        suggestion_tree, typed_word_list[1:word_under_cursor_idx]
    )

    return [
        word
        for word in words_for_current_cursor_position
        if word.startswith(word_under_cursor)
    ]


def _get_subcommands(
    suggestion_tree: SuggestionTree, previous_subcommand_list: StringSequence
) -> list[str]:
    subcommand_tree = suggestion_tree
    for subcommand in previous_subcommand_list:
        if subcommand not in subcommand_tree:
            return []
        subcommand_tree = subcommand_tree[subcommand]
    return sorted(list(subcommand_tree.keys()))
