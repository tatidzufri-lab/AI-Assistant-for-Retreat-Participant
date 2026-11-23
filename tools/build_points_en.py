import json, sys, uuid
from pathlib import Path
from dotenv import dotenv_values
from openai import OpenAI

EN_DIR = Path(sys.argv[1]); OUT = Path(sys.argv[2])
key = dotenv_values(sys.argv[3])["OPENAI_API_KEY"]
client = OpenAI(api_key=key)

EXACT = {"22_current_schedule_filled", "05_pricing_tariffs", "06_booking_payment", "07_refund_policy",
         "08_location_logistics", "09_accommodation_food", "10_packing_list", "11_checkin_checkout",
         "15_participation_rules", "16_health_safety", "18_pre_retreat_preparation", "20_online_course",
         "23_postretrit_practices_checklist"}
DOC_TYPE = [("22_", "schedule"), ("10_", "packing"), ("05_", "pricing"), ("08_", "logistics"), ("18_", "preparation"),
            ("19_", "postretrit"), ("23_", "postretrit"), ("20_", "course")]

def chunks(text, size=1000, overlap=200):
    """По строкам, как RecursiveCharacterTextSplitter n8n: ~1000 знаков с перекрытием ~200, с номерами строк."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        j, length = i, 0
        while j < len(lines) and (length + len(lines[j]) + 1 <= size or j == i):
            length += len(lines[j]) + 1; j += 1
        body = "\n".join(lines[i:j]).strip()
        if body:
            out.append((body, i + 1, j))
        if j >= len(lines):
            break
        back, k = 0, j
        while k > i + 1 and back + len(lines[k - 1]) + 1 <= overlap:
            back += len(lines[k - 1]) + 1; k -= 1
        i = k if k > i else j
    return out

points = []
for f in sorted(EN_DIR.glob("*_en.md")):
    base = f.stem[:-3]
    doc_type = next((t for p, t in DOC_TYPE if base.startswith(p)), "general")
    for body, a, b in chunks(f.read_text(encoding="utf-8")):
        points.append({"id": str(uuid.uuid4()), "content": body, "source": f.name, "from": a, "to": b,
                       "doc_type": doc_type, "search_type": "exact" if base in EXACT else "vector"})
texts = [p["content"] for p in points]
vecs = []
for i in range(0, len(texts), 64):
    r = client.embeddings.create(model="text-embedding-3-small", input=texts[i:i + 64])
    vecs += [d.embedding for d in r.data]
qpoints = [{"id": p["id"], "vector": v, "payload": {
    "content": p["content"],
    "metadata": {"source": p["source"], "blobType": "text/markdown", "loc": {"lines": {"from": p["from"], "to": p["to"]}},
                 "doc_type": p["doc_type"], "lang": "en"},
    "search_type": p["search_type"]}} for p, v in zip(points, vecs)]
OUT.write_text(json.dumps({"points": qpoints}))
from collections import Counter
print(len(qpoints), "points;", Counter(p["search_type"] for p in points))
