"""Read PSID fields using their documented fixed-width column positions."""
import hashlib
import re

import pandas as pd


def read_fixed(folder, stem, columns, metadata):
    """Return selected fields and a source checksum; append variable metadata."""
    layout_text = (folder / f"{stem}.do").read_text()
    layout = layout_text.split("infix", 1)[1].split("using", 1)[0]
    spans = {
        name: (int(start) - 1, int(end))
        for name, start, end in re.findall(r"(\w+)\s+(\d+)\s*-\s*(\d+)", layout)
    }
    labels = dict(re.findall(r'label variable\s+(\w+)\s+"([^"]+)"', layout_text))
    selected = [spans[column] for column in columns]
    source = folder / f"{stem}.txt"
    rows = []
    digest = hashlib.sha256()

    with source.open("rb") as file:
        for line in file:
            digest.update(line)
            rows.append([
                int(line[start:end].strip()) if line[start:end].strip() else None
                for start, end in selected
            ])

    for column in columns:
        metadata.append({
            "file": str(source.relative_to(folder.parent)),
            "variable": column,
            "label": labels.get(column, ""),
            "start": spans[column][0] + 1,
            "end": spans[column][1],
        })

    print(f"Read {stem}: {len(rows):,} rows, {len(columns)} columns")
    frame = pd.DataFrame(rows, columns=columns)
    audit = {"file": source.name, "rows": len(rows), "sha256": digest.hexdigest()}
    return frame, audit
