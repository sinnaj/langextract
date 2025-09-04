import sys


def chunk_document(text, max_chunk_size=5000):
  chunks = []
  words = text.split()
  for i in range(0, len(words), max_chunk_size - 200):  # 200 words overlap
    chunk = " ".join(words[i : i + max_chunk_size])
    chunks.append(chunk)
  return chunks
