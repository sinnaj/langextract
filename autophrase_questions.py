from typing import Any, Dict

from postprocessing.build_question_from_tag_path import build_question_from_tag_path


def autophrase_questions(obj: Dict[str, Any]):
  qs = obj.get("questions", [])
  created = 0
  for q in qs:
    if q.get("question_text"):
      continue
    tp = q.get("tag_path") or (q.get("outputs") or [None])[0]
    if not isinstance(tp, str):
      continue
    phrased = build_question_from_tag_path(tp)
    q["question_text"] = phrased + " (auto)"
    created += 1
  if created:
    obj.setdefault("quality", {}).setdefault("warnings", []).append(
        f"AUTO_QUESTION_PHRASED:{created}"
    )
