"""State-independent Singmaster dynamics; no solver, evaluation or action selection."""

RULES_VERSION = "singmaster-sticker-cycles-v1"
FACE_CW_CYCLES = ("1397", "2684")
STRIP_CW_CYCLES = {
    "U": ("R123", "F123", "L123", "B123"),
    "R": ("U369", "B741", "D369", "F369"),
    "F": ("U789", "R147", "D321", "L963"),
    "D": ("R789", "B789", "L789", "F789"),
    "L": ("U147", "F147", "D147", "B963"),
    "B": ("U123", "L741", "D987", "R369"),
}
TURN_RULES = (
    " Cells 1-9 are row-major per face. CW source>destination cycles wrap last>first; "
    "copy old stickers simultaneously. On the turned face: "
    + ",".join(">".join(c) for c in FACE_CW_CYCLES) + ". "
    "Adjacent strips (digits are cells; map position-wise): "
    + ";".join(f"{f}:" + ">".join(strips) for f, strips in STRIP_CW_CYCLES.items()) + ". "
    "Unlisted cells stay fixed. Prime reverses CW cycles; 2 repeats CW twice."
)
