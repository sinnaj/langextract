# Copyright 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Text tokenization utilities with Unicode support.

This module provides tokenization for text processing, splitting text into
meaningful units (tokens) while preserving exact character positions. It
supports all Unicode scripts and languages through proper grapheme handling.

Key Features:
  - Full Unicode support (Latin, CJK, Arabic, emojis, etc.)
  - Grapheme-aware tokenization (handles multi-codepoint characters)
  - Character position tracking for text alignment
  - Configurable CJK tokenization strategies

Terminology:
  - Token: A meaningful unit of text (word, number, punctuation, or acronym).
  - Grapheme: A user-perceived character, which may consist of multiple
    Unicode code points. Examples: "é" (e + accent), "👨‍👩‍👧‍👦" (family emoji).

Tokenization Behavior:
  - Words: Consecutive letters group together ("hello" → 1 token)
  - Numbers: Consecutive digits group together ("123" → 1 token)
  - Punctuation: Consecutive symbols group together ("?!" → 1 token)
  - Underscores: Treated as punctuation, not word characters ("a_b" → 3 tokens)
  - CJK text: By default, each character is a separate token for precise
    text grounding. Use tokenize_cjk_by_char=False to group them.

Example:
  >>> tokenized = tokenize("Hello, 世界! test_123")
  >>> # Results in tokens: ["Hello", ",", "世", "界", "!", "test", "_", "123"]
"""

from collections.abc import Sequence, Set
import dataclasses
import enum
import functools
import unicodedata

from absl import logging
import regex

from langextract import exceptions


class BaseTokenizerError(exceptions.LangExtractError):
  """Base class for all tokenizer-related errors."""


class InvalidTokenIntervalError(BaseTokenizerError):
  """Error raised when a token interval is invalid or out of range."""


class SentenceRangeError(BaseTokenizerError):
  """Error raised when the start token index for a sentence is out of range."""


@dataclasses.dataclass(slots=True)
class CharInterval:
  """Represents a range of character positions in the original text.

  Attributes:
    start_pos: The starting character index (inclusive).
    end_pos: The ending character index (exclusive).
  """

  start_pos: int
  end_pos: int


@dataclasses.dataclass
class TokenInterval:
  """Represents an interval over tokens in tokenized text.

  The interval is defined by a start index (inclusive) and an end index
  (exclusive).

  Attributes:
    start_index: The index of the first token in the interval.
    end_index: The index one past the last token in the interval.
  """

  start_index: int = 0
  end_index: int = 0


class TokenType(enum.IntEnum):
  """Enumeration of token types produced during tokenization.

  Attributes:
    WORD: Represents an alphabetical word token.
    NUMBER: Represents a numeric token.
    PUNCTUATION: Represents punctuation characters.
    ACRONYM: Represents an acronym or slash-delimited abbreviation.
  """

  WORD = 0
  NUMBER = 1
  PUNCTUATION = 2
  ACRONYM = 3


@dataclasses.dataclass(slots=True)
class Token:
  """Represents a token extracted from text.

  Each token is assigned an index and classified into a type (word, number,
  punctuation, or acronym). The token also records the range of characters
  (its CharInterval) that correspond to the substring from the original text.
  Additionally, it tracks whether it follows a newline.

  Attributes:
    index: The position of the token in the sequence of tokens.
    token_type: The type of the token, as defined by TokenType.
    char_interval: The character interval within the original text that this
      token spans.
    first_token_after_newline: True if the token immediately follows a newline
      or carriage return.
  """

  index: int
  token_type: TokenType
  char_interval: CharInterval = dataclasses.field(
      default_factory=lambda: CharInterval(0, 0)
  )
  first_token_after_newline: bool = False


@dataclasses.dataclass
class TokenizedText:
  """Holds the result of tokenizing a text string.

  Attributes:
    text: The original text that was tokenized.
    tokens: A list of Token objects extracted from the text.
  """

  text: str
  tokens: list[Token] = dataclasses.field(default_factory=list)


_LETTERS_PATTERN = r"\p{L}+"
_DIGITS_PATTERN = r"\p{Nd}+"
_SYMBOLS_PATTERN = r"[^\p{L}\p{Nd}\s]+"
# Slash patterns like "mg/kg" or "DNA/RNA" - letters or digits only
_SLASH_ABBREV_PATTERN = r"(?:\p{L}+(?:/\p{L}+)+|\p{Nd}+(?:/\p{Nd}+)+)"
_REGEX_FLAGS = regex.VERSION1 | regex.UNICODE

_END_OF_SENTENCE_PATTERN = regex.compile(r"[.?!。？！।۔؟]+$", _REGEX_FLAGS)

# Matches emoji families, combining marks, etc. as single units
_GRAPHEME_PATTERN = regex.compile(r"\X", _REGEX_FLAGS)

_WORD_PATTERN = regex.compile(
    rf"(?:{_LETTERS_PATTERN}|{_DIGITS_PATTERN})\Z", _REGEX_FLAGS
)
_DIGITS_ONLY_PATTERN = regex.compile(_DIGITS_PATTERN + r"\Z", _REGEX_FLAGS)
_ACRONYM_ONLY_PATTERN = regex.compile(
    _SLASH_ABBREV_PATTERN + r"\Z", _REGEX_FLAGS
)

_CJK_SCRIPTS_PATTERN = regex.compile(
    r"[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]",
    regex.VERSION1,
)

_LET_OR_DIGIT = regex.compile(r"[\p{L}\p{Nd}]", _REGEX_FLAGS)
_PUNCT_NO_SLASH = regex.compile(r"[^\p{L}\p{Nd}\s/]", _REGEX_FLAGS)

# Known abbreviations that should not count as sentence enders.
# TODO: Consider removing or parameterizing abbreviations
# for multi-language support (e.g., "M.", "Mme." for French).
_KNOWN_ABBREVIATIONS = frozenset({"Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "St."})


def _classify_grapheme(grapheme: str) -> TokenType:
  """Classifies a single grapheme into a token type.

  Args:
    grapheme: A single extended grapheme cluster.

  Returns:
    The TokenType classification.
  """
  if _ACRONYM_ONLY_PATTERN.fullmatch(grapheme):
    return TokenType.ACRONYM
  if _DIGITS_ONLY_PATTERN.fullmatch(grapheme):
    return TokenType.NUMBER
  if _WORD_PATTERN.fullmatch(grapheme):
    return TokenType.WORD
  # Handle combining characters like "é" (e + combining accent) as word tokens
  if any("L" == unicodedata.category(c)[0] for c in grapheme):
    return TokenType.WORD
  return TokenType.PUNCTUATION


def _should_group_token(grapheme: str, tokenize_cjk_by_char: bool) -> bool:
  """Determines if a grapheme should be grouped with similar adjacent graphemes.

  Args:
    grapheme: The grapheme to check.
    tokenize_cjk_by_char: If True, CJK characters are not grouped.

  Returns:
    True if the grapheme should be grouped with adjacent similar graphemes.
  """
  # If we're tokenizing CJK by character and this is a CJK character, don't group
  if tokenize_cjk_by_char and _CJK_SCRIPTS_PATTERN.fullmatch(grapheme):
    return False

  if _LET_OR_DIGIT.match(grapheme):
    return True

  # Don't start a punctuation group if the first grapheme is a slash
  if grapheme == "/":
    return False

  # Slash is handled separately in post-processing
  if _PUNCT_NO_SLASH.match(grapheme):
    return True

  return False


def _merge_slash_patterns(tokens: list[Token], text: str) -> list[Token]:
  """Post-process tokens to merge slash patterns like mg/kg.

  Args:
    tokens: List of tokens to process.
    text: The original text.

  Returns:
    Updated list of tokens with slash patterns merged.
  """
  if len(tokens) < 3:
    return tokens

  merged_tokens = []
  i = 0

  while i < len(tokens):
    if (
        i + 2 < len(tokens)
        and tokens[i].token_type in (TokenType.WORD, TokenType.NUMBER)
        and tokens[i + 1].token_type == TokenType.PUNCTUATION
        and text[
            tokens[i + 1]
            .char_interval.start_pos : tokens[i + 1]
            .char_interval.end_pos
        ]
        == "/"
        and tokens[i + 2].token_type in (TokenType.WORD, TokenType.NUMBER)
    ):

      if (
          tokens[i].char_interval.end_pos
          == tokens[i + 1].char_interval.start_pos
          and tokens[i + 1].char_interval.end_pos
          == tokens[i + 2].char_interval.start_pos
      ):

        combined_start = tokens[i].char_interval.start_pos
        combined_end = tokens[i + 2].char_interval.end_pos
        combined_text = text[combined_start:combined_end]

        if _ACRONYM_ONLY_PATTERN.fullmatch(combined_text):
          merged_token = Token(
              index=len(merged_tokens),
              token_type=TokenType.ACRONYM,
              char_interval=CharInterval(
                  start_pos=combined_start, end_pos=combined_end
              ),
              first_token_after_newline=tokens[i].first_token_after_newline,
          )
          merged_tokens.append(merged_token)
          i += 3  # We merged 3 tokens into 1
          continue

    token = Token(
        index=len(merged_tokens),
        token_type=tokens[i].token_type,
        char_interval=tokens[i].char_interval,
        first_token_after_newline=tokens[i].first_token_after_newline,
    )
    merged_tokens.append(token)
    i += 1

  return merged_tokens


# Cache regex operations for performance
@functools.lru_cache(maxsize=2048)
def _is_letter_sequence(text: str) -> bool:
  """Check if text matches letter pattern."""
  return bool(regex.fullmatch(r"\p{L}+", text, _REGEX_FLAGS))


@functools.lru_cache(maxsize=2048)
def _is_single_letter(text: str) -> bool:
  """Check if text is a single letter."""
  return bool(regex.fullmatch(r"\p{L}", text, _REGEX_FLAGS))


@functools.lru_cache(maxsize=2048)
def _is_digit_sequence(text: str) -> bool:
  """Check if text matches digit pattern."""
  return bool(regex.fullmatch(r"\p{Nd}+", text, _REGEX_FLAGS))


@functools.lru_cache(maxsize=2048)
def _is_single_digit(text: str) -> bool:
  """Check if text is a single digit."""
  return bool(regex.fullmatch(r"\p{Nd}", text, _REGEX_FLAGS))


@functools.lru_cache(maxsize=2048)
def _is_punct_sequence(text: str) -> bool:
  """Check if text matches punctuation pattern."""
  return bool(regex.fullmatch(r"[^\p{L}\p{Nd}\s]+", text, _REGEX_FLAGS))


@functools.lru_cache(maxsize=2048)
def _is_single_punct(text: str) -> bool:
  """Check if text is a single punctuation character."""
  return bool(regex.fullmatch(r"[^\p{L}\p{Nd}\s]", text, _REGEX_FLAGS))


def tokenize(text: str, tokenize_cjk_by_char: bool = True) -> TokenizedText:
  """Splits text into tokens (words, digits, or punctuation).

  Each token is annotated with its character position and type (WORD or
  PUNCTUATION). If there is a newline or carriage return in the gap before
  a token, that token's `first_token_after_newline` is set to True.

  Grouping Logic:
  The tokenizer scans ahead from each grapheme to group similar types:

  Text:     "Hello123 世界! test_case"
            ↓ ↓ ↓ ↓ ↓   ↓ ↓↓  ↓ ↓ ↓ ↓ ↓ ↓
  Process:  [Hello][123] [世][界][!] [test][_][case]
            └─┬──┘ └┬─┘  └┬┘ └┬┘ └┘  └─┬─┘ └┘ └─┬─┘
           Letters│   CJK│ CJK│Punct Letters│ Letters
                 Digits  │    │            Punct

  Rules:
  - Groups consecutive letters (same script)
  - Groups consecutive digits
  - Groups consecutive punctuation (except slash)
  - CJK characters are kept separate when tokenize_cjk_by_char=True
  - Underscores emit as punctuation tokens

  Args:
    text: The text to tokenize.
    tokenize_cjk_by_char: If True (default), splits CJK scripts character by
      character for precise grounding. If False, groups continuous CJK runs
      into single tokens.

  Returns:
    A TokenizedText object containing all extracted tokens.
  """
  logging.debug(
      "Entering tokenize() with text length: %d characters", len(text)
  )
  tokens = []
  next_token_index = 0
  last_end_pos = 0
  pending_newline = (
      False  # Track if next token should be marked as after newline
  )

  grapheme_iter = _GRAPHEME_PATTERN.finditer(text)
  grapheme_buffer = []

  def peek_grapheme(n=0):
    while len(grapheme_buffer) <= n:
      try:
        grapheme_buffer.append(next(grapheme_iter))
      except StopIteration:
        return None
    return grapheme_buffer[n]

  while True:
    if grapheme_buffer:
      match = grapheme_buffer.pop(0)
    else:
      match = peek_grapheme(0)
      if match is None:
        break
      grapheme_buffer.pop(0)

    start_pos, end_pos = match.span()
    grapheme = match.group()

    has_newline = pending_newline
    if last_end_pos < start_pos:
      gap = text[last_end_pos:start_pos]
      if "\n" in gap or "\r" in gap:
        has_newline = True
    pending_newline = False

    # Skip whitespace graphemes but track if they contain newlines
    if grapheme.isspace():
      if "\n" in grapheme or "\r" in grapheme:
        # The next non-whitespace token should be marked as first after newline
        pending_newline = True
      last_end_pos = end_pos
      continue

    # Handle underscores as punctuation
    if grapheme == "_":
      token = Token(
          index=next_token_index,
          token_type=TokenType.PUNCTUATION,
          char_interval=CharInterval(start_pos=start_pos, end_pos=end_pos),
          first_token_after_newline=has_newline,
      )
      tokens.append(token)
      next_token_index += 1
      last_end_pos = end_pos
      continue

    if _should_group_token(grapheme, tokenize_cjk_by_char):
      group_start = start_pos
      group_end = end_pos
      group_parts = [grapheme]

      j = 0
      while True:
        next_match = peek_grapheme(j)
        if next_match is None:
          break
        next_start, next_end = next_match.span()
        next_grapheme = next_match.group()

        if next_start > group_end:
          gap = text[group_end:next_start]
          if gap and not gap.isspace():
            break

        # For CJK tokenization, don't group CJK characters
        if tokenize_cjk_by_char and _CJK_SCRIPTS_PATTERN.fullmatch(
            next_grapheme
        ):
          break

        # Use same-type grouping to avoid mixing scripts/types
        valid_group = False

        current_group = text[group_start:group_end]
        if _is_letter_sequence(current_group):
          if _is_single_letter(next_grapheme):
            valid_group = True
        elif _is_digit_sequence(current_group):
          if _is_single_digit(next_grapheme):
            valid_group = True
        elif _is_punct_sequence(current_group):
          if _is_single_punct(next_grapheme):
            # Slash patterns handled separately in post-processing
            if "/" not in current_group and next_grapheme != "/":
              valid_group = True

        if not valid_group:
          potential_group = text[group_start:next_end]
          if _ACRONYM_ONLY_PATTERN.fullmatch(potential_group):
            valid_group = True

        if valid_group:
          group_end = next_end
          group_parts.append(next_grapheme)
          j += 1
        else:
          break

      grouped_text = text[group_start:group_end]
      token_type = _classify_grapheme(grouped_text)

      token = Token(
          index=next_token_index,
          token_type=token_type,
          char_interval=CharInterval(start_pos=group_start, end_pos=group_end),
          first_token_after_newline=has_newline,
      )
      tokens.append(token)
      next_token_index += 1
      last_end_pos = group_end
      for _ in range(j):
        if grapheme_buffer:
          grapheme_buffer.pop(0)
    else:
      # Single grapheme token
      token_type = _classify_grapheme(grapheme)

      token = Token(
          index=next_token_index,
          token_type=token_type,
          char_interval=CharInterval(start_pos=start_pos, end_pos=end_pos),
          first_token_after_newline=has_newline,
      )
      tokens.append(token)
      next_token_index += 1
      last_end_pos = end_pos

  tokens = _merge_slash_patterns(tokens, text)

  logging.debug("Completed tokenize(). Total tokens: %d", len(tokens))
  return TokenizedText(text=text, tokens=tokens)


def tokens_text(
    tokenized_text: TokenizedText,
    token_interval: TokenInterval,
) -> str:
  """Reconstructs text substring for a given token interval.

  Args:
    tokenized_text: A TokenizedText object containing token data.
    token_interval: The interval specifying the range [start_index, end_index)
      of tokens.

  Returns:
    The exact substring of the original text corresponding to the token
    interval.

  Raises:
    InvalidTokenIntervalError: If the token_interval is invalid or out of range.
  """
  if (
      token_interval.start_index < 0
      or token_interval.end_index > len(tokenized_text.tokens)
      or token_interval.start_index >= token_interval.end_index
  ):

    raise InvalidTokenIntervalError(
        f"Invalid token interval. start_index={token_interval.start_index}, "
        f"end_index={token_interval.end_index}, "
        f"total_tokens={len(tokenized_text.tokens)}."
    )

  start_token = tokenized_text.tokens[token_interval.start_index]
  end_token = tokenized_text.tokens[token_interval.end_index - 1]
  return tokenized_text.text[
      start_token.char_interval.start_pos : end_token.char_interval.end_pos
  ]


def _is_end_of_sentence_token(
    text: str,
    tokens: Sequence[Token],
    current_idx: int,
    known_abbreviations: Set[str],
) -> bool:
  """Checks if the punctuation token at `current_idx` ends a sentence.

  A token is considered a sentence terminator and is not part of a known
  abbreviation. Only searches the text corresponding to the current token.

  Args:
    text: The entire input text.
    tokens: The sequence of Token objects.
    current_idx: The current token index to check.
    known_abbreviations: Abbreviations that should not count as sentence enders
      (e.g., "Dr.").

  Returns:
    True if the token at `current_idx` ends a sentence, otherwise False.
  """
  current_token_text = text[
      tokens[current_idx]
      .char_interval.start_pos : tokens[current_idx]
      .char_interval.end_pos
  ]
  if _END_OF_SENTENCE_PATTERN.search(current_token_text):
    if current_idx > 0:
      prev_token_text = text[
          tokens[current_idx - 1]
          .char_interval.start_pos : tokens[current_idx - 1]
          .char_interval.end_pos
      ]
      if f"{prev_token_text}{current_token_text}" in known_abbreviations:
        return False
    return True
  return False


def _starts_with_cased_or_caseless_letter(token_text: str) -> bool:
  """Checks whether token_text starts with a letter that can begin a sentence.

  A sentence-start letter is either:
  - An uppercase letter in a script that has case (e.g. Latin, Cyrillic, Greek).
  - Any letter from a script with no case distinction (e.g. Han, Hiragana,
    Hangul).  This allows the newline-plus-capital heuristic to work for
    caseless scripts.

  Args:
    token_text: The text to test. May be empty.

  Returns:
    True if the first character matches the criteria above; otherwise False.
  """
  if not token_text:
    return False
  ch = token_text[0]
  if unicodedata.category(ch) in ("Lu", "Lt"):
    return True
  if ch.isupper():
    return True
  # Caseless scripts (e.g., CJK, Thai) can start sentences
  if ch.lower() == ch.upper() and unicodedata.category(ch).startswith("L"):
    return True
  return False


def _is_sentence_break_after_newline(
    text: str,
    tokens: Sequence[Token],
    current_idx: int,
) -> bool:
  """Checks for sentence break at newline followed by uppercase letter.

  This is a heuristic for determining sentence boundaries. It favors terminating
  a sentence prematurely over missing a sentence boundary, and will terminate a
  sentence early if the first line ends with new line and the second line begins
  with a capital letter.

  Note: This heuristic works best for Latin-script languages. For scripts without
  case distinction (e.g., Thai, Lao, Khmer), the function allows any letter after
  a newline to trigger a sentence break, which may cause over-segmentation.

  Args:
    text: The entire input text.
    tokens: The sequence of Token objects.
    current_idx: The current token index.

  Returns:
    True if a newline or carriage return is found between current_idx and
    current_idx+1, and the next token (if any) begins with an uppercase character.
  """
  if current_idx + 1 >= len(tokens):
    return False

  gap_text = text[
      tokens[current_idx]
      .char_interval.end_pos : tokens[current_idx + 1]
      .char_interval.start_pos
  ]
  if "\n" not in gap_text and "\r" not in gap_text:
    return False

  next_token_text = text[
      tokens[current_idx + 1]
      .char_interval.start_pos : tokens[current_idx + 1]
      .char_interval.end_pos
  ]
  return _starts_with_cased_or_caseless_letter(next_token_text)


def find_sentence_range(
    text: str,
    tokens: Sequence[Token],
    start_token_index: int,
    abbreviations: Set[str] | None = None,
) -> TokenInterval:
  """Finds a 'sentence' interval from a given start index.

  Sentence boundaries are defined by:
    - punctuation tokens in _END_OF_SENTENCE_PATTERN
    - newline breaks followed by an uppercase letter
    - not abbreviations in the provided set (e.g., "Dr.")

  This favors terminating a sentence prematurely over missing a sentence
  boundary, and will terminate a sentence early if the first line ends with new
  line and the second line begins with a capital letter.

  Args:
    text: The original text.
    tokens: The tokens that make up `text`.
    start_token_index: The token index from which to begin the sentence.
    abbreviations: Optional set of abbreviations that should not be treated as
      sentence boundaries. If None, uses default English abbreviations.

  Returns:
    A TokenInterval representing the sentence range [start_token_index, end). If
    no sentence boundary is found, the end index will be the length of
    `tokens`.

  Raises:
    SentenceRangeError: If `start_token_index` is out of range.
  """
  if start_token_index < 0 or start_token_index >= len(tokens):
    raise SentenceRangeError(
        f"start_token_index={start_token_index} out of range. "
        f"Total tokens: {len(tokens)}."
    )

  abbrev_set = (
      abbreviations if abbreviations is not None else _KNOWN_ABBREVIATIONS
  )

  i = start_token_index
  while i < len(tokens):
    if tokens[i].token_type == TokenType.PUNCTUATION:
      if _is_end_of_sentence_token(text, tokens, i, abbrev_set):
        return TokenInterval(start_index=start_token_index, end_index=i + 1)
    if _is_sentence_break_after_newline(text, tokens, i):
      return TokenInterval(start_index=start_token_index, end_index=i + 1)
    i += 1

  return TokenInterval(start_index=start_token_index, end_index=len(tokens))
