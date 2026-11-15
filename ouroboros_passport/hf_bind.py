import argparse, json, sys

"""Bind a passport to a Hugging Face model repo: upload passport.json and
project the anatomy into the README. The HF model card becomes the public
projection of the passport."""

def bind(passport_path, repo_id, readme_path=None):
    from huggingface_hub import HfApi
    api = HfApi()
    p = json.load(open(passport_path, encoding="utf-8"))
    api.upload_file(path_or_fileobj=passport_path, path_in_repo="passport.json", repo_id=repo_id, repo_type="model")
    sec_lines = []
    for sec, body in p.get("sections", {}).items():
        sec_lines.append("### " + sec)
        for ev in body.get("evidence", []):
            val = ev.get("value")
            sec_lines.append("- " + ev["name"] + ": " + ev["class"] + (" = " + json.dumps(val) if val is not None else ""))
    anatomy = "## Model Anatomy (Ouroboros Passport)\n\nPassport digest: `" + p.get("digest", "") + "`\n\n" + "\n".join(sec_lines) + "\n"
    readme = open(readme_path, encoding="utf-8").read() if readme_path and os.path.exists(readme_path) else ""
    marker = "## Model Anatomy (Ouroboros Passport)"
    if marker in readme:
        readme = readme.split(marker)[0].rstrip() + "\n\n" + anatomy
    else:
        readme = readme.rstrip() + "\n\n" + anatomy
    tmp = passport_path + ".readme.md"
    open(tmp, "w", encoding="utf-8").write(readme)
    api.upload_file(path_or_fileobj=tmp, path_in_repo="README.md", repo_id=repo_id, repo_type="model")
    return {"repo": repo_id, "passport_digest": p.get("digest")}

if __name__ == "__main__":
    import os
    ap = argparse.ArgumentParser()
    ap.add_argument("passport"); ap.add_argument("repo_id")
    ap.add_argument("--readme", default=None)
    a = ap.parse_args()
    print(json.dumps(bind(a.passport, a.repo_id, a.readme), indent=2))
