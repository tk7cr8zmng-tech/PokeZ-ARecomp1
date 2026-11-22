// The few Windows declarations windows_launcher.c uses, for building it with clang + lld alone
// (tools/lumiose/build_windows_launcher.sh). With MSYS2 / MinGW or MSVC, the real <windows.h> is used instead.
// Layouts follow the Windows SDK for x64.
#pragma once
#include <stddef.h>
#include <stdint.h>

#define WINAPI __stdcall
#define CALLBACK __stdcall
#define DECL __declspec(dllimport)
typedef int BOOL;
typedef unsigned char BYTE;
typedef unsigned short WORD, LANGID;
typedef unsigned long DWORD;
typedef unsigned int UINT;
typedef long LONG;
typedef unsigned long COLORREF;
typedef size_t SIZE_T;
typedef uintptr_t WPARAM, UINT_PTR, ULONG_PTR;
typedef intptr_t LPARAM, LRESULT;
typedef wchar_t *PWSTR, *LPWSTR;
typedef const wchar_t *LPCWSTR;
typedef void *HANDLE, *HINSTANCE, *HMODULE, *HWND, *HDC, *HBITMAP, *HFONT, *HGDIOBJ, *HICON, *HCURSOR, *HBRUSH, *HMENU;
typedef LRESULT(CALLBACK *WNDPROC)(HWND, UINT, WPARAM, LPARAM);
typedef void(CALLBACK *TIMERPROC)(HWND, UINT, UINT_PTR, DWORD);
#define FALSE 0
#define TRUE 1

typedef struct { LONG left, top, right, bottom; } RECT;
typedef struct { LONG x, y; } POINT;
typedef struct { LONG cx, cy; } SIZE;
typedef struct { WORD wYear, wMonth, wDayOfWeek, wDay, wHour, wMinute, wSecond, wMilliseconds; } SYSTEMTIME;
typedef struct {
    DWORD cb;
    LPWSTR lpReserved, lpDesktop, lpTitle;
    DWORD dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
    WORD wShowWindow, cbReserved2;
    BYTE *lpReserved2;
    HANDLE hStdInput, hStdOutput, hStdError;
} STARTUPINFOW;
typedef struct { HANDLE hProcess, hThread; DWORD dwProcessId, dwThreadId; } PROCESS_INFORMATION;
typedef struct {
    UINT cbSize, style;
    WNDPROC lpfnWndProc;
    int cbClsExtra, cbWndExtra;
    HINSTANCE hInstance;
    HICON hIcon;
    HCURSOR hCursor;
    HBRUSH hbrBackground;
    LPCWSTR lpszMenuName, lpszClassName;
    HICON hIconSm;
} WNDCLASSEXW;
typedef struct { HWND hwnd; UINT message; WPARAM wParam; LPARAM lParam; DWORD time; POINT pt; DWORD lPrivate; } MSG;
typedef struct { HDC hdc; BOOL fErase; RECT rcPaint; BOOL fRestore, fIncUpdate; BYTE rgbReserved[32]; } PAINTSTRUCT;
typedef struct {
    DWORD biSize;
    LONG biWidth, biHeight;
    WORD biPlanes, biBitCount;
    DWORD biCompression, biSizeImage;
    LONG biXPelsPerMeter, biYPelsPerMeter;
    DWORD biClrUsed, biClrImportant;
} BITMAPINFOHEADER;
typedef struct { BYTE rgbBlue, rgbGreen, rgbRed, rgbReserved; } RGBQUAD;
typedef struct { BITMAPINFOHEADER bmiHeader; RGBQUAD bmiColors[1]; } BITMAPINFO;

#define RGB(r, g, b) ((COLORREF)((BYTE)(r) | ((WORD)(BYTE)(g) << 8) | ((DWORD)(BYTE)(b) << 16)))
#define MAKEINTRESOURCEW(i) ((LPWSTR)(ULONG_PTR)(WORD)(i))
#define CREATE_NEW_CONSOLE 0x10
#define MB_OK 0x0
#define MB_ICONERROR 0x10
#define MEM_COMMIT 0x1000
#define MEM_RESERVE 0x2000
#define PAGE_READWRITE 0x04
#define WS_POPUP 0x80000000L
#define WS_EX_TOPMOST 0x8L
#define WS_EX_TOOLWINDOW 0x80L
#define WS_EX_LAYERED 0x80000L
#define LWA_ALPHA 0x2
#define SW_SHOW 5
#define SW_SHOWDEFAULT 10
#define SM_CXSCREEN 0
#define SM_CYSCREEN 1
#define LOGPIXELSY 90
#define WM_DESTROY 0x0002
#define WM_PAINT 0x000F
#define WM_ERASEBKGND 0x0014
#define WM_KEYDOWN 0x0100
#define WM_TIMER 0x0113
#define WM_LBUTTONDOWN 0x0201
#define WM_RBUTTONDOWN 0x0204
#define BI_RGB 0
#define DIB_RGB_COLORS 0
#define SRCCOPY 0x00CC0020
#define TRANSPARENT 1
#define FW_NORMAL 400
#define FW_SEMIBOLD 600
#define FW_BOLD 700
#define DEFAULT_CHARSET 1
#define OUT_DEFAULT_PRECIS 0
#define CLIP_DEFAULT_PRECIS 0
#define CLEARTYPE_QUALITY 5
#define DEFAULT_PITCH 0

// kernel32
DECL DWORD WINAPI GetModuleFileNameW(HMODULE, LPWSTR, DWORD);
DECL HMODULE WINAPI GetModuleHandleW(LPCWSTR);
DECL LPWSTR WINAPI GetCommandLineW(void);
DECL BOOL WINAPI CreateProcessW(LPCWSTR, LPWSTR, void *, void *, BOOL, DWORD, void *, LPCWSTR, STARTUPINFOW *, PROCESS_INFORMATION *);
DECL BOOL WINAPI CloseHandle(HANDLE);
DECL void WINAPI ExitProcess(UINT);
DECL DWORD WINAPI GetEnvironmentVariableW(LPCWSTR, LPWSTR, DWORD);
DECL void WINAPI GetLocalTime(SYSTEMTIME *);
DECL DWORD WINAPI GetTickCount(void);
DECL LANGID WINAPI GetUserDefaultUILanguage(void);
DECL void *WINAPI VirtualAlloc(void *, SIZE_T, DWORD, DWORD);
// user32
DECL int WINAPI MessageBoxW(HWND, LPCWSTR, LPCWSTR, UINT);
DECL BOOL WINAPI SetProcessDPIAware(void);
DECL HDC WINAPI GetDC(HWND);
DECL int WINAPI ReleaseDC(HWND, HDC);
DECL int WINAPI GetSystemMetrics(int);
DECL HICON WINAPI LoadIconW(HINSTANCE, LPCWSTR);
DECL HCURSOR WINAPI LoadCursorW(HINSTANCE, LPCWSTR);
DECL WORD WINAPI RegisterClassExW(const WNDCLASSEXW *);
DECL HWND WINAPI CreateWindowExW(DWORD, LPCWSTR, LPCWSTR, DWORD, int, int, int, int, HWND, HMENU, HINSTANCE, void *);
DECL BOOL WINAPI DestroyWindow(HWND);
DECL BOOL WINAPI ShowWindow(HWND, int);
DECL BOOL WINAPI UpdateWindow(HWND);
DECL BOOL WINAPI SetLayeredWindowAttributes(HWND, COLORREF, BYTE, DWORD);
DECL BOOL WINAPI InvalidateRect(HWND, const RECT *, BOOL);
DECL HDC WINAPI BeginPaint(HWND, PAINTSTRUCT *);
DECL BOOL WINAPI EndPaint(HWND, const PAINTSTRUCT *);
DECL UINT_PTR WINAPI SetTimer(HWND, UINT_PTR, UINT, TIMERPROC);
DECL BOOL WINAPI GetMessageW(MSG *, HWND, UINT, UINT);
DECL BOOL WINAPI TranslateMessage(const MSG *);
DECL LRESULT WINAPI DispatchMessageW(const MSG *);
DECL void WINAPI PostQuitMessage(int);
DECL LRESULT WINAPI DefWindowProcW(HWND, UINT, WPARAM, LPARAM);
// gdi32
DECL HDC WINAPI CreateCompatibleDC(HDC);
DECL HBITMAP WINAPI CreateDIBSection(HDC, const BITMAPINFO *, UINT, void **, HANDLE, DWORD);
DECL HGDIOBJ WINAPI SelectObject(HDC, HGDIOBJ);
DECL int WINAPI GetDeviceCaps(HDC, int);
DECL int WINAPI SetBkMode(HDC, int);
DECL COLORREF WINAPI SetTextColor(HDC, COLORREF);
DECL BOOL WINAPI TextOutW(HDC, int, int, LPCWSTR, int);
DECL BOOL WINAPI GetTextExtentPoint32W(HDC, LPCWSTR, int, SIZE *);
DECL HFONT WINAPI CreateFontW(int, int, int, int, int, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, LPCWSTR);
DECL BOOL WINAPI BitBlt(HDC, int, int, int, int, HDC, int, int, DWORD);
DECL BOOL WINAPI GdiFlush(void);
