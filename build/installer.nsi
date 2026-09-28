; Eksport Monitor — Windows installer (NSIS 3). Build:
;   makensis -DVERSION=2.0.0 installer.nsi                → EksportMonitor-Admin-Setup.exe (server)
;   makensis -DVERSION=2.0.0 -DCLIENT installer.nsi       → EksportMonitor-Setup.exe (staff, client mode)
Unicode true
SetCompressor /SOLID lzma
SetCompressorDictSize 32
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!ifndef VERSION
  !define VERSION "2.0.0"
!endif
!ifdef CLIENT
  !define NAME "Eksport Monitor"
  !define OUTFILE "EksportMonitor-Setup.exe"
  !define KIND "xodim (client)"
!else
  !define NAME "Eksport Monitor (Admin)"
  !define OUTFILE "EksportMonitor-Admin-Setup.exe"
  !define KIND "server (admin)"
!endif
!define PAYLOAD "payload"
!define REGKEY "Software\EksportMonitor"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\EksportMonitor"

Name "${NAME}"
OutFile "out\${OUTFILE}"
InstallDir "C:\EksportMonitor"
InstallDirRegKey HKLM "${REGKEY}" "InstallDir"
RequestExecutionLevel admin
BrandingText "Buxoro viloyati · Eksport bo'limi"

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "Eksport Monitor"
VIAddVersionKey "FileDescription" "Eksport Monitor o'rnatuvchi — ${KIND}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "Buxoro viloyati investitsiya, sanoat va savdo boshqarmasi"

; ---------------------------------------------------------------- UI
!define MUI_ICON "app.ico"
!define MUI_UNICON "app.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Eksport Monitor — ${KIND}"
!ifdef CLIENT
  !define MUI_WELCOMEPAGE_TEXT "Bu dastur xodim kompyuteriga Eksport Monitor oynasini o'rnatadi.$\r$\n$\r$\nDastur ofis tarmog'idagi server (admin) kompyuteriga ulanadi. Keyingi qadamda server manzili so'raladi.$\r$\n$\r$\nInternet kerak emas. Davom etish uchun «Keyingi» ni bosing."
!else
  !define MUI_WELCOMEPAGE_TEXT "Bu dastur server (admin) kompyuteriga Eksport Monitor tizimini o'rnatadi: dastur, ma'lumotlar bazasi, login va rollar, tashqi diskka zaxira.$\r$\n$\r$\nXodimlar ofis tarmog'i orqali shu kompyuterga ulanadi. Internet kerak emas.$\r$\n$\r$\nDavom etish uchun «Keyingi» ni bosing."
!endif
!define MUI_DIRECTORYPAGE_TEXT_TOP "Dastur quyidagi papkaga o'rnatiladi. C:\Program Files ni tanlamang — yangilanish ishlamaydi."
!define MUI_FINISHPAGE_TITLE "Tayyor"
!ifdef CLIENT
  !define MUI_FINISHPAGE_TEXT "Eksport Monitor o'rnatildi. Ish stolida «Eksport Monitor» yorlig'i paydo bo'ldi.$\r$\n$\r$\nLogin va parolni admin beradi. Dastur har ochilganda yangilanishlarni serverdan o'zi oladi."
!else
  !define MUI_FINISHPAGE_TEXT "Eksport Monitor o'rnatildi. Ish stolida «Eksport Monitor» yorlig'i paydo bo'ldi.$\r$\n$\r$\nBirinchi kirish: login «admin», parol — ma'lumotlar papkasidagi ADMIN_PAROL.txt faylida (dastur birinchi ochilganda yaratiladi). Kirgach parolni o'zgartiring.$\r$\n$\r$\nXodimlarga: EksportMonitor-Setup.exe + shu kompyuterning IP manzili (Superadmin → Server)."
!endif
!define MUI_FINISHPAGE_RUN "$INSTDIR\EksportMonitor.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Eksport Monitor ni hozir ochish"
!define MUI_FINISHPAGE_NOREBOOTSUPPORT

Var Dlg
Var HData
Var HBackup
Var HServer
Var DataDir
Var BackupDir
Var ServerUrl
Var KeepConfig

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
Page custom SettingsPage SettingsLeave
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Uzbek"

; ---------------------------------------------------------------- settings page
Function SettingsPage
  StrCpy $KeepConfig "0"
  ${If} ${FileExists} "$INSTDIR\config.json"
    StrCpy $KeepConfig "1"
    Abort                                  ; upgrade: existing settings are kept, page skipped
  ${EndIf}
!ifdef CLIENT
  !insertmacro MUI_HEADER_TEXT "Server manzili" "Admin (server) kompyuterining manzili"
!else
  !insertmacro MUI_HEADER_TEXT "Ma'lumotlar" "Baza va zaxira qayerda saqlanadi"
!endif
  nsDialogs::Create 1018
  Pop $Dlg
  ${If} $Dlg == error
    Abort
  ${EndIf}
!ifdef CLIENT
  ${NSD_CreateLabel} 0 0 100% 24u "Server (admin) kompyuterining manzili. IP ni admin aytadi (Superadmin → Server bo'limida ko'rinadi). Masalan: http://192.168.1.10:8765"
  Pop $0
  ${NSD_CreateText} 0 30u 100% 13u "http://192.168.1.10:8765"
  Pop $HServer
  ${NSD_CreateLabel} 0 50u 100% 24u "Keyin o'zgartirish: C:\EksportMonitor\config.json faylida $\"server_url$\"."
  Pop $0
!else
  ${NSD_CreateLabel} 0 0 100% 12u "Ma'lumotlar papkasi (baza, hujjatlar shu yerda saqlanadi):"
  Pop $0
  ${NSD_CreateText} 0 13u 78% 13u "$INSTDIR\data"
  Pop $HData
  ${NSD_CreateButton} 80% 13u 20% 13u "Tanlash…"
  Pop $0
  ${NSD_OnClick} $0 BrowseData
  ${NSD_CreateLabel} 0 30u 100% 20u "Mavjud bazangiz bo'lsa (masalan D:\2026 export\data) — o'sha papkani ko'rsating, hech narsa ko'chirilmaydi."
  Pop $0
  ${NSD_CreateLabel} 0 56u 100% 12u "Tashqi zaxira diski papkasi (ixtiyoriy, keyin ham sozlash mumkin):"
  Pop $0
  ${NSD_CreateText} 0 69u 78% 13u ""
  Pop $HBackup
  ${NSD_CreateButton} 80% 69u 20% 13u "Tanlash…"
  Pop $0
  ${NSD_OnClick} $0 BrowseBackup
  ${NSD_CreateLabel} 0 86u 100% 20u "Masalan E:\EksportMonitor_zaxira. Dastur yopilganda «Zaxira olinsinmi?» so'raydi va shu papkaga yozadi."
  Pop $0
!endif
  nsDialogs::Show
FunctionEnd

Function BrowseData
  ${NSD_GetText} $HData $1
  nsDialogs::SelectFolderDialog "Ma'lumotlar papkasi" "$1"
  Pop $1
  ${If} $1 != error
    ${NSD_SetText} $HData "$1"
  ${EndIf}
FunctionEnd

Function BrowseBackup
  nsDialogs::SelectFolderDialog "Zaxira diski papkasi" ""
  Pop $1
  ${If} $1 != error
    ${NSD_SetText} $HBackup "$1"
  ${EndIf}
FunctionEnd

Function SettingsLeave
!ifdef CLIENT
  ${NSD_GetText} $HServer $ServerUrl
  ${If} $ServerUrl == ""
    MessageBox MB_ICONEXCLAMATION|MB_OK "Server manzilini yozing (masalan http://192.168.1.10:8765)."
    Abort
  ${EndIf}
!else
  ${NSD_GetText} $HData $DataDir
  ${NSD_GetText} $HBackup $BackupDir
  ${If} $DataDir == ""
    StrCpy $DataDir "$INSTDIR\data"
  ${EndIf}
!endif
FunctionEnd

; ---------------------------------------------------------------- install
Function StopRunning
  ; close a running Eksport Monitor from this folder (pythonw/python started from $INSTDIR)
  nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process pythonw,python -ErrorAction SilentlyContinue | Where-Object { $$_.Path -like $\"$INSTDIR\*$\" } | Stop-Process -Force"'
  Pop $0
  Sleep 800
FunctionEnd

Section "Eksport Monitor" SEC_MAIN
  SectionIn RO
  Call StopRunning
  SetOutPath "$INSTDIR"
  ; old code out (data/config/webview-data/appwin.log stay)
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\appwin"
  RMDir /r "$INSTDIR\vendor"
  File /r "${PAYLOAD}\*.*"
  ; everyone on this PC may write here (log, updates, webview cache)
  nsExec::ExecToLog 'icacls "$INSTDIR" /grant *S-1-5-11:(OI)(CI)M /T /Q'
  Pop $0
  ; config.json — only on first install; an upgrade keeps the existing one
  ${If} $KeepConfig != "1"
!ifdef CLIENT
    nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\appwin\setup_config.py" "$INSTDIR\config.json" client "server_url=$ServerUrl"'
!else
    nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\appwin\setup_config.py" "$INSTDIR\config.json" server "data_dir=$DataDir" "backup_dir=$BackupDir"'
!endif
    Pop $0
  ${EndIf}
!ifndef CLIENT
  ; LAN access for staff: Windows Firewall
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="Eksport Monitor"'
  Pop $0
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="Eksport Monitor" dir=in action=allow program="$INSTDIR\python\pythonw.exe" enable=yes profile=private,domain'
  Pop $0
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="Eksport Monitor" dir=in action=allow program="$INSTDIR\python\python.exe" enable=yes profile=private,domain'
  Pop $0
!endif
  ; shortcuts
  CreateShortcut "$DESKTOP\Eksport Monitor.lnk" "$INSTDIR\EksportMonitor.exe" "" "$INSTDIR\EksportMonitor.exe" 0
  CreateDirectory "$SMPROGRAMS\Eksport Monitor"
  CreateShortcut "$SMPROGRAMS\Eksport Monitor\Eksport Monitor.lnk" "$INSTDIR\EksportMonitor.exe" "" "$INSTDIR\EksportMonitor.exe" 0
  CreateShortcut "$SMPROGRAMS\Eksport Monitor\Qo'llanma.lnk" "$INSTDIR\QOLLANMA.txt"
  CreateShortcut "$SMPROGRAMS\Eksport Monitor\O'chirish.lnk" "$INSTDIR\Uninstall.exe"
  ; registry + uninstaller
  WriteRegStr HKLM "${REGKEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "${REGKEY}" "Version" "${VERSION}"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "${UNINSTKEY}" "DisplayName" "Eksport Monitor"
  WriteRegStr HKLM "${UNINSTKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINSTKEY}" "Publisher" "Buxoro viloyati · Eksport bo'limi"
  WriteRegStr HKLM "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\EksportMonitor.exe"
  WriteRegStr HKLM "${UNINSTKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKLM "${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTKEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${UNINSTKEY}" "EstimatedSize" "$0"
SectionEnd

; ---------------------------------------------------------------- uninstall
Section "Uninstall"
  nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process pythonw,python -ErrorAction SilentlyContinue | Where-Object { $$_.Path -like $\"$INSTDIR\*$\" } | Stop-Process -Force"'
  Pop $0
  Sleep 800
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\appwin"
  RMDir /r "$INSTDIR\vendor"
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\webview-data"
  RMDir /r "$INSTDIR\_update"
  Delete "$INSTDIR\EksportMonitor.exe"
  Delete "$INSTDIR\Ishga_tushirish.bat"
  Delete "$INSTDIR\QOLLANMA.txt"
  Delete "$INSTDIR\config.client.example.json"
  Delete "$INSTDIR\appwin.log"
  Delete "$INSTDIR\Uninstall.exe"
  ; config.json and data\ are kept on purpose (ma'lumotlar o'chmaydi)
  RMDir "$INSTDIR"
  Delete "$DESKTOP\Eksport Monitor.lnk"
  RMDir /r "$SMPROGRAMS\Eksport Monitor"
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="Eksport Monitor"'
  Pop $0
  DeleteRegKey HKLM "${UNINSTKEY}"
  DeleteRegKey HKLM "${REGKEY}"
  MessageBox MB_ICONINFORMATION|MB_OK "Dastur o'chirildi. Ma'lumotlar (data papkasi) va config.json saqlanib qoldi."
SectionEnd
