#include "pharmakon_c.h"
#include "pharmakon_dsp.hpp"

struct PharmakonInstance {
    pharmakon::dsp::PharmakonEngine engine;
    float sampleRate{48000.0f};
};

PharmakonHandle pharmakon_create(float sampleRate) {
    auto* inst = new (std::nothrow) PharmakonInstance();
    if (!inst) return nullptr;
    inst->sampleRate = sampleRate;
    inst->engine.configure(sampleRate);
    return reinterpret_cast<PharmakonHandle>(inst);
}

void pharmakon_destroy(PharmakonHandle handle) {
    if (handle) {
        delete reinterpret_cast<PharmakonInstance*>(handle);
    }
}

void pharmakon_set_parameters(
    PharmakonHandle handle,
    float deharshDepth,
    float tapeDrive,
    float airGain,
    float subMonoDepth,
    bool deltaListen
) {
    if (!handle) return;
    auto* inst = reinterpret_cast<PharmakonInstance*>(handle);
    inst->engine.setDeHarshDepth(deharshDepth);
    inst->engine.setDeHarshDelta(deltaListen);
    inst->engine.setTapeDrive(tapeDrive);
    inst->engine.setAirGain(airGain);
    inst->engine.setSubMonoDepth(subMonoDepth);
}

void pharmakon_process_block(
    PharmakonHandle handle,
    float* leftChannel,
    float* rightChannel,
    int32_t numSamples
) {
    if (!handle || !leftChannel || !rightChannel || numSamples <= 0) return;
    auto* inst = reinterpret_cast<PharmakonInstance*>(handle);
    for (int32_t i = 0; i < numSamples; ++i) {
        inst->engine.processSample(leftChannel[i], rightChannel[i], leftChannel[i], rightChannel[i]);
    }
}

int32_t pharmakon_get_latency_samples(PharmakonHandle handle) {
    if (!handle) return 0;
    return static_cast<int32_t>(reinterpret_cast<PharmakonInstance*>(handle)->engine.getLatencySamples());
}
