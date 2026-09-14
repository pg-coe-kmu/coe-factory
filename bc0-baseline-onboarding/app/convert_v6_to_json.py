# -*- coding: utf-8 -*-
"""
Konvertiert NoroAI_Unternehmensprofil_v6.0.md -> noroai_profile_v6.json (verschachtelt nach Überschriften).
Ergebnis dient als 'profile_json' (Reiter "Unternehmensdaten") und als RAG-Quelle für BC1.

Aufruf:
    python convert_v6_to_json.py <pfad_v6.md> <ziel.json>
Default-Pfade passend zur Projektstruktur, wenn ohne Argumente aufgerufen (aus BC0_App heraus).
"""
import sys, os, json, re, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "04_NoroAI_Grundlagen", "NoroAI_Unternehmensprofil_v6.0.md")
DST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "06_Mockdata_BC1_to_BC2", "baseline_json", "noroai_profile_v6.json")

CONTENT_KEY = "Inhalt"


def parse_md(text):
    root = {}
    # Stack hält (level, node); buffers sammelt Textzeilen je node-id
    stack = [(0, root)]
    buffers = {id(root): []}

    def uniq_key(parent, key):
        if key not in parent:
            return key
        i = 2
        while "%s (%d)" % (key, i) in parent:
            i += 1
        return "%s (%d)" % (key, i)

    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            # bis zum passenden Eltern-Level zurückspringen
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1]
            node = {}
            key = uniq_key(parent, title)
            parent[key] = node
            buffers[id(node)] = []
            stack.append((level, node))
        else:
            stack[-1][1].setdefault  # no-op
            buffers[id(stack[-1][1])].append(line)

    def finalize(node):
        # Text einsetzen
        txt = "\n".join(buffers.get(id(node), [])).strip()
        # Kinder rekursiv finalisieren
        child_keys = [k for k in list(node.keys())]
        for k in child_keys:
            node[k] = finalize(node[k])
        if not node:                      # Blatt -> nur Text
            return txt
        if txt:
            node[CONTENT_KEY] = txt
        return node

    return finalize(root)


def main():
    if not os.path.exists(SRC):
        sys.exit("v6-MD nicht gefunden: %s" % SRC)
    text = open(SRC, encoding="utf-8").read()
    tree = parse_md(text)
    out = {
        "meta": {
            "version": "v6.0",
            "quelle": os.path.basename(SRC),
            "konvertiert_am": datetime.datetime.utcnow().isoformat() + "Z",
            "konvertiert_von": "BC0 / convert_v6_to_json.py",
        }
    }
    # Den Doku-Titel (einzige H1) als 'profil' einhängen; sonst gesamten Baum
    if isinstance(tree, dict) and len(tree) == 1:
        only = list(tree.values())[0]
        out["profil"] = only if isinstance(only, dict) else {CONTENT_KEY: only}
    else:
        out["profil"] = tree
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("OK: %s (%d Bytes)" % (DST, os.path.getsize(DST)))


if __name__ == "__main__":
    main()
