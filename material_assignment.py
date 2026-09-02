import argparse
from src.pipeline.materials import (
    MATERIAL_CATALOG,
    STYLE_PRESETS,
    load_presets,
    load_semantic,
    assign_materials,
    run_material_assignment,
    match_room_preset
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Material assignment stage with style presets.")
    parser.add_argument("--preset", type=str, default=None, help="Style preset name (e.g. 'Luxury Minimal', 'Rustic', 'Industrial')")
    parser.add_argument("--input", type=str, default=".output/semantic.json", help="Path to input semantic JSON")
    parser.add_argument("--output", type=str, default=".output/materials.json", help="Path to output materials JSON")
    parser.add_argument("--catalog", type=str, default=None, help="Path to custom presets catalog JSON")
    args = parser.parse_args()

    run_material_assignment(
        input_path=args.input,
        output_path=args.output,
        preset=args.preset,
        catalog_path=args.catalog
    )

