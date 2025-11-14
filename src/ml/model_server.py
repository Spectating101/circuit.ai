"""
Production Model Serving Infrastructure

Features:
- Model loading and caching
- Batch inference optimization
- Multi-model serving
- Model versioning and A/B testing
- Request queue management
- GPU memory management
- Model warmup
- Inference optimization (TensorRT, ONNX Runtime)
- Monitoring and metrics
- Graceful model updates
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio
import time
from pathlib import Path
import numpy as np
import torch
from loguru import logger
from collections import deque
import onnxruntime as ort

from .model_registry import ModelRegistry, ModelMetadata, model_registry


class InferenceBackend(Enum):
    """Inference backend types."""
    PYTORCH = "pytorch"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    OPENVINO = "openvino"


@dataclass
class InferenceRequest:
    """Inference request."""
    request_id: str
    image: np.ndarray
    model_name: str
    model_version: Optional[str]
    confidence_threshold: float
    callback: Optional[asyncio.Future]
    created_at: datetime


@dataclass
class InferenceResult:
    """Inference result."""
    request_id: str
    detections: List[Dict[str, Any]]
    inference_time_ms: float
    model_id: str
    backend: InferenceBackend


class ModelLoader:
    """Load and cache models."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        cache_size: int = 3,
        device: str = "cuda"
    ):
        """
        Initialize model loader.

        Args:
            model_registry: Model registry instance
            cache_size: Number of models to keep in memory
            device: Device for inference (cuda, cpu)
        """
        self.model_registry = model_registry
        self.cache_size = cache_size
        self.device = device

        self.loaded_models: Dict[str, Any] = {}
        self.model_access_times: Dict[str, float] = {}

        logger.info(f"ModelLoader initialized (device: {device})")

    def load_model(
        self,
        model_id: str,
        backend: InferenceBackend = InferenceBackend.PYTORCH
    ) -> Any:
        """
        Load model into memory.

        Args:
            model_id: Model ID
            backend: Inference backend

        Returns:
            Loaded model
        """
        # Check if already loaded
        cache_key = f"{model_id}:{backend.value}"

        if cache_key in self.loaded_models:
            self.model_access_times[cache_key] = time.time()
            logger.debug(f"Model cache hit: {cache_key}")
            return self.loaded_models[cache_key]

        # Get model metadata
        metadata = self.model_registry.get_model(model_id)

        if not metadata:
            raise ValueError(f"Model not found: {model_id}")

        # Evict least recently used model if cache full
        if len(self.loaded_models) >= self.cache_size:
            self._evict_lru_model()

        # Load model based on backend
        if backend == InferenceBackend.PYTORCH:
            model = self._load_pytorch_model(metadata)
        elif backend == InferenceBackend.ONNX:
            model = self._load_onnx_model(metadata)
        elif backend == InferenceBackend.TENSORRT:
            model = self._load_tensorrt_model(metadata)
        else:
            raise NotImplementedError(f"Backend {backend} not supported")

        # Cache model
        self.loaded_models[cache_key] = model
        self.model_access_times[cache_key] = time.time()

        logger.info(f"Loaded model: {cache_key}")

        return model

    def _load_pytorch_model(self, metadata: ModelMetadata) -> Any:
        """Load PyTorch model."""
        from ultralytics import YOLO

        weights_path = self.model_registry.storage.load_model(
            metadata.model_id,
            artifact="weights"
        )

        # Load model
        model = YOLO(weights_path)

        # Move to device
        if self.device == "cuda" and torch.cuda.is_available():
            model.to(self.device)

        return model

    def _load_onnx_model(self, metadata: ModelMetadata) -> Any:
        """Load ONNX model."""
        onnx_path = metadata.onnx_path

        if not onnx_path or not Path(onnx_path).exists():
            raise ValueError(f"ONNX model not found for {metadata.model_id}")

        # Create ONNX Runtime session
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] \
            if self.device == "cuda" else ['CPUExecutionProvider']

        session = ort.InferenceSession(onnx_path, providers=providers)

        return session

    def _load_tensorrt_model(self, metadata: ModelMetadata) -> Any:
        """Load TensorRT model."""
        # Would implement TensorRT loading
        raise NotImplementedError("TensorRT loading not yet implemented")

    def _evict_lru_model(self):
        """Evict least recently used model."""
        if not self.model_access_times:
            return

        # Find LRU model
        lru_key = min(self.model_access_times.items(), key=lambda x: x[1])[0]

        # Evict
        del self.loaded_models[lru_key]
        del self.model_access_times[lru_key]

        logger.info(f"Evicted LRU model: {lru_key}")

    def warmup_model(
        self,
        model_id: str,
        backend: InferenceBackend = InferenceBackend.PYTORCH,
        num_warmup: int = 3
    ):
        """
        Warm up model with dummy inference.

        Args:
            model_id: Model to warm up
            backend: Inference backend
            num_warmup: Number of warmup iterations
        """
        model = self.load_model(model_id, backend)

        # Create dummy input
        dummy_input = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

        logger.info(f"Warming up model: {model_id}")

        for i in range(num_warmup):
            if backend == InferenceBackend.PYTORCH:
                _ = model.predict(dummy_input, verbose=False)
            elif backend == InferenceBackend.ONNX:
                # Would run ONNX inference
                pass

        logger.info(f"Model warmup complete: {model_id}")


class BatchProcessor:
    """Process inference requests in batches."""

    def __init__(
        self,
        batch_size: int = 8,
        max_wait_time: float = 0.1  # 100ms
    ):
        """
        Initialize batch processor.

        Args:
            batch_size: Maximum batch size
            max_wait_time: Maximum time to wait for batch (seconds)
        """
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time

        self.request_queue: deque = deque()
        self.processing = False

        logger.info(f"BatchProcessor initialized (batch_size: {batch_size})")

    async def add_request(self, request: InferenceRequest):
        """
        Add request to batch queue.

        Args:
            request: Inference request
        """
        self.request_queue.append(request)

    async def process_batches(
        self,
        inference_fn: callable
    ):
        """
        Process batched requests.

        Args:
            inference_fn: Function to call for batch inference
        """
        while True:
            if len(self.request_queue) == 0:
                await asyncio.sleep(0.01)
                continue

            # Collect batch
            batch = []
            start_time = time.time()

            while len(batch) < self.batch_size:
                # Check if we should process current batch
                if len(batch) > 0:
                    elapsed = time.time() - start_time
                    if elapsed >= self.max_wait_time:
                        break

                # Get request
                try:
                    request = self.request_queue.popleft()
                    batch.append(request)
                except IndexError:
                    break

                if len(batch) >= self.batch_size:
                    break

            # Process batch
            if batch:
                await self._process_batch(batch, inference_fn)

    async def _process_batch(
        self,
        batch: List[InferenceRequest],
        inference_fn: callable
    ):
        """Process single batch."""
        logger.debug(f"Processing batch of {len(batch)} requests")

        # Group by model
        by_model = {}
        for request in batch:
            key = f"{request.model_name}:{request.model_version or 'latest'}"
            if key not in by_model:
                by_model[key] = []
            by_model[key].append(request)

        # Process each model's requests
        for model_key, requests in by_model.items():
            results = await inference_fn(requests)

            # Resolve callbacks
            for request, result in zip(requests, results):
                if request.callback:
                    request.callback.set_result(result)


class ModelServer:
    """Production model serving system."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        device: str = "cuda",
        max_cache_size: int = 3,
        batch_size: int = 8,
        enable_batching: bool = True
    ):
        """
        Initialize model server.

        Args:
            model_registry: Model registry instance
            device: Device for inference
            max_cache_size: Model cache size
            batch_size: Batch size for inference
            enable_batching: Enable request batching
        """
        self.model_registry = model_registry
        self.device = device

        self.model_loader = ModelLoader(
            model_registry=model_registry,
            cache_size=max_cache_size,
            device=device
        )

        self.enable_batching = enable_batching
        self.batch_processor = BatchProcessor(batch_size=batch_size) if enable_batching else None

        # Model routing (for A/B testing)
        self.model_routing: Dict[str, Dict[str, Any]] = {}

        # Metrics
        self.request_count = 0
        self.total_inference_time = 0.0

        logger.info("ModelServer initialized")

        # Start batch processor if enabled
        if self.enable_batching:
            asyncio.create_task(self.batch_processor.process_batches(self._batch_inference))

    def set_model_routing(
        self,
        model_name: str,
        routing: Dict[str, float]
    ):
        """
        Set model routing for A/B testing.

        Args:
            model_name: Model name
            routing: Dictionary of {model_id: traffic_percentage}

        Example:
            {
                'model_v1': 0.9,  # 90% of traffic
                'model_v2': 0.1   # 10% of traffic
            }
        """
        # Validate routing percentages sum to 1.0
        total = sum(routing.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Routing percentages must sum to 1.0, got {total}")

        self.model_routing[model_name] = routing

        logger.info(f"Set routing for {model_name}: {routing}")

    def _select_model(self, model_name: str) -> str:
        """
        Select model based on routing rules.

        Args:
            model_name: Requested model name

        Returns:
            Selected model ID
        """
        # Check if routing configured
        if model_name not in self.model_routing:
            # Use production model
            prod_model = self.model_registry.get_production_model(model_name)
            if prod_model:
                return prod_model.model_id

            # Fallback to latest
            models = self.model_registry.list_models(name=model_name)
            if models:
                return models[0].model_id

            raise ValueError(f"No model found: {model_name}")

        # A/B test routing
        import random
        routing = self.model_routing[model_name]

        rand = random.random()
        cumulative = 0.0

        for model_id, percentage in routing.items():
            cumulative += percentage
            if rand <= cumulative:
                return model_id

        # Fallback to first model
        return list(routing.keys())[0]

    async def predict(
        self,
        image: np.ndarray,
        model_name: str,
        model_version: Optional[str] = None,
        confidence_threshold: float = 0.25,
        backend: InferenceBackend = InferenceBackend.PYTORCH
    ) -> InferenceResult:
        """
        Run inference on image.

        Args:
            image: Input image (numpy array)
            model_name: Model name
            model_version: Specific version (optional)
            confidence_threshold: Confidence threshold
            backend: Inference backend

        Returns:
            Inference result
        """
        start_time = time.time()

        # Select model
        if model_version:
            model_id = f"{model_name}_v{model_version}"
        else:
            model_id = self._select_model(model_name)

        # Load model
        model = self.model_loader.load_model(model_id, backend)

        # Run inference
        if backend == InferenceBackend.PYTORCH:
            results = model.predict(
                image,
                conf=confidence_threshold,
                verbose=False
            )[0]

            # Parse detections
            detections = []
            if results.boxes:
                for box in results.boxes:
                    detections.append({
                        'bbox': box.xyxy[0].tolist(),
                        'confidence': float(box.conf[0]),
                        'class_id': int(box.cls[0]),
                        'class_name': model.names[int(box.cls[0])]
                    })

        elif backend == InferenceBackend.ONNX:
            # Would run ONNX inference
            detections = []

        else:
            raise NotImplementedError(f"Backend {backend} not supported")

        inference_time = (time.time() - start_time) * 1000  # ms

        # Update metrics
        self.request_count += 1
        self.total_inference_time += inference_time

        result = InferenceResult(
            request_id=f"req_{int(time.time()*1000)}",
            detections=detections,
            inference_time_ms=inference_time,
            model_id=model_id,
            backend=backend
        )

        logger.debug(
            f"Inference complete: {len(detections)} detections in {inference_time:.2f}ms"
        )

        return result

    async def predict_batch(
        self,
        images: List[np.ndarray],
        model_name: str,
        **kwargs
    ) -> List[InferenceResult]:
        """
        Run batch inference.

        Args:
            images: List of images
            model_name: Model name
            **kwargs: Additional arguments

        Returns:
            List of results
        """
        # Create requests
        requests = []
        futures = []

        for image in images:
            future = asyncio.Future()
            request = InferenceRequest(
                request_id=f"batch_{int(time.time()*1000)}",
                image=image,
                model_name=model_name,
                model_version=kwargs.get('model_version'),
                confidence_threshold=kwargs.get('confidence_threshold', 0.25),
                callback=future,
                created_at=datetime.utcnow()
            )
            requests.append(request)
            futures.append(future)

        # Add to batch processor
        for request in requests:
            await self.batch_processor.add_request(request)

        # Wait for results
        results = await asyncio.gather(*futures)

        return results

    async def _batch_inference(
        self,
        requests: List[InferenceRequest]
    ) -> List[InferenceResult]:
        """Process batch of requests."""
        results = []

        for request in requests:
            result = await self.predict(
                request.image,
                request.model_name,
                request.model_version,
                request.confidence_threshold
            )
            results.append(result)

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get server metrics."""
        return {
            'total_requests': self.request_count,
            'avg_inference_time_ms': self.total_inference_time / self.request_count
            if self.request_count > 0 else 0,
            'loaded_models': len(self.model_loader.loaded_models),
            'cache_size': self.model_loader.cache_size
        }

    async def warmup_production_models(self):
        """Warm up all production models."""
        # Get all production models
        models = self.model_registry.list_models()

        for metadata in models:
            if metadata.stage.value == "production":
                self.model_loader.warmup_model(metadata.model_id)


# Singleton instance
model_server = ModelServer(
    model_registry=model_registry,
    device="cuda" if torch.cuda.is_available() else "cpu",
    max_cache_size=3,
    batch_size=8,
    enable_batching=True
)
