#!/usr/bin/env python3
"""Test script to reproduce the NoneType iteration error."""

from pathlib import Path
import tempfile

import lxRunnerExtraction


def test_with_real_text():
  """Test makeRun with real text content to trigger potential NoneType error."""

  # Create a temporary file with some text that might trigger the error
  test_text = """# 2 Señalización de las instalaciones manuales de protección contra incendios

1 La señalización de las instalaciones manuales de protección contra incendios debe cumplir lo establecido en el vigente Reglamento de instalaciones de protección contra incendios, aprobado por el Real Decreto 513/2017, de 22 de mayo.

# Sección SI 5 Intervención de los bomberos

# 1 Condiciones de aproximación y entorno(1)

# 1.1 Aproximación a los edificios

1 Los viales de aproximación de los vehículos de los bomberos a los espacios de maniobra a los que se refiere el apartado 1.2, deben cumplir las condiciones siguientes:

a) anchura mínima libre 3,5 m;
b) altura mínima libre o gálibo 4,5 m;
c)capacidad portante del vial 20 kN/m².

2 En los tramos curvos, el carril de rodadura debe quedar delimitado por la traza de una corona circular cuyos radios mínimos deben ser 5,30 m y 12,50 m, con una anchura libre para circulación de 7,20 m.
"""

  # Create temporary input file
  with tempfile.NamedTemporaryFile(
      mode='w', suffix='.txt', delete=False, encoding='utf-8'
  ) as f:
    f.write(test_text)
    temp_file_path = f.name

  try:
    # Set the INPUT_FILE globally before calling makeRun
    lxRunnerExtraction.INPUT_FILE = Path(temp_file_path)

    print('Testing makeRun with real text content...')
    lxRunnerExtraction.makeRun(
        'test-nonetype-001',  # RUN_ID
        'openai/gpt-4o-mini',  # MODEL_ID
        0.1,  # MODEL_TEMPERATURE
        10,  # MAX_NORMS_PER_5K
        5000,  # MAX_CHAR_BUFFER
        1,  # EXTRACTION_PASSES
        'input_promptfiles/extraction_prompt.md',  # INPUT_PROMPTFILE
        'input_glossaryfiles/dsl_glossary.json',  # INPUT_GLOSSARYFILE
        'input_examplefiles/default.py',  # INPUT_EXAMPLESFILE
        'input_semanticsfiles/prompt_appendix_entity_semantics.md',  # INPUT_SEMANTCSFILE
        'input_teachfiles/prompt_appendix_teaching.md',  # INPUT_TEACHFILE
    )
    print('makeRun with real text completed successfully!')

  except Exception as e:
    print(f'Error: {e}')
    import traceback

    traceback.print_exc()

  finally:
    # Clean up
    Path(temp_file_path).unlink(missing_ok=True)


if __name__ == '__main__':
  test_with_real_text()
