"""Execute the Python sections in reproducibility.qmd, without rendering the blog."""
import argparse
from pathlib import Path
import re


def main():
    project_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=project_dir.parent / "Blog6data",
        help="Folder containing the six original PSID releases.",
    )
    arguments = parser.parse_args()
    source = project_dir / "reproducibility.qmd"
    chunks = re.findall(r"^```\{python\}\n(.*?)^```\s*$", source.read_text(), re.M | re.S)
    if not chunks:
        raise RuntimeError("No Python sections found in reproducibility.qmd")

    # Use the same code as the readable notebook, with explicit portable paths.
    namespace = {
        "__name__": "__main__",
        "PROJECT_DIR": project_dir,
        "RAW_DATA_DIR": arguments.data_dir.resolve(),
    }
    for number, chunk in enumerate(chunks, start=1):
        print(f"Reproducibility section {number}/{len(chunks)}", flush=True)
        exec(compile(chunk, f"{source}:section-{number}", "exec"), namespace)

    print("Finished: tables in results/tables; figures in results/figures.")


if __name__ == "__main__":
    main()
