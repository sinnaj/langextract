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

import textwrap

from absl.testing import absltest
from absl.testing import parameterized

from langextract import tokenizer

WORD = tokenizer.TokenType.WORD
NUMBER = tokenizer.TokenType.NUMBER
PUNCTUATION = tokenizer.TokenType.PUNCTUATION
ACRONYM = tokenizer.TokenType.ACRONYM


class TokenizerTest(parameterized.TestCase):

  def assertTokenListEqual(self, actual_tokens, expected_tokens, msg=None):
    """Assert that token lists match in structure (excluding char_interval)."""
    self.assertLen(actual_tokens, len(expected_tokens), msg=msg)
    for i, (expected, actual) in enumerate(zip(expected_tokens, actual_tokens)):
      expected = tokenizer.Token(
          index=expected.index,
          token_type=expected.token_type,
          first_token_after_newline=expected.first_token_after_newline,
      )
      actual = tokenizer.Token(
          index=actual.index,
          token_type=actual.token_type,
          first_token_after_newline=actual.first_token_after_newline,
      )
      self.assertDataclassEqual(
          expected,
          actual,
          msg=f"Token mismatch at index {i}",
      )

  def assertTokenCharIntervalsValid(
      self, text: str, tokens: list[tokenizer.Token]
  ):
    """Assert that all token char_intervals correctly extract text."""
    for i, token in enumerate(tokens):
      self.assertIsNotNone(
          token.char_interval, f"Token {i} has None char_interval"
      )
      start = token.char_interval.start_pos
      end = token.char_interval.end_pos
      self.assertGreaterEqual(
          start, 0, f"Token {i} has negative start position: {start}"
      )
      self.assertLessEqual(
          end,
          len(text),
          f"Token {i} end position {end} exceeds text length {len(text)}",
      )
      self.assertLess(
          start,
          end,
          f"Token {i} has invalid interval: start={start}, end={end}",
      )

  def assertTokenTextMatches(
      self, text: str, token: tokenizer.Token, expected_text: str
  ):
    """Assert that a token's char_interval extracts the expected text."""
    actual_text = text[
        token.char_interval.start_pos : token.char_interval.end_pos
    ]
    self.assertEqual(
        actual_text,
        expected_text,
        f"Token text mismatch: expected '{expected_text}', got '{actual_text}'"
        " from interval"
        f" [{token.char_interval.start_pos}:{token.char_interval.end_pos}]",
    )

  @parameterized.named_parameters(
      dict(
          testcase_name="basic_text",
          input_text="Hello, world!",
          expected_tokens=[
              tokenizer.Token(index=0, token_type=tokenizer.TokenType.WORD),
              tokenizer.Token(
                  index=1, token_type=tokenizer.TokenType.PUNCTUATION
              ),
              tokenizer.Token(index=2, token_type=tokenizer.TokenType.WORD),
              tokenizer.Token(
                  index=3, token_type=tokenizer.TokenType.PUNCTUATION
              ),
          ],
      ),
      dict(
          testcase_name="multiple_spaces_and_numbers",
          input_text="Age:   25\nWeight=70kg.",
          expected_tokens=[
              tokenizer.Token(index=0, token_type=tokenizer.TokenType.WORD),
              tokenizer.Token(
                  index=1, token_type=tokenizer.TokenType.PUNCTUATION
              ),
              tokenizer.Token(index=2, token_type=tokenizer.TokenType.NUMBER),
              tokenizer.Token(
                  index=3,
                  token_type=tokenizer.TokenType.WORD,
                  first_token_after_newline=True,
              ),
              tokenizer.Token(
                  index=4, token_type=tokenizer.TokenType.PUNCTUATION
              ),
              tokenizer.Token(index=5, token_type=tokenizer.TokenType.NUMBER),
              tokenizer.Token(index=6, token_type=tokenizer.TokenType.WORD),
              tokenizer.Token(
                  index=7, token_type=tokenizer.TokenType.PUNCTUATION
              ),
          ],
      ),
      dict(
          testcase_name="multi_line_input",
          input_text="Line1\nLine2\nLine3",
          expected_tokens=[
              tokenizer.Token(index=0, token_type=tokenizer.TokenType.WORD),
              tokenizer.Token(index=1, token_type=tokenizer.TokenType.NUMBER),
              tokenizer.Token(
                  index=2,
                  token_type=tokenizer.TokenType.WORD,
                  first_token_after_newline=True,
              ),
              tokenizer.Token(index=3, token_type=tokenizer.TokenType.NUMBER),
              tokenizer.Token(
                  index=4,
                  token_type=tokenizer.TokenType.WORD,
                  first_token_after_newline=True,
              ),
              tokenizer.Token(index=5, token_type=tokenizer.TokenType.NUMBER),
          ],
      ),
      dict(
          testcase_name="crlf_line_endings",
          input_text="Line1\r\nLine2\r\nLine3",
          expected_tokens=[
              tokenizer.Token(index=0, token_type=tokenizer.TokenType.WORD),
              tokenizer.Token(index=1, token_type=tokenizer.TokenType.NUMBER),
              tokenizer.Token(
                  index=2,
                  token_type=tokenizer.TokenType.WORD,
                  first_token_after_newline=True,
              ),
              tokenizer.Token(index=3, token_type=tokenizer.TokenType.NUMBER),
              tokenizer.Token(
                  index=4,
                  token_type=tokenizer.TokenType.WORD,
                  first_token_after_newline=True,
              ),
              tokenizer.Token(index=5, token_type=tokenizer.TokenType.NUMBER),
          ],
      ),
      dict(
          testcase_name="only_symbols",
          input_text="!!!@#   $$$%",
          expected_tokens=[
              tokenizer.Token(
                  index=0, token_type=tokenizer.TokenType.PUNCTUATION
              ),
              tokenizer.Token(
                  index=1, token_type=tokenizer.TokenType.PUNCTUATION
              ),
          ],
      ),
      dict(
          testcase_name="empty_string",
          input_text="",
          expected_tokens=[],
      ),
  )
  def test_tokenize_various_inputs(self, input_text, expected_tokens):
    tokenized = tokenizer.tokenize(input_text)
    self.assertTokenListEqual(
        tokenized.tokens,
        expected_tokens,
        msg=f"Tokens mismatch for input: {input_text!r}",
    )
    self.assertTokenCharIntervalsValid(input_text, tokenized.tokens)

  def test_first_token_after_newline_flag(self):
    input_text = "Line1\nLine2\nLine3"
    tokenized = tokenizer.tokenize(input_text)

    expected_tokens = [
        tokenizer.Token(
            index=0,
            token_type=tokenizer.TokenType.WORD,
        ),
        tokenizer.Token(
            index=1,
            token_type=tokenizer.TokenType.NUMBER,
        ),
        tokenizer.Token(
            index=2,
            token_type=tokenizer.TokenType.WORD,
            first_token_after_newline=True,
        ),
        tokenizer.Token(
            index=3,
            token_type=tokenizer.TokenType.NUMBER,
        ),
        tokenizer.Token(
            index=4,
            token_type=tokenizer.TokenType.WORD,
            first_token_after_newline=True,
        ),
        tokenizer.Token(
            index=5,
            token_type=tokenizer.TokenType.NUMBER,
        ),
    ]

    self.assertTokenListEqual(
        tokenized.tokens,
        expected_tokens,
        msg="Newline flags mismatch",
    )


class TokensTextTest(parameterized.TestCase):

  _SENTENCE_WITH_ONE_LINE = "Patient Jane Doe, ID 67890, received 10mg daily."

  @parameterized.named_parameters(
      dict(
          testcase_name="substring_jane_doe",
          input_text=_SENTENCE_WITH_ONE_LINE,
          start_index=1,
          end_index=3,
          expected_substring="Jane Doe",
      ),
      dict(
          testcase_name="substring_with_punctuation",
          input_text=_SENTENCE_WITH_ONE_LINE,
          start_index=0,
          end_index=4,
          expected_substring="Patient Jane Doe,",
      ),
      dict(
          testcase_name="numeric_tokens",
          input_text=_SENTENCE_WITH_ONE_LINE,
          start_index=5,
          end_index=6,
          expected_substring="67890",
      ),
  )
  def test_valid_intervals(
      self, input_text, start_index, end_index, expected_substring
  ):
    input_tokenized = tokenizer.tokenize(input_text)
    interval = tokenizer.TokenInterval(
        start_index=start_index, end_index=end_index
    )
    result_str = tokenizer.tokens_text(input_tokenized, interval)
    self.assertEqual(
        result_str,
        expected_substring,
        msg=f"Wrong substring for interval {start_index}..{end_index}",
    )

  @parameterized.named_parameters(
      dict(
          testcase_name="start_index_negative",
          input_text=_SENTENCE_WITH_ONE_LINE,
          start_index=-1,
          end_index=2,
      ),
      dict(
          testcase_name="end_index_out_of_bounds",
          input_text=_SENTENCE_WITH_ONE_LINE,
          start_index=0,
          end_index=999,
      ),
      dict(
          testcase_name="start_index_ge_end_index",
          input_text=_SENTENCE_WITH_ONE_LINE,
          start_index=4,
          end_index=4,
      ),
  )
  def test_invalid_intervals(self, input_text, start_index, end_index):
    input_tokenized = tokenizer.tokenize(input_text)
    interval = tokenizer.TokenInterval(
        start_index=start_index, end_index=end_index
    )
    with self.assertRaises(tokenizer.InvalidTokenIntervalError):
      _ = tokenizer.tokens_text(input_tokenized, interval)


class SentenceRangeTest(parameterized.TestCase):

  @parameterized.named_parameters(
      dict(
          testcase_name="simple_sentence",
          input_text="This is one sentence. Then another?",
          start_pos=0,
          expected_interval=(0, 5),
      ),
      dict(
          testcase_name="abbreviation_not_boundary",
          input_text="Dr. John visited. Then left.",
          start_pos=0,
          expected_interval=(0, 5),
      ),
      dict(
          testcase_name="second_line_capital_letter_terminates_sentence",
          input_text=textwrap.dedent("""\
              Blood pressure was 160/90 and patient was recommended to
              Atenolol 50 mg daily."""),
          start_pos=0,
          expected_interval=(0, 9),
      ),
      # Multi-language sentence boundary tests
      dict(
          testcase_name="japanese_cjk_period_first_sentence",
          input_text="これは文です。次の文です。",  # "This is a sentence. Next sentence."
          start_pos=0,
          expected_interval=(0, 2),
      ),
      dict(
          testcase_name="japanese_cjk_period_second_sentence",
          input_text="これは文です。次の文です。",  # "This is a sentence. Next sentence."
          start_pos=2,  # Start of the second sentence
          expected_interval=(2, 4),
      ),
      dict(
          testcase_name="arabic_question_mark",
          input_text="كيف حالك؟ أنا بخير.",  # "How are you? I am fine."
          start_pos=0,
          expected_interval=(0, 3),
      ),
      dict(
          testcase_name="greek_uppercase_after_newline_triggers_sentence_break",
          input_text="line one\nΣ line two",  # Σ = Greek capital letter Sigma
          start_pos=0,
          expected_interval=(0, 2),
      ),
      dict(
          testcase_name="crlf_uppercase_after_newline_triggers_sentence_break",
          input_text="line one\r\nLine two",  # Windows CRLF line ending
          start_pos=0,
          expected_interval=(0, 2),
      ),
  )
  def test_partial_sentence_range(
      self, input_text, start_pos, expected_interval
  ):
    # Use tokenize_cjk_by_char=False for consistent sentence boundaries
    tokenized = tokenizer.tokenize(input_text, tokenize_cjk_by_char=False)
    tokens = tokenized.tokens

    interval = tokenizer.find_sentence_range(input_text, tokens, start_pos)
    expected_start, expected_end = expected_interval
    self.assertEqual(interval.start_index, expected_start)
    self.assertEqual(interval.end_index, expected_end)

  @parameterized.named_parameters(
      dict(
          testcase_name="end_of_text",
          input_text="Only one sentence here",
          start_pos=0,
      ),
  )
  def test_full_sentence_range(self, input_text, start_pos):
    tokenized = tokenizer.tokenize(input_text)
    tokens = tokenized.tokens

    interval = tokenizer.find_sentence_range(input_text, tokens, start_pos)
    self.assertEqual(interval.start_index, 0)
    self.assertLen(
        tokens,
        interval.end_index,
        "Expected sentence to end at last token, but got"
        f" {interval.end_index} vs {len(tokens)} tokens",
    )

  @parameterized.named_parameters(
      dict(
          testcase_name="out_of_range_negative_start",
          input_text="Hello world.",
          start_pos=-1,
      ),
      dict(
          testcase_name="out_of_range_exceeding_length",
          input_text="Hello world.",
          start_pos=999,
      ),
  )
  def test_invalid_start_pos(self, input_text, start_pos):
    tokenized = tokenizer.tokenize(input_text)
    tokens = tokenized.tokens
    with self.assertRaises(tokenizer.SentenceRangeError):
      tokenizer.find_sentence_range(input_text, tokens, start_pos)

  def test_custom_abbreviations(self):
    """Test that custom abbreviations parameter works correctly."""
    # Test with French abbreviation
    text = "M. Dupont arrived. Then left."
    tokenized = tokenizer.tokenize(text)
    tokens = tokenized.tokens

    # Default behavior - M. is not in English abbreviations, so sentence ends
    default_range = tokenizer.find_sentence_range(text, tokens, 0)
    self.assertEqual(default_range.start_index, 0)
    self.assertEqual(default_range.end_index, 2)  # Ends at "M."

    # With French abbreviations - M. is an abbreviation, sentence continues
    french_abbrevs = {"M.", "Mme.", "Mlle.", "Dr."}
    french_range = tokenizer.find_sentence_range(
        text, tokens, 0, abbreviations=french_abbrevs
    )
    self.assertEqual(french_range.start_index, 0)
    self.assertEqual(french_range.end_index, 5)  # Ends at "arrived."

    # With empty abbreviations - all periods are sentence boundaries
    no_abbrev_range = tokenizer.find_sentence_range(
        text, tokens, 0, abbreviations=frozenset()
    )
    self.assertEqual(no_abbrev_range.start_index, 0)
    self.assertEqual(no_abbrev_range.end_index, 2)  # Ends at "M."


class MultiLanguageTokenizerTest(parameterized.TestCase):
  """Test default tokenization for various languages, scripts, and emojis.

  Note: Tests use the default character-by-character CJK tokenization.

  Documentation pattern: All non-English test text includes inline comments
  with English translations for better readability and understanding.
  """

  @parameterized.named_parameters(
      dict(
          testcase_name="japanese_with_latin_dosage",
          input_text="患者は毎日10mgを服用します。",  # "The patient takes 10mg daily."
          expected_tokens=[
              ("患", WORD),
              ("者", WORD),
              ("は", WORD),
              ("毎", WORD),
              ("日", WORD),
              ("10", NUMBER),
              ("mg", WORD),
              ("を", WORD),
              ("服", WORD),
              ("用", WORD),
              ("し", WORD),
              ("ま", WORD),
              ("す", WORD),
              ("。", PUNCTUATION),
          ],
      ),
      dict(
          testcase_name="chinese_with_numbers",
          input_text="病人每天服用10毫克。",  # "The patient takes 10 milligrams daily."
          expected_tokens=[
              ("病", WORD),
              ("人", WORD),
              ("每", WORD),
              ("天", WORD),
              ("服", WORD),
              ("用", WORD),
              ("10", NUMBER),
              ("毫", WORD),
              ("克", WORD),
              ("。", PUNCTUATION),
          ],
      ),
      dict(
          testcase_name="korean_medical_dosage_with_spaces",
          input_text="환자는 매일 10mg을 복용합니다.",  # "The patient takes 10mg daily."
          expected_tokens=[
              ("환", WORD),
              ("자", WORD),
              ("는", WORD),
              ("매", WORD),
              ("일", WORD),
              ("10", NUMBER),
              ("mg", WORD),
              ("을", WORD),
              ("복", WORD),
              ("용", WORD),
              ("합", WORD),
              ("니", WORD),
              ("다", WORD),
              (".", PUNCTUATION),
          ],
      ),
      dict(
          testcase_name="arabic_rtl",
          input_text="يأخذ المريض 10 ملغ يوميا.",  # "The patient takes 10 mg daily."
          expected_tokens=[
              ("يأخذ", WORD),
              ("المريض", WORD),
              ("10", NUMBER),
              ("ملغ", WORD),
              ("يوميا", WORD),
              (".", PUNCTUATION),
          ],
      ),
      dict(
          testcase_name="russian_cyrillic",
          input_text="Пациент принимает 10 мг.",  # "The patient takes 10 mg."
          expected_tokens=[
              ("Пациент", WORD),
              ("принимает", WORD),
              ("10", NUMBER),
              ("мг", WORD),
              (".", PUNCTUATION),
          ],
      ),
      dict(
          testcase_name="french_accents_and_currency",
          input_text="Le café coûte 5€.",  # "The coffee costs 5€."
          expected_tokens=[
              ("Le", WORD),
              ("café", WORD),
              ("coûte", WORD),
              ("5", NUMBER),
              ("€.", PUNCTUATION),  # Currency symbol and period grouped
          ],
      ),
      dict(
          testcase_name="emoji_and_symbols",
          input_text="feels 😊 medicine 💊!",
          expected_tokens=[
              ("feels", WORD),
              ("😊", PUNCTUATION),  # Emojis are treated as symbols/punctuation
              ("medicine", WORD),
              ("💊!", PUNCTUATION),  # Consecutive punctuation is grouped
          ],
      ),
      dict(
          testcase_name="mixed_latin_and_japanese_words",
          input_text="Patient 田中 takes 薬.",  # "Patient Tanaka takes medicine."
          expected_tokens=[
              ("Patient", WORD),
              ("田", WORD),
              ("中", WORD),
              ("takes", WORD),
              ("薬", WORD),
              (".", PUNCTUATION),
          ],
      ),
      dict(
          testcase_name="mixed_script_slash_abbreviation",
          input_text="Analyze DNA/РНК results.",  # РНК = RNA in Russian
          expected_tokens=[
              ("Analyze", WORD),
              ("DNA/РНК", ACRONYM),  # Recognized as a single acronym token
              ("results", WORD),
              (".", PUNCTUATION),
          ],
      ),
      dict(
          testcase_name="arabic_indic_digits_mixed_with_ascii",
          input_text="Digits ١٢٣456.",  # "Digits 123456." (١٢٣ = 123 in Arabic-Indic)
          expected_tokens=[
              ("Digits", WORD),
              ("١٢٣456", NUMBER),
              (".", PUNCTUATION),
          ],
      ),
      dict(
          testcase_name="zero_width_space",
          input_text="foo\u200bbar",
          expected_tokens=[
              ("foo", WORD),
              (
                  "\u200b",
                  PUNCTUATION,
              ),  # Zero-width space treated as punctuation
              ("bar", WORD),
          ],
      ),
      dict(
          testcase_name="slash_with_zero_width_space_not_merged",
          input_text="mg\u200b/kg",  # Zero-width space prevents slash merging
          expected_tokens=[
              ("mg", WORD),
              ("\u200b", PUNCTUATION),
              ("/", PUNCTUATION),
              ("kg", WORD),
          ],
      ),
      dict(
          testcase_name="decomposed_accent",
          input_text="cafe\u0301",  # e with combining acute accent
          expected_tokens=[
              ("caf", WORD),
              ("e\u0301", WORD),  # Grapheme cluster kept together as é
          ],
      ),
      dict(
          testcase_name="numeric_slash",
          input_text="120/80",
          expected_tokens=[
              ("120/80", ACRONYM),  # Numeric slash pattern
          ],
      ),
  )
  def test_unicode_tokenization_and_grounding(
      self, input_text, expected_tokens
  ):
    """Test tokenization, classification, and char_interval grounding."""
    # Test with default tokenization (character-by-character for CJK)
    tokenized = tokenizer.tokenize(input_text)
    self.assertLen(
        tokenized.tokens,
        len(expected_tokens),
        f"Expected {len(expected_tokens)} tokens for multilingual text, but got"
        f" {len(tokenized.tokens)}",
    )

    for i, (token, (expected_text, expected_type)) in enumerate(
        zip(tokenized.tokens, expected_tokens)
    ):
      self.assertEqual(
          token.token_type,
          expected_type,
          msg=f"Token {i} type mismatch. Text: '{expected_text}'",
      )

      # Reconstruct the text using the char_interval positions.
      actual_text = input_text[
          token.char_interval.start_pos : token.char_interval.end_pos
      ]
      self.assertEqual(
          actual_text,
          expected_text,
          msg=f"Token {i} char_interval mismatch.",
      )


class GroupedCJKTokenizerTest(parameterized.TestCase):
  """Test grouped CJK tokenization mode (non-default)."""

  @parameterized.named_parameters(
      dict(
          testcase_name="japanese_grouped",
          input_text="患者は毎日10mgを服用します。",  # "The patient takes 10mg daily."
          expected_tokens=[
              ("患者は毎日", WORD),
              ("10", NUMBER),
              ("mgを服用します", WORD),
              ("。", PUNCTUATION),
          ],
      ),
      dict(
          testcase_name="chinese_grouped",
          input_text="病人每天服用10毫克。",  # "The patient takes 10 milligrams daily."
          expected_tokens=[
              ("病人每天服用", WORD),
              ("10", NUMBER),
              ("毫克", WORD),
              ("。", PUNCTUATION),
          ],
      ),
      dict(
          testcase_name="korean_grouped",
          input_text="환자는 매일 10mg을 복용합니다.",  # "The patient takes 10mg daily."
          expected_tokens=[
              ("환자는", WORD),
              ("매일", WORD),
              ("10", NUMBER),
              ("mg을", WORD),
              ("복용합니다", WORD),
              (".", PUNCTUATION),
          ],
      ),
  )
  def test_grouped_cjk_tokenization(self, input_text, expected_tokens):
    """Test CJK tokenization with grouping enabled."""
    tokenized = tokenizer.tokenize(input_text, tokenize_cjk_by_char=False)
    self.assertLen(
        tokenized.tokens,
        len(expected_tokens),
        f"Expected {len(expected_tokens)} tokens for grouped CJK mode, but got"
        f" {len(tokenized.tokens)}",
    )

    for i, (token, (expected_text, expected_type)) in enumerate(
        zip(tokenized.tokens, expected_tokens)
    ):
      actual_text = input_text[
          token.char_interval.start_pos : token.char_interval.end_pos
      ]
      self.assertEqual(
          actual_text,
          expected_text,
          msg=f"Token {i} text mismatch.",
      )
      self.assertEqual(
          token.token_type,
          expected_type,
          msg=f"Token {i} type mismatch.",
      )


class EdgeCaseTokenizerTest(parameterized.TestCase):
  """Test edge cases identified in code review."""

  @parameterized.named_parameters(
      dict(
          testcase_name="thai_with_newline",
          input_text="นี่คือประโยคหนึ่ง\nนี่คือประโยคที่สอง",  # "This is one sentence\nThis is the second sentence"
          expected_tokens=[
              ("นี่", WORD),
              ("คื", WORD),
              ("อประโยคห", WORD),
              ("นึ่", WORD),
              ("ง", WORD),
              ("นี่", WORD),
              ("คื", WORD),
              ("อประโยค", WORD),
              ("ที่", WORD),
              ("สอง", WORD),
          ],
          expected_first_after_newline=[
              False,
              False,
              False,
              False,
              False,
              True,
              False,
              False,
              False,
              False,
          ],
      ),
      dict(
          testcase_name="lao_sentence_segmentation",
          input_text="ນີ້ແມ່ນປະໂຫຍກ\nປະໂຫຍກໃໝ່",  # "This is a sentence\nNew sentence"
          expected_tokens=[
              ("ນີ້", WORD),
              ("ແ", WORD),
              ("ມ່", WORD),
              ("ນປະໂຫຍກ", WORD),
              ("ປະໂຫຍກໃ", WORD),
              ("ໝ່", WORD),
          ],
          expected_first_after_newline=[
              False,
              False,
              False,
              False,
              True,
              False,
          ],
      ),
      dict(
          testcase_name="triple_slash_acronym",
          input_text="mL/kg/min",
          expected_tokens=[
              ("mL/kg", ACRONYM),
              ("/", PUNCTUATION),
              ("min", WORD),
          ],
          expected_first_after_newline=[False, False, False],
      ),
      dict(
          testcase_name="ascii_art_punctuation",
          input_text="----====****",
          expected_tokens=[
              ("----====****", PUNCTUATION),
          ],
          expected_first_after_newline=[False],
      ),
      dict(
          testcase_name="combining_mark_in_middle",
          input_text="résumé",  # Two accented e's
          expected_tokens=[
              ("résumé", WORD),
          ],
          expected_first_after_newline=[False],
      ),
      dict(
          testcase_name="emoji_with_skin_tone_and_punctuation",
          input_text="👍🏽!",
          expected_tokens=[
              ("👍🏽!", PUNCTUATION),
          ],
          expected_first_after_newline=[False],
      ),
      dict(
          testcase_name="mixed_digit_han_same_type_grouping",
          input_text="10毫克",  # "10 milligrams"
          expected_tokens=[
              ("10", NUMBER),
              ("毫", WORD),
              ("克", WORD),
          ],
          expected_first_after_newline=[False, False, False],
      ),
      dict(
          testcase_name="underscore_word_separator",
          input_text="hello_world",
          expected_tokens=[
              ("hello", WORD),
              ("_", PUNCTUATION),
              ("world", WORD),
          ],
          expected_first_after_newline=[False, False, False],
      ),
      dict(
          testcase_name="leading_trailing_underscores",
          input_text="_test_case_",
          expected_tokens=[
              ("_", PUNCTUATION),
              ("test", WORD),
              ("_", PUNCTUATION),
              ("case", WORD),
              ("_", PUNCTUATION),
          ],
          expected_first_after_newline=[False, False, False, False, False],
      ),
  )
  def test_special_unicode_and_punctuation_handling(
      self, input_text, expected_tokens, expected_first_after_newline
  ):
    """Test special Unicode sequences, punctuation grouping, and script handling edge cases."""
    tokenized = tokenizer.tokenize(input_text)
    self.assertLen(
        tokenized.tokens,
        len(expected_tokens),
        f"Expected {len(expected_tokens)} tokens for edge case test, but got"
        f" {len(tokenized.tokens)}",
    )

    for i, (
        token,
        (expected_text, expected_type),
        expected_newline,
    ) in enumerate(
        zip(tokenized.tokens, expected_tokens, expected_first_after_newline)
    ):
      actual_text = input_text[
          token.char_interval.start_pos : token.char_interval.end_pos
      ]
      self.assertEqual(
          actual_text,
          expected_text,
          msg=f"Token {i} text mismatch.",
      )
      self.assertEqual(
          token.token_type,
          expected_type,
          msg=f"Token {i} type mismatch.",
      )
      self.assertEqual(
          token.first_token_after_newline,
          expected_newline,
          msg=f"Token {i} newline flag mismatch.",
      )


class ExceptionTest(absltest.TestCase):
  """Test custom exception types and error conditions."""

  def test_invalid_token_interval_errors(self):
    """Test that InvalidTokenIntervalError is raised for invalid intervals."""
    text = "Hello, world!"
    tokenized = tokenizer.tokenize(text)

    # Test negative start index
    with self.assertRaisesRegex(
        tokenizer.InvalidTokenIntervalError,
        "Invalid token interval.*start_index=-1",
    ):
      tokenizer.tokens_text(
          tokenized, tokenizer.TokenInterval(start_index=-1, end_index=1)
      )

    # Test end index out of bounds
    with self.assertRaisesRegex(
        tokenizer.InvalidTokenIntervalError,
        "Invalid token interval.*end_index=999",
    ):
      tokenizer.tokens_text(
          tokenized, tokenizer.TokenInterval(start_index=0, end_index=999)
      )

    # Test start >= end
    with self.assertRaisesRegex(
        tokenizer.InvalidTokenIntervalError,
        "Invalid token interval.*start_index=2.*end_index=2",
    ):
      tokenizer.tokens_text(
          tokenized, tokenizer.TokenInterval(start_index=2, end_index=2)
      )

  def test_sentence_range_errors(self):
    """Test that SentenceRangeError is raised for invalid start positions."""
    text = "Hello world."
    tokens = tokenizer.tokenize(text).tokens

    # Test negative start position
    with self.assertRaisesRegex(
        tokenizer.SentenceRangeError, "start_token_index=-1 out of range"
    ):
      tokenizer.find_sentence_range(text, tokens, -1)

    # Test start position beyond token count
    with self.assertRaisesRegex(
        tokenizer.SentenceRangeError,
        "start_token_index=999 out of range.*Total tokens: 3",
    ):
      tokenizer.find_sentence_range(text, tokens, 999)

    # Test with empty token list
    with self.assertRaisesRegex(
        tokenizer.SentenceRangeError,
        "start_token_index=0 out of range.*Total tokens: 0",
    ):
      tokenizer.find_sentence_range(text, [], 0)


class NegativeTestCases(parameterized.TestCase):
  """Test cases for invalid input and edge cases."""

  @parameterized.named_parameters(
      dict(
          testcase_name="invalid_utf8_sequence",
          # Using Unicode replacement character for invalid sequences
          input_text="Invalid \ufffd sequence",
          expected_tokens=[
              ("Invalid", WORD),
              (
                  "\ufffd",
                  PUNCTUATION,
              ),  # Replacement char treated as punctuation
              ("sequence", WORD),
          ],
      ),
      dict(
          testcase_name="extremely_long_grapheme_cluster",
          # Test with many combining marks
          input_text="e" + "\u0301" * 10,  # e with 10 combining acute accents
          expected_tokens=[
              ("e" + "\u0301" * 10, WORD),  # Should be treated as single token
          ],
      ),
      dict(
          testcase_name="mixed_valid_invalid_unicode",
          input_text="Valid текст \ufffd 中文",
          expected_tokens=[
              ("Valid", WORD),
              ("текст", WORD),
              ("\ufffd", PUNCTUATION),
              ("中", WORD),
              ("文", WORD),
          ],
      ),
      dict(
          testcase_name="zero_width_joiners",
          # Test emoji with ZWJ sequences
          input_text="Family: 👨‍👩‍👧‍👦",  # Family emoji with ZWJ
          expected_tokens=[
              ("Family", WORD),
              (":", PUNCTUATION),
              ("👨‍👩‍👧‍👦", PUNCTUATION),  # Complex emoji as single token
          ],
      ),
      dict(
          testcase_name="isolated_combining_marks",
          # Combining marks without base characters
          input_text="\u0301\u0302\u0303 test",  # Isolated combining marks
          expected_tokens=[
              ("\u0301\u0302\u0303", PUNCTUATION),  # Treated as punctuation
              ("test", WORD),
          ],
      ),
  )
  def test_invalid_and_edge_case_unicode(self, input_text, expected_tokens):
    """Test handling of invalid Unicode sequences and edge cases."""
    tokenized = tokenizer.tokenize(input_text)
    self.assertLen(
        tokenized.tokens,
        len(expected_tokens),
        f"Expected {len(expected_tokens)} tokens for edge case '{input_text}',"
        f" but got {len(tokenized.tokens)}",
    )

    for i, (token, (expected_text, expected_type)) in enumerate(
        zip(tokenized.tokens, expected_tokens)
    ):
      actual_text = input_text[
          token.char_interval.start_pos : token.char_interval.end_pos
      ]
      self.assertEqual(
          actual_text,
          expected_text,
          f"Token {i} text mismatch. Expected '{expected_text}', got"
          f" '{actual_text}'",
      )
      self.assertEqual(
          token.token_type,
          expected_type,
          f"Token {i} type mismatch. Expected {expected_type}, got"
          f" {token.token_type}",
      )

  def test_empty_string_edge_case(self):
    tokenized = tokenizer.tokenize("")
    self.assertEmpty(tokenized.tokens, "Empty string should produce no tokens")
    self.assertEqual(
        tokenized.text, "", "Tokenized text should preserve empty string"
    )

  def test_whitespace_only_string(self):
    test_cases = [
        "   ",  # Spaces
        "\t\t",  # Tabs
        "\n\n",  # Newlines
        " \t\n\r ",  # Mixed whitespace
    ]
    for whitespace in test_cases:
      tokenized = tokenizer.tokenize(whitespace)
      self.assertEmpty(
          tokenized.tokens,
          f"Whitespace-only string '{repr(whitespace)}' should produce no"
          " tokens",
      )


if __name__ == "__main__":
  absltest.main()
