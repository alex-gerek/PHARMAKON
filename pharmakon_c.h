#ifndef PHARMAKON_C_H
#define PHARMAKON_C_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
    #if defined(PHARMAKON_BUILD_DLL)
        #define PHARMAKON_API __declspec(dllexport)
    #else
        #define PHARMAKON_API __declspec(dllimport)
    #endif
#else
    #define PHARMAKON_API __attribute__((visibility("default")))
#endif

typedef struct PharmakonInstance* PharmakonHandle;

PHARMAKON_API PharmakonHandle pharmakon_create(float sampleRate);
PHARMAKON_API void pharmakon_destroy(PharmakonHandle handle);

PHARMAKON_API void pharmakon_set_parameters(
    PharmakonHandle handle,
    float deharshDepth,
    float tapeDrive,
    float airGain,
    float subMonoDepth,
    bool deltaListen
);

PHARMAKON_API void pharmakon_process_block(
    PharmakonHandle handle,
    float* leftChannel,
    float* rightChannel,
    int32_t numSamples
);

PHARMAKON_API int32_t pharmakon_get_latency_samples(PharmakonHandle handle);

#ifdef __cplusplus
}
#endif

#endif // PHARMAKON_C_H
