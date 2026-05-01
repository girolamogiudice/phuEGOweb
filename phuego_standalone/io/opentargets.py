import pickle
from pathlib import Path

def load_opentargets_lookup(path):
    path = Path(path)

    try:
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")

        with open(path, "rb") as f:
            data = pickle.load(f)

        print(f"✅ OpenTargets loaded: {len(data)} proteins")

        for _, ot in data.items():
            ot["drugs"] = sorted(
                ot.get("drugs", []),
                key=lambda x: -x.get("phase", 0)
            )
            ot["diseases"] = sorted(
                ot.get("diseases", []),
                key=lambda x: -x.get("score", 0)
            )

        return data

    except Exception as e:
        print(f"⚠️ OpenTargets not loaded: {e}")
        return {}
