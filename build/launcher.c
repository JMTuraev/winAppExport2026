/* EksportMonitor.exe — tiny native launcher.
   Finds ..\EksportMonitor\python\pythonw.exe next to this AppWin folder, sets PYTHONPATH and starts
   `pythonw.exe -m appwin.desktop` with the working directory = AppWin. No console window.
   Build (MinGW): x86_64-w64-mingw32-windres app.rc -O coff -o app.res
                  x86_64-w64-mingw32-gcc -O2 -mwindows -municode launcher.c app.res -o EksportMonitor.exe -lshlwapi -static */
#include <windows.h>
#include <shlwapi.h>
#include <string.h>

#define BUF 4096

static void die(const wchar_t *msg) { MessageBoxW(NULL, msg, L"Eksport Monitor", MB_ICONERROR | MB_OK); }

static void cat(wchar_t *dst, const wchar_t *src) { wcsncat(dst, src, BUF - wcslen(dst) - 1); }

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE hPrev, PWSTR cmdLine, int nShow) {
    wchar_t app[BUF], legacy[BUF], py[BUF], pypath[BUF], cmd[BUF], msg[BUF];
    ZeroMemory(app, sizeof(app)); ZeroMemory(legacy, sizeof(legacy)); ZeroMemory(py, sizeof(py));
    ZeroMemory(pypath, sizeof(pypath)); ZeroMemory(cmd, sizeof(cmd)); ZeroMemory(msg, sizeof(msg));

    GetModuleFileNameW(NULL, app, BUF - 1);
    PathRemoveFileSpecW(app);                                    /* ...\AppWin */

    /* legacy = <parent of AppWin>\EksportMonitor, or AppWin\EksportMonitor if bundled */
    wcscpy(legacy, app); PathRemoveFileSpecW(legacy); cat(legacy, L"\\EksportMonitor");
    if (!PathFileExistsW(legacy)) { wcscpy(legacy, app); cat(legacy, L"\\EksportMonitor"); }

    int console = (cmdLine != NULL && wcsstr(cmdLine, L"--console") != NULL);
    wcscpy(py, legacy); cat(py, console ? L"\\python\\python.exe" : L"\\python\\pythonw.exe");
    if (!PathFileExistsW(py)) {
        wcscpy(msg, L"Python topilmadi:\n"); cat(msg, py); cat(msg, L"\n\nAppWin papkasi EksportMonitor papkasi yonida turishi kerak.");
        die(msg); return 1;
    }

    /* PYTHONPATH = AppWin\vendor;EksportMonitor\vendor;EksportMonitor;AppWin */
    wcscpy(pypath, app); cat(pypath, L"\\vendor;"); cat(pypath, legacy); cat(pypath, L"\\vendor;"); cat(pypath, legacy); cat(pypath, L";"); cat(pypath, app);
    SetEnvironmentVariableW(L"PYTHONPATH", pypath);
    SetEnvironmentVariableW(L"PYTHONUTF8", L"1");
    SetEnvironmentVariableW(L"PYTHONIOENCODING", L"utf-8");
    SetEnvironmentVariableW(L"PYTHONNET_RUNTIME", L"netfx");

    wcscpy(cmd, L"\""); cat(cmd, py); cat(cmd, L"\" -m appwin.desktop");
    if (cmdLine != NULL && cmdLine[0] != 0) { cat(cmd, L" "); cat(cmd, cmdLine); }

    STARTUPINFOW si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si); ZeroMemory(&pi, sizeof(pi));
    if (!CreateProcessW(NULL, cmd, NULL, NULL, FALSE, console ? 0 : CREATE_NO_WINDOW, NULL, app, &si, &pi)) {
        DWORD err = GetLastError();
        wchar_t num[32]; wsprintfW(num, L"%lu", (unsigned long)err);
        wcscpy(msg, L"Dastur ishga tushmadi (CreateProcess xato "); cat(msg, num); cat(msg, L").\n\nBuyruq:\n"); cat(msg, cmd);
        cat(msg, L"\n\nIsh papkasi:\n"); cat(msg, app);
        die(msg); return 1;
    }
    if (console) { WaitForSingleObject(pi.hProcess, INFINITE); }
    CloseHandle(pi.hProcess); CloseHandle(pi.hThread);
    return 0;
}
