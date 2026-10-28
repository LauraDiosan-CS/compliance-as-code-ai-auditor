import re

from pdfminer.high_level import extract_text

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def parse_cv(stream):
    text = extract_text(stream)
    email = EMAIL.search(text)
    return {
        "email": email.group(0) if email else "unknown",
        "raw_text": text,
        "years_experience": len(re.findall(r"\b(19|20)\d{2}\b", text)) // 2,
        "num_skills": len(re.findall(r"python|java|sql|excel|sales|aws", text, re.I)),
        "degree_level": 3 if "master" in text.lower() else 2 if "bachelor" in text.lower() else 1,
    }
