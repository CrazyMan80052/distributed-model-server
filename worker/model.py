from __future__ import annotations

import pathlib
from typing import Protocol

import numpy as np


class ModelInterface(Protocol):
    def predict_batch(self, texts: list[str]) -> tuple[list[tuple[str, float]], float, float, float]:
        ...


class FakeModel:
    def __init__(self) -> None:
        pass

    def predict_batch(self, texts: list[str]) -> tuple[list[tuple[str, float]], float, float, float]:
        results = []
        for text in texts:
            # Deterministic dummy scoring based on text
            positive_score = 0.95 if "love" in text.lower() or "good" in text.lower() else 0.10
            label = "positive" if positive_score >= 0.5 else "negative"
            results.append((label, positive_score))
        return results, 0.1, 0.5, 0.1


class ONNXModel:
    def __init__(self, model_dir: str | pathlib.Path, intra_op_threads: int = 1, inter_op_threads: int = 1) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_dir = pathlib.Path(model_dir)
        tokenizer_path = model_dir / "tokenizer.json"
        onnx_path = model_dir / "model.onnx"

        if not tokenizer_path.exists() or not onnx_path.exists():
            raise FileNotFoundError(f"Model files missing in {model_dir}")

        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.enable_truncation(max_length=128)
        self.tokenizer.enable_padding(direction="right")

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = intra_op_threads
        opts.inter_op_num_threads = inter_op_threads
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        self.session = ort.InferenceSession(str(onnx_path), sess_options=opts)
        self.input_names = [inp.name for inp in self.session.get_inputs()]

    def predict_batch(self, texts: list[str]) -> tuple[list[tuple[str, float]], float, float, float]:
        import time

        if not texts:
            return [], 0.0, 0.0, 0.0

        t0 = time.perf_counter()
        encodings = self.tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        token_type_ids = np.array([e.type_ids for e in encodings], dtype=np.int64)

        inputs = {}
        if "input_ids" in self.input_names:
            inputs["input_ids"] = input_ids
        if "attention_mask" in self.input_names:
            inputs["attention_mask"] = attention_mask
        if "token_type_ids" in self.input_names:
            inputs["token_type_ids"] = token_type_ids

        t1 = time.perf_counter()
        outputs = self.session.run(None, inputs)
        logits = outputs[0]  # shape: (batch_size, 2)
        t2 = time.perf_counter()

        # Stable softmax
        max_logits = np.max(logits, axis=-1, keepdims=True)
        exp_logits = np.exp(logits - max_logits)
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)

        results: list[tuple[str, float]] = []
        for prob in probs:
            pos_score = float(prob[1])
            label = "positive" if pos_score >= 0.5 else "negative"
            results.append((label, pos_score))

        t3 = time.perf_counter()
        preprocess_ms = (t1 - t0) * 1000.0
        inference_ms = (t2 - t1) * 1000.0
        postprocess_ms = (t3 - t2) * 1000.0

        return results, preprocess_ms, inference_ms, postprocess_ms
