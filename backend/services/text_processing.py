import re


class TextProcessingService:
    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""

        normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", " ")
        normalized = re.sub(r"[^\S\n]+", " ", normalized)

        paragraphs = []
        buffer = []
        for raw_line in normalized.split("\n"):
            line = raw_line.strip()
            if not line:
                if buffer:
                    paragraphs.append(" ".join(buffer))
                    buffer = []
                continue
            buffer.append(line)
        if buffer:
            paragraphs.append(" ".join(buffer))

        return re.sub(r"\n{3,}", "\n\n", "\n\n".join(paragraphs)).strip()

    @staticmethod
    def analyze_text(text: str) -> dict:
        words = re.findall(r"\b[\w']+\b", text)
        word_count = len(words)
        char_count = len(text)
        paragraph_count = len([p for p in text.split("\n\n") if p.strip()])
        estimated_minutes = round(word_count / 150, 2) if word_count else 0.0

        return {
            "word_count": word_count,
            "char_count": char_count,
            "paragraph_count": paragraph_count,
            "estimated_listening_minutes": estimated_minutes,
            "estimated_listening_seconds": int(round(estimated_minutes * 60)),
        }

