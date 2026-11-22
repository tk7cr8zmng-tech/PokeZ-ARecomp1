// Prepared module ABI data; build IDs bind a record to its module, not admission.
#pragma once
#include "rt.h"
#include <stdlib.h>
#define LUMIOSE_NATIVE_PROFILE_ENABLED 1
typedef struct {
    uint8_t build_id[32];
    uint32_t camera_query_returns[64];
    uint32_t camera_query_count;
    bool native_abi;
} LumioseNativeProfile;
static const LumioseNativeProfile lumiose_native_profiles[] = {
    {{0x84,0x68,0x44,0x91,0x19,0x9a,0x6b,0x91,0x80,0x72,0x58,0x02,0x55,0x8b,0x75,0xd9,0xc0,0xa0,0xd0,0xc4,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00},{0x152b0,0x15320,0x15400},3,true},
    {{0xd2,0xe9,0x4b,0x5e,0x81,0xe6,0xda,0x07,0x52,0x56,0xb5,0x15,0x95,0x2e,0x75,0xed,0x21,0x03,0xe3,0x2a,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00},{0x152b0,0x15320,0x15400},3,true},
    {{0xfe,0xd1,0xe6,0x4f,0xbb,0x84,0x79,0xba,0xa7,0x8e,0x4f,0x57,0xaf,0xda,0x7f,0x46,0x8c,0x7d,0x4a,0xd2,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00},{0x152b0,0x15320,0x15400},3,true},
    {{0x0f,0x59,0x5e,0xfe,0xd7,0xe8,0x26,0x86,0xfd,0x28,0x8a,0xd6,0x1b,0xec,0x0c,0x0f,0x68,0xf1,0xa4,0x08,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00},{0x1a300,0x1a370,0x1a450},3,true},
};

// LCP2: 8-byte magic, u32 ABI flags, u32 count, exact 32-byte NSO identity,
// then count u32 camera-query return offsets. Old native-only 44-byte records
// remain readable for already prepared versions. All words are little endian.
static LumioseNativeProfile lumiose_native_prepared_profile;
static bool lumiose_native_prepared_valid;
static pthread_once_t lumiose_native_prepared_once = PTHREAD_ONCE_INIT;
static inline uint32_t lumiose_profile_u32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static void lumiose_native_read_prepared_profile(void) {
    const char *path = getenv("LUMIOSE_NATIVE_PROFILE_PATH");
    if (!path || !*path) return;
    FILE *file = fopen(path, "rb");
    if (!file) return;
    uint8_t raw[48 + 64*4 + 1];
    size_t size = fread(raw, 1, sizeof raw, file);
    bool failed = ferror(file) != 0;
    fclose(file);
    if (failed) return;
    uint32_t count, flags;
    const uint8_t *id, *returns;
    if (size == 44) {
        count = 3; flags = 1; id = raw; returns = raw + 32;
    } else {
        static const uint8_t magic[8] = {'L','C','P','2',0,0,0,0};
        if (size < 48 || memcmp(raw, magic, sizeof magic)) return;
        flags = lumiose_profile_u32(raw + 8);
        count = lumiose_profile_u32(raw + 12);
        if ((flags & ~1u) || count > 64 || size != 48 + (size_t)count*4) return;
        id = raw + 16; returns = raw + 48;
    }
    uint8_t any = 0;
    for (unsigned i=0; i<32; ++i) any |= id[i];
    if (!any) return;
    memcpy(lumiose_native_prepared_profile.build_id, id, 32);
    for (unsigned i=0; i<count; ++i) {
        uint32_t value = lumiose_profile_u32(returns + 4*i);
        if (!value || (value & 3)) return;
        for (unsigned j=0; j<i; ++j)
            if (lumiose_native_prepared_profile.camera_query_returns[j] == value) return;
        lumiose_native_prepared_profile.camera_query_returns[i] = value;
    }
    lumiose_native_prepared_profile.camera_query_count = count;
    lumiose_native_prepared_profile.native_abi = (flags & 1) != 0;
    lumiose_native_prepared_valid = true;
}
static inline const LumioseNativeProfile *lumiose_native_prepared_current(void) {
    pthread_once(&lumiose_native_prepared_once, lumiose_native_read_prepared_profile);
    if (!lumiose_native_prepared_valid ||
        memcmp(g_modules[2].build_id, lumiose_native_prepared_profile.build_id, 32)) return NULL;
    uint64_t start = g_modules[2].text_off, end = start + g_modules[2].text_size;
    if (end <= start) return NULL;
    for (unsigned i=0; i<lumiose_native_prepared_profile.camera_query_count; ++i) {
        uint64_t offset = lumiose_native_prepared_profile.camera_query_returns[i];
        if (offset < start || offset >= end) return NULL;
    }
    return &lumiose_native_prepared_profile;
}
static inline const LumioseNativeProfile *lumiose_native_profile_current(void) {
    if (!LUMIOSE_NATIVE_PROFILE_ENABLED || g_nmodules <= 2) return NULL;
    const LumioseNativeProfile *prepared = lumiose_native_prepared_current();
    if (prepared) return prepared;
    // Backward compatibility for old prepared versions that have no record.
    for (unsigned i=0; i<sizeof lumiose_native_profiles/sizeof lumiose_native_profiles[0]; ++i)
        if (!memcmp(g_modules[2].build_id, lumiose_native_profiles[i].build_id, 32))
            return &lumiose_native_profiles[i];
    return NULL;
}
static inline bool lumiose_native_module(void) {
    const LumioseNativeProfile *p = lumiose_native_profile_current();
    return p && p->native_abi;
}
static inline bool lumiose_native_caller(uint64_t lr) {
    return lumiose_native_module() && lr >= g_modules[2].base + g_modules[2].text_off &&
        lr < g_modules[2].base + g_modules[2].text_off + g_modules[2].text_size;
}
static inline bool lumiose_native_camera_query(uint64_t lr) {
    const LumioseNativeProfile *profile = lumiose_native_profile_current();
    if (!profile) return false;
    uint64_t offset = lr - g_modules[2].base;
    for (unsigned i=0; i<profile->camera_query_count; ++i)
        if (offset == profile->camera_query_returns[i]) return true;
    return false;
}
