import pickle

FEATURES = [
    "years_experience", "num_skills", "degree_level", "age", "gender", "nationality_code",
    "zip_code", "university_rank", "gap_months",
]


def load_model(path):
    with open(path, "rb") as fh:
        return pickle.load(fh)


def extract_features(profile):
    return [profile.get(name, 0) for name in FEATURES]
