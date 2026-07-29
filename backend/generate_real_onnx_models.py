"""Generate self-contained ONNX models for pet breed and age classification.

Uses only the ``onnx`` helper library (no PyTorch/torchvision required).
The models are lightweight MLPs that operate on a 224×224 RGB image tensor:

  Breed model:  input [1, 3, 224, 224] → output [1, 37]   (37 breed logits)
  Age model:    input [1, 3, 224, 224] → output [1, 3]    (3 age-category logits)

Weights are initialised with orthogonal-like random values so the models
produce varied (but untrained) predictions for different images.  The files
are fully self-contained — no external ``.onnx.data`` sidecar.
"""

import os

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

NUM_BREEDS = 37
NUM_AGES = 3
INPUT_C, INPUT_H, INPUT_W = 3, 224, 224
FLAT_DIM = INPUT_C * INPUT_H * INPUT_W  # 150528

# Smaller hidden dimension keeps the file size manageable.
HIDDEN_DIM = 32


def _random_weight(shape: tuple[int, ...], seed: int) -> np.ndarray:
    """Return a float32 array with small random values (seeded for reproducibility)."""
    rng = np.random.default_rng(seed)
    # Xavier-style scaling
    fan_in = shape[0] if len(shape) >= 2 else shape[0]
    scale = np.sqrt(2.0 / fan_in)
    return (rng.standard_normal(shape) * scale).astype(np.float32)


def _build_classifier(name: str, num_classes: int, seed_offset: int) -> onnx.ModelProto:
    """Build a 2-layer MLP:  flatten → Linear(FLAT_DIM, HIDDEN) → ReLU → Linear(HIDDEN, num_classes)."""

    # --- Initializer weights ---
    W1 = _random_weight((FLAT_DIM, HIDDEN_DIM), seed=42 + seed_offset)
    b1 = np.zeros(HIDDEN_DIM, dtype=np.float32)
    W2 = _random_weight((HIDDEN_DIM, num_classes), seed=99 + seed_offset)
    b2 = np.zeros(num_classes, dtype=np.float32)

    # --- ONNX graph ---
    X = helper.make_tensor_value_info("input_image", TensorProto.FLOAT, [1, INPUT_C, INPUT_H, INPUT_W])
    Y = helper.make_tensor_value_info(f"{name}_output", TensorProto.FLOAT, [1, num_classes])

    # Flatten: [1, 3, 224, 224] → [1, 150528]
    flatten_node = helper.make_node("Flatten", inputs=["input_image"], outputs=["flat"], axis=1)

    # FC1: flat × W1 + b1
    fc1_node = helper.make_node("MatMul", inputs=["flat", "W1"], outputs=["fc1_mm"])
    add1_node = helper.make_node("Add", inputs=["fc1_mm", "b1"], outputs=["fc1"])

    # ReLU
    relu_node = helper.make_node("Relu", inputs=["fc1"], outputs=["relu1"])

    # FC2: relu1 × W2 + b2
    fc2_node = helper.make_node("MatMul", inputs=["relu1", "W2"], outputs=["fc2_mm"])
    add2_node = helper.make_node("Add", inputs=["fc2_mm", "b2"], outputs=[f"{name}_output"])

    graph = helper.make_graph(
        [flatten_node, fc1_node, add1_node, relu_node, fc2_node, add2_node],
        f"pet_{name}_classifier",
        [X],
        [Y],
        initializer=[
            numpy_helper.from_array(W1, name="W1"),
            numpy_helper.from_array(b1, name="b1"),
            numpy_helper.from_array(W2, name="W2"),
            numpy_helper.from_array(b2, name="b2"),
        ],
    )

    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 14)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    return model


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))

    breed_path = os.path.join(out_dir, "pet_breed_model.onnx")
    age_path = os.path.join(out_dir, "pet_age_model.onnx")

    print("Building breed classifier...")
    breed_model = _build_classifier("breed", NUM_BREEDS, seed_offset=0)
    onnx.save(breed_model, breed_path)
    size_kb = os.path.getsize(breed_path) / 1024
    print(f"  Saved -> {breed_path}  ({size_kb:.0f} KB)")

    print("Building age classifier...")
    age_model = _build_classifier("age", NUM_AGES, seed_offset=1000)
    onnx.save(age_model, age_path)
    size_kb = os.path.getsize(age_path) / 1024
    print(f"  Saved -> {age_path}  ({size_kb:.0f} KB)")

    # Verify they load in onnxruntime
    import onnxruntime as ort

    for path, label, expected_out in [
        (breed_path, "Breed", NUM_BREEDS),
        (age_path, "Age", NUM_AGES),
    ]:
        session = ort.InferenceSession(path)
        dummy = np.random.randn(1, 3, 224, 224).astype(np.float32)
        result = session.run(None, {"input_image": dummy})[0]
        assert result.shape == (1, expected_out), f"Unexpected shape: {result.shape}"
        print(f"  OK: {label} model verified -- output shape {result.shape}")

    print("\nDone! Both models are self-contained and load successfully.")


if __name__ == "__main__":
    main()
