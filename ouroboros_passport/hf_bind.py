import argparse
import json
import os

from .verifier import verify

"""Bind a passport to a Hugging Face model repo: upload passport.json and
project the anatomy into the README. The HF model card becomes the public
projection of the passport."""


def bind(passport_path, repo_id, readme_path=None):
    from huggingface_hub import HfApi

    p = json.load(open(passport_path, encoding="utf-8"))
    verification = verify(p)
    if not verification["valid"]:
        raise ValueError("invalid passport: " + "; ".join(verification["issues"]))

    api = HfApi()
    api.upload_file(
        path_or_fileobj=passport_path,
        path_in_repo="passport.json",
        repo_id=repo_id,
        repo_type="model",
    )
    sec_lines = []
    for sec, body in p.get("sections", {}).items():
        sec_lines.append("### " + sec)
        for ev in body.get("evidence", []):
            val = ev.get("value")
            suffix = " = " + json.dumps(val, ensure_ascii=False) if val is not None else ""
            sec_lines.append("- " + ev["name"] + ": " + ev["class"] + suffix)
    anatomy = (
        "## Model Anatomy (Ouroboros Passport)\n\n"
        + "Passport digest: " + p.get("digest", "") + "\n\n"
        + "\n".join(sec_lines)
        + "\n"
    )
    readme = open(readme_path, encoding="utf-8").read() if readme_path and os.path.exists(readme_path) else ""
    marker = "## Model Anatomy (Ouroboros Passport)"
    if marker in readme:
        readme = readme.split(marker)[0].rstrip() + "\n\n" + anatomy
    else:
        readme = readme.rstrip() + "\n\n" + anatomy
    tmp = passport_path + ".readme.md"
    try:
        open(tmp, "w", encoding="utf-8").write(readme)
        api.upload_file(
            path_or_fileobj=tmp,
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="model",
        )
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
    return {"repo": repo_id, "passport_digest": p.get("digest")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("passport")
    ap.add_argument("repo_id")
    ap.add_argument("--readme", default=None)
    args = ap.parse_args()
    print(json.dumps(bind(args.passport, args.repo_id, args.readme), indent=2))
