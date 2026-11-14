// Native Windows first-run assistant. Statically linked; starts before Python
// or any game/compiler DLL, so missing prerequisites can be explained in UI.
#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commdlg.h>
#include <shlobj.h>
#include <shellapi.h>
#include <GL/gl.h>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <cstdio>

namespace fs=std::filesystem;
static HWND win,report,disc_label,check_button,prepare_button,play_button;
static HANDLE process_handle,operation_job;
static fs::path app,data,kit,python,image;
static std::wstring operation;
static bool hardware_ok=false,requirements_ok=false;
static bool auto_libraries_attempted=false,direct_play=false;
static HFONT font;
static const wchar_t* KIT_URL=L"https://github.com/TechnicallyComputers/retcomm-toolchains/releases";

static std::wstring wide(const std::string& text) {
    int n=MultiByteToWideChar(CP_UTF8,0,text.data(),(int)text.size(),NULL,0);
    std::wstring result(n,0);if(n)MultiByteToWideChar(CP_UTF8,0,text.data(),(int)text.size(),result.data(),n);return result;
}
static std::wstring read(const fs::path& path) {
    std::ifstream file(path,std::ios::binary);std::ostringstream text;text<<file.rdbuf();
    auto result=wide(text.str());std::wstring out;
    for(size_t i=0;i<result.size();++i){if(result[i]==L'\n' && (!i || result[i-1]!=L'\r'))out+=L'\r';out+=result[i];}return out;
}
static std::wstring quote(const std::wstring& text) {
    std::wstring out=L"\"";unsigned slashes=0;
    for(wchar_t c:text){if(c==L'\\'){++slashes;continue;}if(c==L'\"')out.append(slashes*2+1,L'\\');else out.append(slashes,L'\\');slashes=0;out+=c;}
    out.append(slashes*2,L'\\');return out+L"\"";
}
static bool regular(const fs::path& path) {std::error_code error;return fs::is_regular_file(path,error);}
static fs::path python_in(const fs::path& root) {
    for(const auto& relative:{L"python/python.exe",L"python/install/python.exe"})if(regular(root/relative))return root/relative;
    return {};
}
static void choose_python() {
    python=python_in(kit);
    if(read(data/L"python-kit.txt")==kit.wstring() && regular(data/L"python/Scripts/python.exe"))python=data/L"python/Scripts/python.exe";
}
static fs::path discover_kit() {
    std::vector<fs::path> candidates={app/L"toolchain"};
    wchar_t value[32768];
    for(const wchar_t* name:{L"RETCOMM_TOOLCHAIN_DIR",L"PSXRECOMP_TOOLCHAIN_DIR"})if(GetEnvironmentVariableW(name,value,32768))candidates.emplace_back(value);
    if(GetEnvironmentVariableW(L"LOCALAPPDATA",value,32768))candidates.push_back(fs::path(value)/L"retcomm/toolchains/cmake-clang-v1/latest");
    if(GetEnvironmentVariableW(L"USERPROFILE",value,32768))candidates.push_back(fs::path(value)/L".local/share/retcomm/toolchains/cmake-clang-v1/latest");
    auto saved=read(data/L"toolchain.txt");if(!saved.empty())candidates.emplace_back(saved);
    for(auto candidate:candidates)if(regular(candidate/L"bin/cmake.exe") && !python_in(candidate).empty())return candidate;
    return {};
}
static std::wstring gpu_check() {
    // Probe the real driver. opengl32.dll existing alone only proves the
    // Windows 1.1 loader is present, not that the modern renderer will work.
    WNDCLASSW cls={};cls.style=CS_OWNDC;cls.lpfnWndProc=DefWindowProcW;cls.hInstance=GetModuleHandle(NULL);cls.lpszClassName=L"DukeTTKGraphicsProbe";RegisterClassW(&cls);
    HWND probe=CreateWindowW(cls.lpszClassName,L"",WS_POPUP,0,0,16,16,NULL,NULL,GetModuleHandle(NULL),NULL);
    HDC dc=GetDC(probe);PIXELFORMATDESCRIPTOR format={};format.nSize=sizeof format;format.nVersion=1;
    format.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL;format.iPixelType=PFD_TYPE_RGBA;format.cColorBits=24;
    int pixel=ChoosePixelFormat(dc,&format);HGLRC context=NULL;
    if(pixel && SetPixelFormat(dc,pixel,&format))context=wglCreateContext(dc);
    int major=0,minor=0;std::wstring detail;
    if(context && wglMakeCurrent(dc,context)) {
        const char* version=(const char*)glGetString(GL_VERSION);
        if(version){std::sscanf(version,"%d.%d",&major,&minor);detail=wide(version);}
        wglMakeCurrent(NULL,NULL);
    }
    if(context)wglDeleteContext(context);ReleaseDC(probe,dc);DestroyWindow(probe);
    hardware_ok=major>3 || (major==3 && minor>=3);
    return hardware_ok?L"OK - OpenGL "+detail:
        L"FALTA - OpenGL 3.3 ou superior. Atualize o driver pelo site do fabricante da sua placa e execute novamente. Não baixe DLLs avulsas.";
}
static std::wstring hardware_report;
static void refresh_buttons() {
    bool idle=!process_handle;
    for(int id:{11,12,16})EnableWindow(GetDlgItem(win,id),idle);
    EnableWindow(GetDlgItem(win,13),idle && hardware_ok && requirements_ok);
    EnableWindow(check_button,idle);EnableWindow(prepare_button,idle && hardware_ok && requirements_ok && (!image.empty() || regular(data/L"project/recomp/disc/time-to-kill.cue")));
    EnableWindow(play_button,idle && hardware_ok && regular(data/L"ready.json") && !python.empty());
}
static void show_check() {
    choose_python();requirements_ok=false;
    if(kit.empty() || python.empty()) {
        SetWindowTextW(report,(hardware_report+L"\r\n\r\nFALTA - Kit portátil de preparação.\r\n\r\nUse Baixar kit, extraia o cmake-clang-v1 para uma pasta do seu usuário e clique em Selecionar kit. O kit reúne Python, CMake, Ninja e Clang. Não é necessário instalar Git ou Visual Studio.\r\n\r\nSe o instalador já incluía o kit, reinstale o pacote completo.").c_str());
        refresh_buttons();return;
    }
    SendMessage(win,WM_APP+1,0,0);
}
static void start(const wchar_t* name) {
    if(process_handle)return;
    choose_python();
    if(!wcscmp(name,L"install-libraries"))python=python_in(kit);
    if(python.empty()){MessageBoxW(win,L"Selecione um kit portátil com Python antes de continuar.",L"Requisito pendente",MB_OK|MB_ICONINFORMATION);return;}
    operation=name;
    auto script=app/L"player_setup.py";
    std::wstring cmd=quote(python.wstring())+L" "+quote(script.wstring())+L" "+name+L" --app-root "+quote(app.wstring())+L" --toolchain "+quote(kit.wstring())+L" --data-dir "+quote(data.wstring());
    if(operation==L"prepare" && !image.empty())cmd+=L" --image "+quote(image.wstring());
    SECURITY_ATTRIBUTES sa={sizeof sa,NULL,TRUE};
    HANDLE log=CreateFileW((data/L"setup.log").c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,&sa,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    HANDLE input=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&sa,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    STARTUPINFOW si={};si.cb=sizeof si;si.dwFlags=STARTF_USESTDHANDLES;si.hStdOutput=si.hStdError=log;si.hStdInput=input;
    PROCESS_INFORMATION pi={};
    operation_job=CreateJobObjectW(NULL,NULL);
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits={};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    BOOL bounded=operation_job && SetInformationJobObject(operation_job,JobObjectExtendedLimitInformation,&limits,sizeof limits);
    BOOL ok=bounded && log!=INVALID_HANDLE_VALUE && CreateProcessW(python.c_str(),cmd.data(),NULL,NULL,TRUE,CREATE_NO_WINDOW|CREATE_SUSPENDED,NULL,app.c_str(),&si,&pi);
    if(ok && !AssignProcessToJobObject(operation_job,pi.hProcess)){TerminateProcess(pi.hProcess,1);CloseHandle(pi.hProcess);CloseHandle(pi.hThread);ok=FALSE;}
    if(log!=INVALID_HANDLE_VALUE)CloseHandle(log);if(input!=INVALID_HANDLE_VALUE)CloseHandle(input);
    if(!ok){if(operation_job)CloseHandle(operation_job);operation_job=NULL;MessageBoxW(win,L"Não foi possível iniciar o Python do kit. Verifique se a pasta foi extraída completamente e selecione-a novamente.",L"Não foi possível continuar",MB_OK|MB_ICONERROR);operation.clear();return;}
    process_handle=pi.hProcess;ResumeThread(pi.hThread);CloseHandle(pi.hThread);
    if(operation==L"prepare")
        SetWindowTextW(report,L"Preparando seu jogo. A primeira preparação pode levar vários minutos.");
    else if(operation==L"play")
        SetWindowTextW(report,L"Jogo em execução. Feche o jogo para voltar ao assistente.");
    else
        SetWindowTextW(report,L"Verificando requisitos...");
    refresh_buttons();
}
static HWND control(const wchar_t* type,const wchar_t* text,DWORD style,int x,int y,int w,int h,int id) {
    HWND child=CreateWindowExW(type==std::wstring(L"EDIT")?WS_EX_CLIENTEDGE:0,type,text,WS_CHILD|WS_VISIBLE|style,x,y,w,h,win,(HMENU)(INT_PTR)id,GetModuleHandle(NULL),NULL);
    SendMessage(child,WM_SETFONT,(WPARAM)font,TRUE);return child;
}
static LRESULT CALLBACK handler(HWND window,UINT msg,WPARAM wp,LPARAM lp) {
    if(msg==WM_APP+1){start(L"check");return 0;}
    if(msg==WM_COMMAND) {
        switch(LOWORD(wp)) {
        case 10:hardware_report=gpu_check();auto_libraries_attempted=false;show_check();break;
        case 11: {
            if(process_handle)break;
            BROWSEINFOW bi={};bi.hwndOwner=win;bi.lpszTitle=L"Selecione a pasta do kit cmake-clang-v1 (contém bin, deps e python)";bi.ulFlags=BIF_RETURNONLYFSDIRS|BIF_NEWDIALOGSTYLE;
            PIDLIST_ABSOLUTE item=SHBrowseForFolderW(&bi);wchar_t path[MAX_PATH];
            if(item){if(SHGetPathFromIDListW(item,path)){kit=path;if(kit.filename()==L"bin")kit=kit.parent_path();auto_libraries_attempted=false;
                std::ofstream saved(data/L"toolchain.txt",std::ios::binary);auto text=kit.u8string();saved.write(text.data(),text.size());saved.close();show_check();}CoTaskMemFree(item);}break;
        }
        case 12:ShellExecuteW(win,L"open",KIT_URL,NULL,NULL,SW_SHOWNORMAL);break;
        case 13: {
            if(process_handle || !requirements_ok || !hardware_ok)break;
            wchar_t path[32768]={};OPENFILENAMEW of={};of.lStructSize=sizeof of;of.hwndOwner=win;of.lpstrFile=path;of.nMaxFile=32768;
            of.lpstrTitle=L"Selecione sua cópia original USA SLUS-00583";
            of.lpstrFilter=L"Disco PlayStation USA (*.cue;*.bin;*.img)\0*.cue;*.bin;*.img\0Todos os arquivos\0*.*\0";of.Flags=OFN_FILEMUSTEXIST|OFN_PATHMUSTEXIST|OFN_NOCHANGEDIR;
            if(GetOpenFileNameW(&of)){
                image=path;
                SetWindowTextW(disc_label,image.filename().c_str());
                start(L"prepare");
            }break;
        }
        case 14:if(requirements_ok && hardware_ok)start(L"prepare");break;
        case 15:start(L"play");break;
        case 16:
            if(MessageBoxW(win,L"Instalar as bibliotecas de preparação em uma pasta privada do aplicativo? Se não houver pacote offline, será usado o índice oficial PyPI. O Python do sistema não será alterado.",L"Instalar bibliotecas",MB_YESNO|MB_ICONQUESTION)==IDYES)start(L"install-libraries");break;
        case 17:ShellExecuteW(win,L"open",L"notepad.exe",quote((data/L"setup.log").wstring()).c_str(),NULL,SW_SHOWNORMAL);break;
        }
        return 0;
    }
    if(msg==WM_TIMER && process_handle) {
        if(operation!=L"check" && operation!=L"play") {
            auto text=operation==L"prepare"?read(data/L"status.txt"):L"Instalando bibliotecas em uma pasta privada do aplicativo. Aguarde...\r\nO registro detalhado está disponível em Ver registro.";
            if(!text.empty())SetWindowTextW(report,text.c_str());
        }
        if(WaitForSingleObject(process_handle,0)==WAIT_OBJECT_0) {
            DWORD status=1;GetExitCodeProcess(process_handle,&status);CloseHandle(process_handle);process_handle=NULL;
            if(operation_job){CloseHandle(operation_job);operation_job=NULL;}
            if(operation==L"check") {
                if(status==3 && hardware_ok && !auto_libraries_attempted) {
                    auto_libraries_attempted=true;
                    start(L"install-libraries");
                    return 0;
                }
                requirements_ok=status==0;
                std::wstring next=requirements_ok && hardware_ok
                    ? L"Selecione o disco original para iniciar a preparação.\r\n\r\n" : L"";
                SetWindowTextW(report,(next+hardware_report+L"\r\n\r\n"+read(data/L"requirements.txt")).c_str());
            } else if(operation==L"play" && direct_play) {
                if(status==0){DestroyWindow(window);return 0;}
                direct_play=false;
                ShowWindow(win,SW_SHOWNORMAL);
                MessageBoxW(win,read(data/L"last-error.txt").c_str(),L"Verifique a instalação",MB_OK|MB_ICONWARNING);
                show_check();return 0;
            } else if(status!=0) {
                SetWindowTextW(report,read(data/L"last-error.txt").c_str());
            } else if(operation==L"install-libraries") {operation.clear();show_check();return 0;}
            else if(operation==L"prepare") {SetWindowTextW(report,L"Preparação concluída. Clique em Jogar. Nas próximas vezes, use o mesmo atalho.");}
            else if(operation==L"play") {SetWindowTextW(report,L"Jogo encerrado. Clique em Jogar para abrir novamente.");}
            operation.clear();refresh_buttons();
        }
        return 0;
    }
    if(msg==WM_CLOSE) {
        if(process_handle){
            if(operation==L"play"){MessageBoxW(win,L"Feche o jogo antes de sair deste assistente.",L"Jogo em execução",MB_OK);return 0;}
            if(MessageBoxW(win,L"Interromper a preparação? Você poderá tentar novamente. Seu disco original e seus saves serão preservados.",L"Interromper etapa",MB_YESNO|MB_ICONQUESTION)!=IDYES)return 0;
            if(operation_job){TerminateJobObject(operation_job,1);CloseHandle(operation_job);operation_job=NULL;}
            CloseHandle(process_handle);process_handle=NULL;
        }
        DestroyWindow(window);return 0;
    }
    if(msg==WM_DESTROY){PostQuitMessage(0);return 0;}
    return DefWindowProcW(window,msg,wp,lp);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR,int) {
    CoInitializeEx(NULL,COINIT_APARTMENTTHREADED);
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    SetEnvironmentVariableW(L"PYTHONUTF8",L"1");SetEnvironmentVariableW(L"PYTHONIOENCODING",L"utf-8");
    OSVERSIONINFOW os={};os.dwOSVersionInfoSize=sizeof os;
    auto get_version=(LONG(WINAPI*)(OSVERSIONINFOW*))GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"RtlGetVersion");
    if(!get_version || get_version(&os)!=0 || os.dwMajorVersion<10){MessageBoxW(NULL,L"Este pacote exige Windows 10 ou 11 de 64 bits.",L"Sistema incompatível",MB_OK|MB_ICONERROR);return 1;}
    wchar_t path[32768];GetModuleFileNameW(NULL,path,32768);app=fs::path(path).parent_path();
    if(!GetEnvironmentVariableW(L"LOCALAPPDATA",path,32768))return 1;
    data=fs::path(path)/L"DukeTTK-PTBR";
    int argc=0;LPWSTR* argv=CommandLineToArgvW(GetCommandLineW(),&argc);
    for(int i=1;argv && i<argc;++i) {
        if(!wcscmp(argv[i],L"--play"))direct_play=true;
        else if(!wcscmp(argv[i],L"--data-dir") && i+1<argc)data=fs::absolute(argv[++i]);
    }
    if(argv)LocalFree(argv);
    try{fs::create_directories(data);}catch(...){MessageBoxW(NULL,L"Não foi possível criar a pasta de dados do aplicativo.",L"Duke TTK PT-BR",MB_OK|MB_ICONERROR);return 1;}
    HANDLE lock=CreateFileW((data/L"assistant.lock").c_str(),GENERIC_WRITE,0,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(lock==INVALID_HANDLE_VALUE){MessageBoxW(NULL,L"Já existe um assistente usando esta pasta de dados. Feche a outra janela e tente novamente.",L"Duke TTK PT-BR",MB_OK|MB_ICONINFORMATION);return 1;}
    SYSTEM_INFO system;GetNativeSystemInfo(&system);
    if(system.wProcessorArchitecture!=PROCESSOR_ARCHITECTURE_AMD64){MessageBoxW(NULL,L"Esta versão exige Windows para processador x64. ARM e Windows 32 bits ainda não são suportados por este pacote.",L"Sistema incompatível",MB_OK|MB_ICONERROR);return 1;}
    WNDCLASSW cls={};cls.lpfnWndProc=handler;cls.hInstance=instance;cls.lpszClassName=L"DukeTTKSetup";cls.hCursor=LoadCursor(NULL,IDC_ARROW);cls.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);RegisterClassW(&cls);
    win=CreateWindowW(cls.lpszClassName,L"Duke Nukem: Time to Kill - Instalação e requisitos",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,800,630,NULL,NULL,instance,NULL);
    font=CreateFontW(-17,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
    control(L"STATIC",L"Prepare sua cópia USA e jogue em português",0,24,20,730,26,0);
    control(L"STATIC",L"Selecione sua cópia original após a verificação automática.",0,24,54,730,24,0);
    report=control(L"EDIT",L"",ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL|WS_VSCROLL,24,92,734,300,0);
    check_button=control(L"BUTTON",L"Verificar novamente",WS_TABSTOP,24,410,178,32,10);
    control(L"BUTTON",L"Selecionar kit...",WS_TABSTOP,214,410,158,32,11);
    control(L"BUTTON",L"Baixar kit",WS_TABSTOP,384,410,130,32,12);
    control(L"BUTTON",L"Instalar bibliotecas",WS_TABSTOP,526,410,232,32,16);
    control(L"BUTTON",L"Selecionar disco e instalar...",WS_TABSTOP,24,460,260,34,13);
    disc_label=control(L"STATIC",L"Disco original ainda não selecionado",SS_PATHELLIPSIS,296,468,462,24,0);
    prepare_button=control(L"BUTTON",L"Preparar jogo",WS_TABSTOP,400,520,174,38,14);
    control(L"BUTTON",L"Ver registro",WS_TABSTOP,24,520,190,38,17);
    play_button=control(L"BUTTON",L"Jogar",WS_TABSTOP|BS_DEFPUSHBUTTON,590,520,168,38,15);
    kit=discover_kit();hardware_report=gpu_check();SetTimer(win,1,300,NULL);
    choose_python();
    if(direct_play && hardware_ok && !python.empty() && regular(data/L"ready.json"))start(L"play");
    if(!process_handle) {
        direct_play=false;
        ShowWindow(win,SW_SHOWNORMAL);UpdateWindow(win);show_check();
    }
    MSG message;while(GetMessageW(&message,NULL,0,0)>0){if(!IsDialogMessageW(win,&message)){TranslateMessage(&message);DispatchMessageW(&message);}}
    DeleteObject(font);CloseHandle(lock);CoUninitialize();return 0;
}
