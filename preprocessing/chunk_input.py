

import sys


def chunk_document(text, max_chunk_size=5000):
        print(f"[INFO] Chunking large document (length: {len(words)})", file=sys.stderr)
        chunks = []
        words = text.split()
        if len(words) > max_chunk_size:
            for i in range(0, len(words), max_chunk_size - 200):  # 200 words overlap
                chunk = " ".join(words[i:i + max_chunk_size])
                chunks.append(chunk)
        return chunks
