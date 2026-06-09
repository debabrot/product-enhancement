import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from app.core.logging import logger


def setup_tracing(app, service_name, jaeger_endpoint):
    """Configure OpenTelemetry tracing with Jaeger OTLP exporter."""
    
    
    # Define the service resource
    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: "0.1.0",
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    
    # Configure OTLP exporter (sends to Jaeger)
    otlp_exporter = OTLPSpanExporter(
        endpoint=jaeger_endpoint,
        insecure=True,  # Use True for local dev without TLS
    )
    
    # Add span processor
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Instrument FastAPI automatically
    FastAPIInstrumentor.instrument_app(app)
    
    logger.info(f"Tracing initialized: service={service_name}, endpoint={jaeger_endpoint}")
    return provider