// Windows entry point: the visible launcher and updater are shipped together.
// In season it also shows a short greeting (splash_draw.h) while the launcher starts behind it: never a wait - the
// launcher is started first, and a click or key closes the greeting at once.
//   Season: by the local date (Thanksgiving: 15-30 November); LARECOMP_SEASON=thanksgiving|off overrides it.
//   "Lumiose Online.exe" --splash-test: the greeting alone, without starting the launcher.
// No C library is needed (tools/lumiose/build_windows_launcher.sh builds it with clang and lld only).
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "splash_draw.h"

#ifndef LUMIOSE_NO_CRT
#include <string.h>
#else
int _fltused = 0;
void *memset(void *d, int v, size_t n) { unsigned char *p = (unsigned char *)d; while (n--) *p++ = (unsigned char)v; return d; }
void *memcpy(void *d, const void *s, size_t n) { unsigned char *p = (unsigned char *)d; const unsigned char *q = (const unsigned char *)s; while (n--) *p++ = *q++; return d; }
#endif

#define PATH_CHARS 32768
static wchar_t g_dir[PATH_CHARS], g_python[PATH_CHARS], g_args[2 * PATH_CHARS + 64];

static int wlen(const wchar_t *s) { int n = 0; while (s[n]) n++; return n; }
static int wcat(wchar_t *dst, int cap, const wchar_t *src) {  // 0: didn't fit
    int n = wlen(dst), m = wlen(src);
    if (n + m >= cap) return 0;
    for (int i = 0; i <= m; i++) dst[n + i] = src[i];
    return 1;
}
static int wsame(const wchar_t *a, const wchar_t *b) { while (*a && *a == *b) a++, b++; return *a == *b; }

static int start_launcher(void) {
    DWORD n = GetModuleFileNameW(NULL, g_dir, PATH_CHARS);
    if (!n || n >= PATH_CHARS) return 0;
    wchar_t *slash = NULL;
    for (wchar_t *p = g_dir; *p; p++)
        if (*p == L'\\') slash = p;
    if (!slash) return 0;
    *slash = 0;
    g_python[0] = g_args[0] = 0;
    if (!wcat(g_python, PATH_CHARS, g_dir) || !wcat(g_python, PATH_CHARS, L"\\python\\python.exe") ||
        !wcat(g_args, 2 * PATH_CHARS + 64, L"\"") || !wcat(g_args, 2 * PATH_CHARS + 64, g_python) ||
        !wcat(g_args, 2 * PATH_CHARS + 64, L"\" \"") || !wcat(g_args, 2 * PATH_CHARS + 64, g_dir) ||
        !wcat(g_args, 2 * PATH_CHARS + 64, L"\\tools\\lumiose\\entry.py\"")) return 0;
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    memset(&si, 0, sizeof si), memset(&pi, 0, sizeof pi);
    si.cb = sizeof si;
    if (!CreateProcessW(g_python, g_args, NULL, NULL, FALSE, CREATE_NEW_CONSOLE, NULL, g_dir, &si, &pi)) return 0;
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 1;
}

static int season_now(void) {
    wchar_t env[32];
    DWORD n = GetEnvironmentVariableW(L"LARECOMP_SEASON", env, 32);
    if (n && n < 32 && !wsame(env, L"auto")) return wsame(env, L"thanksgiving") ? SPLASH_THANKSGIVING : SPLASH_NONE;
    SYSTEMTIME st;
    GetLocalTime(&st);
    if (st.wMonth == 11 && st.wDay >= 15) return SPLASH_THANKSGIVING;  // (US Thanksgiving: 4th Thursday, 22-28 November)
    return SPLASH_NONE;
}

// ------------------------------------------------------------------ the greeting window
#define SPLASH_MS 4200
#define FADE_IN_MS 250
#define FADE_OUT_MS 450
static int g_season;
static SplashCanvas g_canvas;
static uint32_t *g_backdrop;
static HDC g_mem;
static HBITMAP g_bmp;
static HFONT g_font_big, g_font_mid, g_font_small;
static DWORD g_start;
static int g_pt;  // Portuguese system language

static void draw_text(HFONT font, int x, int y, COLORREF color, const wchar_t *t) {
    SelectObject(g_mem, font);
    SetTextColor(g_mem, RGB(10, 6, 14));
    TextOutW(g_mem, x + 2, y + 2, t, wlen(t));
    SetTextColor(g_mem, color);
    TextOutW(g_mem, x, y, t, wlen(t));
}

static void render(void) {
    float t = (GetTickCount() - g_start) / 1000.0f;
    GdiFlush();
    memcpy(g_canvas.px, g_backdrop, (size_t)g_canvas.w * g_canvas.h * 4);
    splash_frame(&g_canvas, g_season, t + 30);  // (+30 s: the leaves already spread over the picture)
    float s = g_canvas.s;
    const wchar_t *big = g_pt ? L"Feliz Dia de Ação de Graças!" : L"Happy Thanksgiving!";
    const wchar_t *mid = g_pt ? L"do Lumiose Online" : L"from Lumiose Online";
    const wchar_t *start = g_pt ? L"Iniciando o Lumiose Online…" : L"Starting Lumiose Online…";
    const wchar_t *skip = g_pt ? L"Clique para pular" : L"Click to skip";
    draw_text(g_font_big, (int)(40 * s), (int)(112 * s), RGB(255, 226, 170), big);
    draw_text(g_font_mid, (int)(42 * s), (int)(170 * s), RGB(255, 196, 120), mid);
    draw_text(g_font_small, (int)(42 * s), (int)(366 * s), RGB(220, 205, 190), start);
    SIZE sz;
    SelectObject(g_mem, g_font_small);
    GetTextExtentPoint32W(g_mem, skip, wlen(skip), &sz);
    draw_text(g_font_small, g_canvas.w - (int)(24 * s) - sz.cx, (int)(366 * s), RGB(190, 170, 150), skip);
}

static LRESULT CALLBACK splash_proc(HWND w, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_TIMER: {
        DWORD ms = GetTickCount() - g_start;
        if (ms >= SPLASH_MS) { DestroyWindow(w); return 0; }
        int a = ms < FADE_IN_MS ? (int)(255 * ms / FADE_IN_MS)
                : ms > SPLASH_MS - FADE_OUT_MS ? (int)(255 * (SPLASH_MS - ms) / FADE_OUT_MS) : 255;
        render();
        SetLayeredWindowAttributes(w, 0, (BYTE)a, LWA_ALPHA);
        InvalidateRect(w, NULL, FALSE);
        return 0;
    }
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(w, &ps);
        BitBlt(dc, 0, 0, g_canvas.w, g_canvas.h, g_mem, 0, 0, SRCCOPY);
        EndPaint(w, &ps);
        return 0;
    }
    case WM_ERASEBKGND: return 1;
    case WM_LBUTTONDOWN: case WM_RBUTTONDOWN: case WM_KEYDOWN: DestroyWindow(w); return 0;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(w, msg, wp, lp);
}

static HFONT make_font(int px, int weight) {
    return CreateFontW(-px, 0, 0, 0, weight, 0, 0, 0, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                       CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
}

static void show_splash(HINSTANCE inst, int season) {
    SetProcessDPIAware();  // (sharp on scaled displays: this process only)
    HDC screen = GetDC(NULL);
    int dpi = GetDeviceCaps(screen, LOGPIXELSY);
    ReleaseDC(NULL, screen);
    int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
    float s = (dpi > 0 ? dpi : 96) / 96.0f;
    if (720 * s > sw * 0.8f) s = sw * 0.8f / 720;  // (never wider than most of the screen)
    int w = (int)(720 * s), h = (int)(405 * s);
    if (w < 64 || h < 36) return;

    BITMAPINFO bi;
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = w, bi.bmiHeader.biHeight = -h;  // (top-down rows)
    bi.bmiHeader.biPlanes = 1, bi.bmiHeader.biBitCount = 32, bi.bmiHeader.biCompression = BI_RGB;
    void *bits = NULL;
    g_mem = CreateCompatibleDC(NULL);
    g_bmp = g_mem ? CreateDIBSection(g_mem, &bi, DIB_RGB_COLORS, &bits, NULL, 0) : NULL;
    g_backdrop = (uint32_t *)VirtualAlloc(NULL, (SIZE_T)w * h * 4, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!g_bmp || !bits || !g_backdrop) return;  // (no greeting this time: the launcher runs anyway)
    SelectObject(g_mem, g_bmp);
    SetBkMode(g_mem, TRANSPARENT);
    g_canvas.px = g_backdrop, g_canvas.w = w, g_canvas.h = h, g_canvas.s = s;
    splash_background(&g_canvas, season);
    g_canvas.px = (uint32_t *)bits;
    g_season = season;
    g_pt = (GetUserDefaultUILanguage() & 0x3ff) == 0x16;  // LANG_PORTUGUESE
    g_font_big = make_font((int)(44 * s), FW_BOLD);
    g_font_mid = make_font((int)(24 * s), FW_SEMIBOLD);
    g_font_small = make_font((int)(14 * s), FW_NORMAL);

    WNDCLASSEXW wc;
    memset(&wc, 0, sizeof wc);
    wc.cbSize = sizeof wc;
    wc.lpfnWndProc = splash_proc;
    wc.hInstance = inst;
    wc.hIcon = LoadIconW(inst, MAKEINTRESOURCEW(1));
    wc.hCursor = LoadCursorW(NULL, MAKEINTRESOURCEW(32649));  // IDC_HAND: clicking closes it
    wc.lpszClassName = L"LumioseSeasonalGreeting";
    if (!RegisterClassExW(&wc)) return;
    HWND win = CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED, wc.lpszClassName, L"Lumiose Online",
                               WS_POPUP, (sw - w) / 2, (sh - h) / 2, w, h, NULL, NULL, inst, NULL);
    if (!win) return;
    g_start = GetTickCount();
    render();
    SetLayeredWindowAttributes(win, 0, 0, LWA_ALPHA);
    ShowWindow(win, SW_SHOW);
    UpdateWindow(win);
    SetTimer(win, 1, 15, NULL);
    MSG m;
    while (GetMessageW(&m, NULL, 0, 0) > 0) {
        TranslateMessage(&m);
        DispatchMessageW(&m);
    }
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command, int show) {
    (void)previous; (void)show;
    int test = 0;
    for (const wchar_t *p = command; p && *p; p++)
        if (*p == L'-' && wsame(p, L"--splash-test")) test = 1;
    if (!test && !start_launcher()) {
        MessageBoxW(NULL, L"The Lumiose launcher could not start its bundled tools. Extract the whole release zip and try again.",
                    L"Lumiose Online", MB_OK | MB_ICONERROR);
        return 1;
    }
    int season = season_now();
    if (test && season == SPLASH_NONE) season = SPLASH_THANKSGIVING;
    if (season != SPLASH_NONE) show_splash(instance, season);
    return 0;
}

#ifdef LUMIOSE_NO_CRT
void wWinMainCRTStartup(void) {
    const wchar_t *cmd = GetCommandLineW();  // past the program's own name (quoted or not)
    if (*cmd == L'"') { cmd++; while (*cmd && *cmd != L'"') cmd++; if (*cmd) cmd++; }
    else while (*cmd && *cmd != L' ' && *cmd != L'\t') cmd++;
    while (*cmd == L' ' || *cmd == L'\t') cmd++;
    ExitProcess((UINT)wWinMain(GetModuleHandleW(NULL), NULL, (PWSTR)cmd, SW_SHOWDEFAULT));
}
#endif
