// Seasonal splash for Lumiose Online.exe (tools/lumiose/windows_launcher.c): the picture behind the greeting, drawn into
// a 32-bit 0x00RRGGBB pixel buffer. Plain C with no C library (the launcher is built without one), so the same code
// also runs in a native preview program. Nothing here comes from the game: shapes and colours only.
#pragma once
#include <stdint.h>

enum { SPLASH_NONE, SPLASH_THANKSGIVING };

#define SPLASH_PI 3.14159265f

static float sp_floor(float x) { int i = (int)x; return (float)(i - (x < (float)i)); }
static float sp_fmod(float a, float b) { return a - b * sp_floor(a / b); }
static float sp_sin(float x) {  // (a parabola fit with one refinement: within 0.001, plenty for drifting leaves)
    x = sp_fmod(x + SPLASH_PI, 2 * SPLASH_PI) - SPLASH_PI;
    float y = 1.27323954f * x - 0.405284735f * x * (x < 0 ? -x : x);
    return 0.225f * (y * (y < 0 ? -y : y) - y) + y;
}
static float sp_cos(float x) { return sp_sin(x + SPLASH_PI / 2); }
static float sp_rand(int i, int salt) {  // 0..1, fixed per particle
    uint32_t h = (uint32_t)i * 2654435761u ^ (uint32_t)salt * 2246822519u;
    h ^= h >> 15, h *= 2246822507u, h ^= h >> 13, h *= 3266489909u, h ^= h >> 16;
    return (h & 0xffffff) / (float)0xffffff;
}

typedef struct { uint32_t *px; int w, h; float s; } SplashCanvas;  // s: pixels per layout unit (layout: 720 x 405)

static void sp_blend(uint32_t *p, int r, int g, int b, int a) {  // a: 0..256
    uint32_t d = *p;
    int dr = (d >> 16) & 255, dg = (d >> 8) & 255, db = d & 255;
    dr += ((r - dr) * a) >> 8, dg += ((g - dg) * a) >> 8, db += ((b - db) * a) >> 8;
    *p = (uint32_t)(dr << 16 | dg << 8 | db);
}

// a convex polygon in pixels, antialiased by 3 x 3 samples per pixel; alpha 0..255
static void sp_poly(SplashCanvas *c, const float *xy, int n, int r, int g, int b, int alpha) {
    float x0 = xy[0], x1 = xy[0], y0 = xy[1], y1 = xy[1], area = 0;
    for (int i = 0; i < n; i++) {
        float x = xy[2 * i], y = xy[2 * i + 1];
        x0 = x < x0 ? x : x0, x1 = x > x1 ? x : x1, y0 = y < y0 ? y : y0, y1 = y > y1 ? y : y1;
        int j = (i + 1) % n;
        area += x * xy[2 * j + 1] - xy[2 * j] * y;
    }
    float dir = area < 0 ? -1.f : 1.f;
    int px0 = (int)sp_floor(x0), px1 = (int)x1 + 1, py0 = (int)sp_floor(y0), py1 = (int)y1 + 1;
    if (px0 < 0) px0 = 0;
    if (py0 < 0) py0 = 0;
    if (px1 > c->w) px1 = c->w;
    if (py1 > c->h) py1 = c->h;
    for (int py = py0; py < py1; py++)
        for (int px = px0; px < px1; px++) {
            int hits = 0;
            for (int sy = 0; sy < 3; sy++)
                for (int sx = 0; sx < 3; sx++) {
                    float x = px + (sx + .5f) / 3, y = py + (sy + .5f) / 3;
                    int in = 1;
                    for (int i = 0; i < n && in; i++) {
                        int j = (i + 1) % n;
                        float ex = xy[2 * j] - xy[2 * i], ey = xy[2 * j + 1] - xy[2 * i + 1];
                        if (dir * (ex * (y - xy[2 * i + 1]) - ey * (x - xy[2 * i])) < 0) in = 0;
                    }
                    hits += in;
                }
            if (hits) sp_blend(&c->px[py * c->w + px], r, g, b, alpha * hits * 256 / (9 * 255));
        }
}

// a soft round glow: alpha falls off as (1 - d^2 / R^2)^2
static void sp_glow(SplashCanvas *c, float cx, float cy, float R, int r, int g, int b, int alpha) {
    int y0 = (int)(cy - R), y1 = (int)(cy + R) + 1, x0 = (int)(cx - R), x1 = (int)(cx + R) + 1;
    if (y0 < 0) y0 = 0;
    if (x0 < 0) x0 = 0;
    if (y1 > c->h) y1 = c->h;
    if (x1 > c->w) x1 = c->w;
    float r2 = R * R;
    for (int y = y0; y < y1; y++)
        for (int x = x0; x < x1; x++) {
            float dx = x + .5f - cx, dy = y + .5f - cy, k = 1 - (dx * dx + dy * dy) / r2;
            if (k > 0) sp_blend(&c->px[y * c->w + x], r, g, b, (int)(alpha * k * k * 256 / 255));
        }
}

static void sp_rect(SplashCanvas *c, float x0, float y0, float x1, float y1, int r, int g, int b, int alpha) {
    float q[8] = {x0, y0, x1, y0, x1, y1, x0, y1};
    sp_poly(c, q, 4, r, g, b, alpha);
}

// the backdrop: drawn once per window size (the caller keeps a copy and restores it every frame)
static void splash_background(SplashCanvas *c, int season) {
    (void)season;
    float s = c->s;
    for (int y = 0; y < c->h; y++) {  // dusk: deep plum at the top to amber at the horizon
        float t = (float)y / (c->h - 1);
        int r, g, b;
        if (t < .6f) {
            float u = t / .6f;
            r = (int)(20 + 48 * u), g = (int)(18 + 22 * u), b = (int)(40 + 22 * u);
        } else {
            float u = (t - .6f) / .4f;
            r = (int)(68 + 110 * u), g = (int)(40 + 52 * u), b = (int)(62 - 14 * u);
        }
        for (int x = 0; x < c->w; x++) c->px[y * c->w + x] = (uint32_t)(r << 16 | g << 8 | b);
    }
    sp_glow(c, c->w * .74f, c->h * 1.02f, c->w * .62f, 255, 166, 72, 120);  // the low sun's glow
    for (int i = 0; i < 26; i++) {  // a few early stars, high up
        float x = sp_rand(i, 40) * c->w, y = sp_rand(i, 41) * c->h * .42f;
        sp_glow(c, x, y, (1.2f + sp_rand(i, 42) * 1.4f) * s, 255, 240, 220, (int)(120 + 120 * sp_rand(i, 43)));
    }
    // a generic tower and two rows of rooftops (not any real building)
    float tx = 520 * s, base = 405 * s;
    float tower[] = {tx - 9 * s, base, tx - 9 * s, 210 * s, tx - 4 * s, 170 * s, tx, 96 * s, tx + 4 * s, 170 * s,
                     tx + 9 * s, 210 * s, tx + 9 * s, base};
    sp_poly(c, tower, 7, 46, 28, 40, 255);
    sp_glow(c, tx, 97 * s, 7 * s, 255, 214, 130, 255);
    for (int i = 0; i < 18; i++) {
        float x0 = i * 42 * s - 10 * s, w = (34 + sp_rand(i, 50) * 30) * s, top = (300 + sp_rand(i, 51) * 50) * s;
        sp_rect(c, x0, top, x0 + w, base, 46, 28, 40, 255);
    }
    for (int i = 0; i < 14; i++) {
        float x0 = i * 56 * s - 20 * s, w = (40 + sp_rand(i, 60) * 34) * s, top = (336 + sp_rand(i, 61) * 36) * s;
        sp_rect(c, x0, top, x0 + w, base, 26, 16, 26, 255);
        for (int k = 0; k < 4; k++)  // lit windows
            if (sp_rand(i * 4 + k, 62) > .45f) {
                float wx = x0 + (6 + sp_rand(i * 4 + k, 63) * (w / s - 14)) * s, wy = top + (8 + k * 13) * s;
                if (wy + 6 * s < base) sp_rect(c, wx, wy, wx + 4 * s, wy + 6 * s, 255, 196, 110, 150 + (int)(90 * sp_rand(i * 4 + k, 64)));
            }
    }
    for (int y = 0; y < c->h; y++)  // the left side a little darker under the greeting
        for (int x = 0; x < c->w * 6 / 10; x++) {
            float k = 1 - (float)x / (c->w * .6f);
            sp_blend(&c->px[y * c->w + x], 12, 8, 20, (int)(110 * k));
        }
    for (int x = 0; x < c->w; x++)  // a thin border
        c->px[x] = c->px[(c->h - 1) * c->w + x] = 0x8a6a3a;
    for (int y = 0; y < c->h; y++) c->px[y * c->w] = c->px[y * c->w + c->w - 1] = 0x8a6a3a;
}

// an autumn leaf: a pointed oval with a stem, `len` pixels long, turned by `ang`
static void splash_leaf(SplashCanvas *c, float x, float y, float len, float ang, uint32_t rgb) {
    static const float shape[8][2] = {{1, 0}, {.55f, .34f}, {0, .42f}, {-.55f, .3f}, {-.9f, 0}, {-.55f, -.3f}, {0, -.42f}, {.55f, -.34f}};
    float co = sp_cos(ang), si = sp_sin(ang), pts[16];
    for (int i = 0; i < 8; i++) {
        float px = shape[i][0] * len / 2, py = shape[i][1] * len / 2;
        pts[2 * i] = x + px * co - py * si, pts[2 * i + 1] = y + px * si + py * co;
    }
    sp_poly(c, pts, 8, (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255, 235);
    float hw = len * .035f + .35f, nx = -si * hw, ny = co * hw;  // the stem: a thin quad behind the tip
    float a = -len * .45f, b = -len * .74f;
    float stem[8] = {x + a * co + nx, y + a * si + ny, x + b * co + nx, y + b * si + ny,
                     x + b * co - nx, y + b * si - ny, x + a * co - nx, y + a * si - ny};
    sp_poly(c, stem, 4, 110, 60, 25, 220);
    float v = len * .42f, vein[8] = {x - v * co + nx * .6f, y - v * si + ny * .6f, x + v * co + nx * .6f, y + v * si + ny * .6f,
                                     x + v * co - nx * .6f, y + v * si - ny * .6f, x - v * co - nx * .6f, y - v * si - ny * .6f};
    sp_poly(c, vein, 4, 90, 45, 15, 110);
}

// one frame's moving part, over the restored backdrop; t: seconds
static void splash_frame(SplashCanvas *c, int season, float t) {
    if (season != SPLASH_THANKSGIVING) return;
    static const uint32_t colors[5] = {0xe88c2c, 0xcc4e26, 0xf2ba46, 0xa85c2a, 0xdc701e};
    float s = c->s, W = c->w / s, H = c->h / s;
    for (int i = 0; i < 30; i++) {
        float speed = 26 + sp_rand(i, 1) * 30, size = 16 + sp_rand(i, 2) * 16;
        float y = sp_fmod(t * speed + sp_rand(i, 3) * (H + 60), H + 60) - 30;
        float x = sp_rand(i, 4) * W + sp_sin(t * (0.5f + sp_rand(i, 5) * 0.6f) + i) * (16 + sp_rand(i, 6) * 24);
        float ang = t * (sp_rand(i, 7) - 0.5f) * 1.8f + sp_rand(i, 8) * 6.283f;
        splash_leaf(c, x * s, y * s, size * s, ang, colors[i % 5]);
    }
}
