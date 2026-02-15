/**
 * OpenTelemetry Stub Module
 *
 * This is an empty stub for OpenTelemetry modules used by aioncli-core.
 * Telemetry is optional and not needed for HiveMind's core functionality.
 */

// Export empty objects to satisfy imports
export const metrics = {};
export const trace = {};
export const context = {};
export const propagation = {};
export const diag = {};
export const api = {};

// Default export
export default {};

// Export common classes as no-op
export class Meter {
  createCounter() { return { add: () => {} }; }
  createHistogram() { return { record: () => {} }; }
  createUpDownCounter() { return { add: () => {} }; }
  createObservableGauge() { return { addCallback: () => {} }; }
}

export class MeterProvider {
  getMeter() { return new Meter(); }
  shutdown() { return Promise.resolve(); }
  forceFlush() { return Promise.resolve(); }
}

export class TracerProvider {
  getTracer() { return { startSpan: () => ({}) }; }
  shutdown() { return Promise.resolve(); }
  forceFlush() { return Promise.resolve(); }
}

export class LoggerProvider {
  getLogger() { return { emit: () => {} }; }
  shutdown() { return Promise.resolve(); }
  forceFlush() { return Promise.resolve(); }
}

// Export common functions as no-op
export const getNodeAutoInstrumentations = () => [];
export const registerInstrumentations = () => {};
