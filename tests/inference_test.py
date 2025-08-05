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

import os
import textwrap
from unittest import mock

from absl.testing import absltest

from langextract import data
from langextract import inference
import langextract as lx


class TestOllamaLanguageModel(absltest.TestCase):

  @mock.patch.object(inference.OllamaLanguageModel, "_ollama_query")
  def test_ollama_infer(self, mock_ollama_query):

    # Actuall full gemma2 response using Ollama.
    gemma_response = {
        "model": "gemma2:latest",
        "created_at": "2025-01-23T22:37:08.579440841Z",
        "response": "{'bus' : '**autóbusz**'} \n\n\n  \n",
        "done": True,
        "done_reason": "stop",
        "context": [
            106,
            1645,
            108,
            1841,
            603,
            1986,
            575,
            59672,
            235336,
            107,
            108,
            106,
            2516,
            108,
            9766,
            6710,
            235281,
            865,
            664,
            688,
            7958,
            235360,
            6710,
            235306,
            688,
            12990,
            235248,
            110,
            139,
            108,
        ],
        "total_duration": 24038204381,
        "load_duration": 21551375738,
        "prompt_eval_count": 15,
        "prompt_eval_duration": 633000000,
        "eval_count": 17,
        "eval_duration": 1848000000,
    }
    mock_ollama_query.return_value = gemma_response
    model = inference.OllamaLanguageModel(
        model_id="gemma2:latest",
        model_url="http://localhost:11434",
        structured_output_format="json",
    )
    batch_prompts = ["What is bus in Hungarian?"]
    results = list(model.infer(batch_prompts))

    mock_ollama_query.assert_called_once_with(
        prompt="What is bus in Hungarian?",
        model="gemma2:latest",
        structured_output_format="json",
        model_url="http://localhost:11434",
    )
    expected_results = [[
        inference.ScoredOutput(
            score=1.0, output="{'bus' : '**autóbusz**'} \n\n\n  \n"
        )
    ]]
    self.assertEqual(results, expected_results)


class TestOpenAILanguageModel(absltest.TestCase):

  @mock.patch("openai.OpenAI")
  def test_openai_infer(self, mock_openai_class):
    # Mock the OpenAI client and chat completion response
    mock_client = mock.Mock()
    mock_openai_class.return_value = mock_client

    # Mock response structure for v1.x API
    mock_response = mock.Mock()
    mock_response.choices = [
        mock.Mock(message=mock.Mock(content='{"name": "John", "age": 30}'))
    ]
    mock_client.chat.completions.create.return_value = mock_response

    # Create model instance
    model = inference.OpenAILanguageModel(
        model_id="gpt-4o-mini", api_key="test-api-key", temperature=0.5
    )

    # Test inference
    batch_prompts = ["Extract name and age from: John is 30 years old"]
    results = list(model.infer(batch_prompts))

    # Verify API was called correctly
    mock_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that responds in JSON format."
                ),
            },
            {
                "role": "user",
                "content": "Extract name and age from: John is 30 years old",
            },
        ],
        temperature=0.5,
        max_tokens=None,
        top_p=None,
        n=1,
    )

    # Check results
    expected_results = [[
        inference.ScoredOutput(score=1.0, output='{"name": "John", "age": 30}')
    ]]
    self.assertEqual(results, expected_results)

  def test_openai_parse_output_json(self):
    model = inference.OpenAILanguageModel(
        api_key="test-key", format_type=data.FormatType.JSON
    )

    # Test valid JSON parsing
    output = '{"key": "value", "number": 42}'
    parsed = model.parse_output(output)
    self.assertEqual(parsed, {"key": "value", "number": 42})

    # Test invalid JSON
    with self.assertRaises(ValueError) as context:
      model.parse_output("invalid json")
    self.assertIn("Failed to parse output as JSON", str(context.exception))

  def test_openai_parse_output_yaml(self):
    model = inference.OpenAILanguageModel(
        api_key="test-key", format_type=data.FormatType.YAML
    )

    # Test valid YAML parsing
    output = "key: value\nnumber: 42"
    parsed = model.parse_output(output)
    self.assertEqual(parsed, {"key": "value", "number": 42})

    # Test invalid YAML
    with self.assertRaises(ValueError) as context:
      model.parse_output("invalid: yaml: bad")
    self.assertIn("Failed to parse output as YAML", str(context.exception))

  def test_openai_no_api_key_raises_error(self):
    with self.assertRaises(ValueError) as context:
      inference.OpenAILanguageModel(api_key=None)
    self.assertEqual(str(context.exception), "API key not provided.")

  @mock.patch("openai.OpenAI")
  def test_openai_temperature_zero(self, mock_openai_class):
    # Test that temperature=0.0 is properly passed through
    mock_client = mock.Mock()
    mock_openai_class.return_value = mock_client

    mock_response = mock.Mock()
    mock_response.choices = [
        mock.Mock(message=mock.Mock(content='{"result": "test"}'))
    ]
    mock_client.chat.completions.create.return_value = mock_response

    model = inference.OpenAILanguageModel(
        api_key="test-key", temperature=0.0  # Testing zero temperature
    )

    list(model.infer(["test prompt"]))

    # Verify temperature=0.0 was passed to the API
    mock_client.chat.completions.create.assert_called_with(
        model="gpt-4o-mini",
        messages=mock.ANY,
        temperature=0.0,
        max_tokens=None,
        top_p=None,
        n=1,
    )


if __name__ == "__main__":
  absltest.main()


class TestAzureOpenAILanguageModel(absltest.TestCase):
  """Test Azure OpenAI language model integration."""

  def setUp(self):
    """Set up test fixtures."""
    self.mock_api_key = "test-azure-openai-api-key"
    self.mock_azure_endpoint = "https://eastus2.api.cognitive.microsoft.com/"
    self.mock_model_id = "gpt-4o"
    self.mock_api_version = "2024-12-01-preview"

  def test_azure_openai_initialization(self):
    """Test Azure OpenAI model initialization."""
    model = inference.AzureOpenAILanguageModel(
        model_id=self.mock_model_id,
        api_key=self.mock_api_key,
        azure_endpoint=self.mock_azure_endpoint,
        api_version=self.mock_api_version,
    )

    self.assertEqual(model.model_id, self.mock_model_id)
    self.assertEqual(model.api_key, self.mock_api_key)
    self.assertEqual(model.azure_endpoint, self.mock_azure_endpoint)
    self.assertEqual(model.api_version, self.mock_api_version)
    self.assertIsNotNone(model._client)

  def test_azure_openai_missing_api_key(self):
    """Test that missing API key raises ValueError."""
    with self.assertRaises(ValueError) as context:
      inference.AzureOpenAILanguageModel(
          azure_endpoint=self.mock_azure_endpoint,
          api_key=None,
      )
    self.assertIn("API key not provided", str(context.exception))

  def test_azure_openai_missing_endpoint(self):
    """Test that missing Azure endpoint raises ValueError."""
    with self.assertRaises(ValueError) as context:
      inference.AzureOpenAILanguageModel(
          api_key=self.mock_api_key,
          azure_endpoint=None,
      )
    self.assertIn("Azure endpoint not provided", str(context.exception))

  @mock.patch("openai.AzureOpenAI")
  def test_azure_openai_client_creation(self, mock_azure_openai):
    """Test that Azure OpenAI client is created with correct parameters."""
    mock_client_instance = mock.Mock()
    mock_azure_openai.return_value = mock_client_instance

    model = inference.AzureOpenAILanguageModel(
        model_id=self.mock_model_id,
        api_key=self.mock_api_key,
        azure_endpoint=self.mock_azure_endpoint,
        api_version=self.mock_api_version,
    )

    mock_azure_openai.assert_called_once_with(
        api_key=self.mock_api_key,
        azure_endpoint=self.mock_azure_endpoint,
        api_version=self.mock_api_version,
    )
    self.assertEqual(model._client, mock_client_instance)

  @mock.patch("openai.AzureOpenAI")
  def test_azure_openai_inference(self, mock_azure_openai):
    """Test Azure OpenAI inference functionality."""
    # Mock the client and response
    mock_client = mock.Mock()
    mock_azure_openai.return_value = mock_client

    mock_response = mock.Mock()
    mock_choice = mock.Mock()
    mock_message = mock.Mock()
    mock_message.content = (
        '{"extraction_class": "character", "extraction_text": "Lady Juliet",'
        ' "attributes": {"emotional_state": "longing"}}'
    )
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    # Initialize the model
    model = inference.AzureOpenAILanguageModel(
        model_id=self.mock_model_id,
        api_key=self.mock_api_key,
        azure_endpoint=self.mock_azure_endpoint,
        api_version=self.mock_api_version,
    )

    # Test inference
    prompts = [
        "Extract characters from this text: Lady Juliet gazed longingly at the"
        " stars."
    ]
    results = list(model.infer(prompts))

    self.assertEqual(len(results), 1)
    self.assertEqual(len(results[0]), 1)
    self.assertEqual(results[0][0].score, 1.0)
    self.assertIn("Lady Juliet", results[0][0].output)

    # Verify the client was called correctly
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args
    self.assertEqual(call_args[1]["model"], self.mock_model_id)
    self.assertEqual(len(call_args[1]["messages"]), 2)
    self.assertEqual(call_args[1]["messages"][0]["role"], "system")
    self.assertEqual(call_args[1]["messages"][1]["role"], "user")

  def test_parse_output_json(self):
    """Test JSON output parsing."""
    model = inference.AzureOpenAILanguageModel(
        model_id=self.mock_model_id,
        api_key=self.mock_api_key,
        azure_endpoint=self.mock_azure_endpoint,
        format_type=data.FormatType.JSON,
    )

    json_output = '{"key": "value", "number": 42}'
    parsed = model.parse_output(json_output)

    self.assertEqual(parsed, {"key": "value", "number": 42})

  def test_parse_output_yaml(self):
    """Test YAML output parsing."""
    model = inference.AzureOpenAILanguageModel(
        model_id=self.mock_model_id,
        api_key=self.mock_api_key,
        azure_endpoint=self.mock_azure_endpoint,
        format_type=data.FormatType.YAML,
    )

    yaml_output = "key: value\nnumber: 42"
    parsed = model.parse_output(yaml_output)

    self.assertEqual(parsed, {"key": "value", "number": 42})


class TestAzureOpenAIIntegrationWithLangExtract(absltest.TestCase):
  """Test Azure OpenAI integration with the main langextract API."""

  def setUp(self):
    """Set up test fixtures."""
    self.mock_api_key = "test-azure-openai-api-key"
    self.mock_azure_endpoint = "https://eastus2.api.cognitive.microsoft.com/"
    self.mock_model_id = "gpt-4o"

    # Example from README adapted for testing
    self.prompt = textwrap.dedent("""\
            Extract characters, emotions, and relationships in order of appearance.
            Use exact text for extractions. Do not paraphrase or overlap entities.
            Provide meaningful attributes for each entity to add context.""")

    self.examples = [
        lx.data.ExampleData(
            text=(
                "ROMEO. But soft! What light through yonder window breaks? It"
                " is the east, and Juliet is the sun."
            ),
            extractions=[
                lx.data.Extraction(
                    extraction_class="character",
                    extraction_text="ROMEO",
                    attributes={"emotional_state": "wonder"},
                ),
                lx.data.Extraction(
                    extraction_class="emotion",
                    extraction_text="But soft!",
                    attributes={"feeling": "gentle awe"},
                ),
                lx.data.Extraction(
                    extraction_class="relationship",
                    extraction_text="Juliet is the sun",
                    attributes={"type": "metaphor"},
                ),
            ],
        )
    ]

  @mock.patch("openai.AzureOpenAI")
  def test_azure_openai_with_langextract_extract(self, mock_azure_openai):
    """Test using Azure OpenAI with the main langextract.extract function."""
    # Mock the client and response
    mock_client = mock.Mock()
    mock_azure_openai.return_value = mock_client

    # Mock a realistic response that would be parsed by the resolver
    mock_response_content = textwrap.dedent("""\
            ```json
            {
              "extractions": [
                {
                  "extraction_class": "character",
                  "extraction_text": "Lady Juliet",
                  "attributes": {"emotional_state": "longing"}
                },
                {
                  "extraction_class": "emotion",
                  "extraction_text": "gazed longingly",
                  "attributes": {"feeling": "yearning"}
                }
              ]
            }
            ```""")

    mock_response = mock.Mock()
    mock_choice = mock.Mock()
    mock_message = mock.Mock()
    mock_message.content = mock_response_content
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    # Test input text
    input_text = (
        "Lady Juliet gazed longingly at the stars, her heart aching for Romeo"
    )

    # Run the extraction with Azure OpenAI
    result = lx.extract(
        text_or_documents=input_text,
        prompt_description=self.prompt,
        examples=self.examples,
        language_model_type=inference.AzureOpenAILanguageModel,
        model_id=self.mock_model_id,
        api_key=self.mock_api_key,
        language_model_params={
            "azure_endpoint": self.mock_azure_endpoint,
        },
        fence_output=True,  # Required for Azure OpenAI as mentioned in README
        use_schema_constraints=False,  # Required for Azure OpenAI as mentioned in README
    )

    # Verify the result structure
    self.assertIsInstance(result, lx.data.AnnotatedDocument)
    self.assertEqual(result.text, input_text)

    # Verify the client was called
    mock_client.chat.completions.create.assert_called()

  def test_azure_openai_parameters_validation(self):
    """Test that Azure OpenAI specific parameters are validated."""
    input_text = "Test text"

    # Test missing azure_endpoint
    with self.assertRaises(ValueError) as context:
      lx.extract(
          text_or_documents=input_text,
          prompt_description=self.prompt,
          examples=self.examples,
          language_model_type=inference.AzureOpenAILanguageModel,
          model_id=self.mock_model_id,
          api_key=self.mock_api_key,
          language_model_params={
              # azure_endpoint missing
          },
      )
    self.assertIn("Azure endpoint not provided", str(context.exception))

  def test_azure_openai_default_api_version(self):
    """Test that Azure OpenAI uses the default API version when not specified."""
    model = inference.AzureOpenAILanguageModel(
        model_id=self.mock_model_id,
        api_key=self.mock_api_key,
        azure_endpoint=self.mock_azure_endpoint,
        # api_version not specified
    )

    self.assertEqual(model.api_version, "2024-12-01-preview")


if __name__ == "__main__":
  absltest.main()
