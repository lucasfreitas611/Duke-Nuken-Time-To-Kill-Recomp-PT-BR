// Native Windows first-run assistant. Statically linked; starts before Python
// or any game/compiler DLL, so missing prerequisites can be explained in UI.
#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commdlg.h>
#include <commctrl.h>
#include <cwchar>
#include <cwctype>
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
static HWND win;
static fs::path app,data,kit,python,image;

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
static bool gpu_check() {
    // Probe the real driver. opengl32.dll existing alone only proves the
    // Windows 1.1 loader is present, not that the modern renderer will work.
    WNDCLASSW cls={};cls.style=CS_OWNDC;cls.lpfnWndProc=DefWindowProcW;cls.hInstance=GetModuleHandle(NULL);cls.lpszClassName=L"DukeTTKGraphicsProbe";RegisterClassW(&cls);
    HWND probe=CreateWindowW(cls.lpszClassName,L"",WS_POPUP,0,0,16,16,NULL,NULL,GetModuleHandle(NULL),NULL);
    HDC dc=GetDC(probe);PIXELFORMATDESCRIPTOR format={};format.nSize=sizeof format;format.nVersion=1;
    format.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL;format.iPixelType=PFD_TYPE_RGBA;format.cColorBits=24;
    int pixel=ChoosePixelFormat(dc,&format);HGLRC context=NULL;
    if(pixel && SetPixelFormat(dc,pixel,&format))context=wglCreateContext(dc);
    int major=0,minor=0;
    if(context && wglMakeCurrent(dc,context)) {
        const char* version=(const char*)glGetString(GL_VERSION);
        if(version)std::sscanf(version,"%d.%d",&major,&minor);
        wglMakeCurrent(NULL,NULL);
    }
    if(context)wglDeleteContext(context);ReleaseDC(probe,dc);DestroyWindow(probe);
    return major>3 || (major==3 && minor>=3);
}

static HBRUSH paper, panel, header;
static HWND heading,step,report,disc_label,action,replace_disc,details,progress_bar;
static HFONT font,title_font,label_font;
static HANDLE process_handle,operation_job;
static fs::path details_path;
static std::wstring operation;
static bool auto_libraries_attempted=false,direct_play=false,failed=false;
static bool disk_error=false;
static UINT dpi=96;
enum { choose_id=101, replace_id, details_id, heading_id, step_id, disc_id, report_id };

static int px(int logical) {return MulDiv(logical,dpi,96);}
static bool imported_disc() {
    auto folder=data/L"project/recomp/disc";
    return regular(folder/L"time-to-kill.cue") && regular(folder/L"time-to-kill.bin") &&
           regular(folder/L"import-receipt.json");
}
static bool ready_to_play() {
    const auto version=read(app/L"VERSION");
    return !version.empty() && read(data/L"prepared-version.txt")==version &&
           regular(data/L"ready.json") && imported_disc();
}
static bool selected_disc() {return !image.empty() || (imported_disc() && !disk_error);}
static void show_progress(bool visible,int done=0,int total=0) {
    const bool marquee=visible && total==0;
    const auto style=GetWindowLongPtrW(progress_bar,GWL_STYLE);
    if(marquee!=(bool)(style&PBS_MARQUEE)) {
        SendMessageW(progress_bar,PBM_SETMARQUEE,FALSE,0);
        SetWindowLongPtrW(progress_bar,GWL_STYLE,marquee ? style|PBS_MARQUEE : style&~PBS_MARQUEE);
        SendMessageW(progress_bar,PBM_SETMARQUEE,marquee,34);
    }
    if(!marquee) SendMessageW(progress_bar,PBM_SETPOS,total ? 100LL*done/total : 0,0);
    ShowWindow(progress_bar,visible?SW_SHOWNA:SW_HIDE);
}
static void state(const wchar_t* title,const std::wstring& message,bool error=false) {
    failed=error;
    SetWindowTextW(step,title);
    SetWindowTextW(report,message.c_str());
    InvalidateRect(step,NULL,TRUE);
}
static void refresh() {
    const bool ready=ready_to_play();
    auto file=image.empty() ? (imported_disc() && !disk_error ? L"Cópia USA já conferida" : L"Nenhum disco selecionado")
                            : image.filename().wstring();
    SetWindowTextW(disc_label,file.c_str());
    const wchar_t* label=process_handle?L"Aguarde…":failed?(selected_disc()?L"Tentar novamente":L"Escolher disco…"):
                         ready?L"Jogar":selected_disc()?L"Preparar jogo":L"Escolher disco…";
    SetWindowTextW(action,label);
    EnableWindow(action,!process_handle);
    ShowWindow(replace_disc,!process_handle && selected_disc()?SW_SHOWNA:SW_HIDE);
    ShowWindow(details,!details_path.empty()?SW_SHOWNA:SW_HIDE);
    if(!process_handle && IsWindowVisible(win))SetFocus(action);
}
static void error_state(const wchar_t* title,const std::wstring& message,const wchar_t* log=L"setup.log") {
    show_progress(false);details_path=data/log;
    state(title,message,true);refresh();
}
static void update_preparation_status() {
    const auto status=read(data/L"status.txt");
    if(status.empty())return;
    const auto newline=status.find(L'\n');
    int done=0,total=0;
    if(newline!=std::wstring::npos && newline+1<status.size() &&
       std::swscanf(status.c_str(),L"%d %d",&done,&total)==2 && done>0 && done<=total) {
        state(L"Preparando o jogo",L"Recompilando o jogo. "+std::to_wstring(done)+L" de "+std::to_wstring(total)+
              L" tarefas concluídas.\r\nMantenha esta janela aberta.");
        show_progress(true,done,total);
    } else {
        state(L"Preparando o jogo",status+L"\r\nMantenha esta janela aberta.");
        show_progress(true);
    }
}
static bool start(const wchar_t* name) {
    if(process_handle)return false;
    choose_python();
    if(!wcscmp(name,L"install-libraries"))python=python_in(kit);
    if(python.empty()){
        error_state(L"Instalação incompleta",L"Execute novamente o instalador completo para restaurar os componentes incluídos.");
        return false;
    }
    operation=name;
    std::error_code ignored;
    fs::remove(data/L"last-error.txt",ignored);
    if(operation==L"prepare") {
        if(!selected_disc()) {
            error_state(L"Escolha o disco original",L"Selecione o arquivo .cue, .bin ou .img da edição USA.");
            operation.clear();return false;
        }
        std::ofstream(data/L"status.txt",std::ios::trunc);
    }
    auto script=app/L"player_setup.py";
    std::wstring cmd=quote(python.wstring())+L" "+quote(script.wstring())+L" "+name+L" --app-root "+quote(app.wstring())+L" --toolchain "+quote(kit.wstring())+L" --data-dir "+quote(data.wstring());
    if(operation==L"prepare" && !image.empty())cmd+=L" --image "+quote(image.wstring());
    SECURITY_ATTRIBUTES sa={sizeof sa,NULL,TRUE};
    const auto log_path=data/L"setup.log";
    HANDLE log=CreateFileW(log_path.c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,&sa,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(log!=INVALID_HANDLE_VALUE)SetFilePointer(log,0,NULL,FILE_END);
    HANDLE input=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&sa,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    STARTUPINFOW si={};si.cb=sizeof si;si.dwFlags=STARTF_USESTDHANDLES;si.hStdOutput=si.hStdError=log;si.hStdInput=input;
    PROCESS_INFORMATION pi={};
    operation_job=CreateJobObjectW(NULL,NULL);
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits={};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    BOOL bounded=operation_job && SetInformationJobObject(operation_job,JobObjectExtendedLimitInformation,&limits,sizeof limits);
    BOOL ok=bounded && log!=INVALID_HANDLE_VALUE && input!=INVALID_HANDLE_VALUE &&
            CreateProcessW(python.c_str(),cmd.data(),NULL,NULL,TRUE,CREATE_NO_WINDOW|CREATE_SUSPENDED,NULL,app.c_str(),&si,&pi);
    if(ok && !AssignProcessToJobObject(operation_job,pi.hProcess)){TerminateProcess(pi.hProcess,1);CloseHandle(pi.hProcess);CloseHandle(pi.hThread);ok=FALSE;}
    if(log!=INVALID_HANDLE_VALUE)CloseHandle(log);if(input!=INVALID_HANDLE_VALUE)CloseHandle(input);
    if(!ok){
        if(operation_job)CloseHandle(operation_job);
        operation_job=NULL;operation.clear();
        error_state(L"Não foi possível continuar",L"Abra os detalhes ou execute novamente o instalador completo.");
        return false;
    }
    process_handle=pi.hProcess;ResumeThread(pi.hThread);CloseHandle(pi.hThread);
    details_path=log_path;
    if(operation==L"prepare")
        state(L"Preparando o jogo",L"Conferindo se o disco é da edição USA.\r\nMantenha esta janela aberta.");
    else if(operation==L"play")
        state(L"Jogo em execução",L"Esta janela fecha automaticamente quando você sair do jogo.");
    else if(operation==L"install-libraries")
        state(L"Instalando os componentes",L"Os arquivos incluídos no instalador estão sendo configurados.\r\nMantenha esta janela aberta.");
    else
        state(L"Verificando o computador",L"Conferindo os componentes do jogo e o espaço disponível.");
    show_progress(operation!=L"play");
    refresh();return true;
}
static void prepare_selected() {
    if(!selected_disc())return;
    if(!gpu_check()){
        error_state(L"Driver de vídeo incompatível",L"Atualize o driver da sua placa de vídeo para uma versão com OpenGL 3.3 e tente novamente.");
        return;
    }
    auto_libraries_attempted=false;
    std::ofstream(data/L"setup.log",std::ios::trunc);
    start(L"check");
}
static void choose_disc() {
    wchar_t path[32768]={};OPENFILENAMEW of={};of.lStructSize=sizeof of;of.hwndOwner=win;of.lpstrFile=path;of.nMaxFile=32768;
    of.lpstrTitle=L"Escolha o disco original da edição USA de Duke Nukem: Time to Kill";
    of.lpstrFilter=L"Disco da edição USA (*.cue;*.bin;*.img)\0*.cue;*.bin;*.img\0Todos os arquivos\0*.*\0\0";
    of.Flags=OFN_FILEMUSTEXIST|OFN_PATHMUSTEXIST|OFN_NOCHANGEDIR|OFN_EXPLORER;
    if(!GetOpenFileNameW(&of))return;
    fs::path picked=path;
    auto ext=picked.extension().wstring();
    for(auto& letter:ext)letter=std::towlower(letter);
    if(ext!=L".cue" && ext!=L".bin" && ext!=L".img"){
        image.clear();disk_error=true;
        error_state(L"Formato de disco incompatível",L"Escolha um arquivo .cue, .bin ou .img da edição USA. Um arquivo .iso comum não funciona.");
        return;
    }
    image=picked;disk_error=false;
    prepare_selected();
}
static HWND control(const wchar_t* type,const wchar_t* text,DWORD style,int x,int y,int w,int h,int id,HFONT face=nullptr) {
    HWND child=CreateWindowExW(0,type,text,WS_CHILD|WS_VISIBLE|style,px(x),px(y),px(w),px(h),win,(HMENU)(INT_PTR)id,GetModuleHandle(NULL),NULL);
    SendMessageW(child,WM_SETFONT,(WPARAM)(face?face:font),TRUE);return child;
}
static void home() {
    if(ready_to_play())state(L"Jogo pronto",L"Clique em Jogar para começar.");
    else if(imported_disc())state(L"Prepare a versão atual",L"Sua cópia USA já está nesta pasta. Clique em Preparar jogo para atualizar.");
    else state(L"Escolha o disco original",L"Selecione o arquivo .cue da edição USA (SLUS-00583) e deixe o .bin na mesma pasta. Também aceitamos .bin ou .img bruto. Arquivos .iso comuns são incompatíveis.");
    refresh();
}
static LRESULT CALLBACK handler(HWND window,UINT msg,WPARAM wp,LPARAM lp) {
    if(msg==WM_CTLCOLORSTATIC){
        const auto dc=(HDC)wp;const int id=GetDlgCtrlID((HWND)lp);
        SetBkMode(dc,TRANSPARENT);
        SetTextColor(dc,id==heading_id ? RGB(255,242,220) :
                        id==step_id && failed ? RGB(157,40,31) : RGB(49,45,41));
        return (LRESULT)(id==heading_id ? header : (id==report_id || id==step_id || id==disc_id) ? panel : paper);
    }
    if(msg==WM_ERASEBKGND) {
        RECT area;GetClientRect(window,&area);FillRect((HDC)wp,&area,paper);
        const RECT band={0,0,area.right,px(104)};
        const RECT content={px(24),px(126),area.right-px(24),px(313)};
        FillRect((HDC)wp,&band,header);FillRect((HDC)wp,&content,panel);
        DrawIconEx((HDC)wp,px(30),px(32),(HICON)GetClassLongPtrW(window,GCLP_HICON),px(36),px(36),0,NULL,DI_NORMAL);
        return 1;
    }
    if(msg==WM_DRAWITEM && wp==choose_id){
        const auto& item=*reinterpret_cast<DRAWITEMSTRUCT*>(lp);
        const bool disabled=item.itemState&ODS_DISABLED, pressed=item.itemState&ODS_SELECTED;
        COLORREF fill=disabled?RGB(231,222,207):pressed?RGB(203,127,40):RGB(241,169,77);
        HIGHCONTRASTW contrast={sizeof contrast};
        if(SystemParametersInfoW(SPI_GETHIGHCONTRAST,sizeof contrast,&contrast,0) && (contrast.dwFlags&HCF_HIGHCONTRASTON))
            fill=GetSysColor(disabled?COLOR_BTNFACE:COLOR_HIGHLIGHT);
        HBRUSH brush=CreateSolidBrush(fill);FillRect(item.hDC,&item.rcItem,brush);DeleteObject(brush);
        SetBkMode(item.hDC,TRANSPARENT);
        SetTextColor(item.hDC,contrast.dwFlags&HCF_HIGHCONTRASTON?GetSysColor(disabled?COLOR_GRAYTEXT:COLOR_HIGHLIGHTTEXT):
                     disabled?RGB(94,84,76):RGB(42,26,13));
        SelectObject(item.hDC,label_font);
        wchar_t caption[128];GetWindowTextW(item.hwndItem,caption,128);
        RECT rect=item.rcItem;DrawTextW(item.hDC,caption,-1,&rect,DT_CENTER|DT_VCENTER|DT_SINGLELINE);
        if(item.itemState&ODS_FOCUS){InflateRect(&rect,-px(4),-px(4));DrawFocusRect(item.hDC,&rect);}
        return TRUE;
    }
    if(msg==WM_COMMAND && HIWORD(wp)==BN_CLICKED){
        const int id=LOWORD(wp);
        if(id==details_id && regular(details_path))
            ShellExecuteW(win,L"open",L"notepad.exe",quote(details_path.wstring()).c_str(),NULL,SW_SHOWNORMAL);
        if(process_handle)return 0;
        if(id==replace_id)choose_disc();
        if(id==choose_id){
            if(ready_to_play() && !failed) {
                if(gpu_check())start(L"play");
                else error_state(L"Driver de vídeo incompatível",L"Atualize o driver da sua placa de vídeo para uma versão com OpenGL 3.3 e tente novamente.");
            } else if(selected_disc())prepare_selected();
            else choose_disc();
        }
        return 0;
    }
    if(msg==WM_TIMER && process_handle) {
        if(operation==L"prepare")update_preparation_status();
        if(WaitForSingleObject(process_handle,0)!=WAIT_OBJECT_0)return 0;
        DWORD status=1;GetExitCodeProcess(process_handle,&status);CloseHandle(process_handle);process_handle=NULL;
        if(operation_job){CloseHandle(operation_job);operation_job=NULL;}
        const auto finished=operation;operation.clear();
        if(finished==L"check") {
            if(status==0){start(L"prepare");return 0;}
            if(status==3 && !auto_libraries_attempted){
                auto_libraries_attempted=true;start(L"install-libraries");return 0;
            }
            auto reason=read(data/L"last-error.txt");
            error_state(L"Seu computador precisa de um ajuste",
                        reason.empty()?L"Execute novamente o instalador completo ou abra Ver detalhes.":reason,
                        status==2?L"requirements.txt":L"setup.log");
        } else if(finished==L"install-libraries" && status==0) {
            start(L"check");
        } else if(finished==L"prepare" && status==0) {
            image.clear();show_progress(true,1,1);
            state(L"Jogo pronto",L"Clique em Jogar para começar. Depois, abra pelo atalho Duke Nuken TTK - Recomp.");
            refresh();
        } else if(finished==L"play" && status==0) {
            DestroyWindow(window);
        } else {
            if(finished==L"play"){direct_play=false;ShowWindow(win,SW_SHOWNORMAL);}
            if(status==4){image.clear();disk_error=true;}
            auto reason=read(data/L"last-error.txt");
            if(reason.empty())reason=L"Abra Ver detalhes e tente novamente.";
            error_state(status==4?L"Confira o arquivo do disco":L"Não foi possível continuar",reason);
        }
        return 0;
    }
    if(msg==WM_CLOSE) {
        if(process_handle){
            if(operation==L"play"){ShowWindow(win,SW_HIDE);return 0;}
            if(MessageBoxW(win,L"Interromper a preparação agora? Você poderá continuar depois.",L"Interromper preparação",MB_YESNO|MB_DEFBUTTON2|MB_ICONQUESTION)!=IDYES)return 0;
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
    INITCOMMONCONTROLSEX common={sizeof common,ICC_PROGRESS_CLASS};
    InitCommonControlsEx(&common);
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
    SetProcessDPIAware();
    HDC screen=GetDC(NULL);
    dpi=GetDeviceCaps(screen,LOGPIXELSX);
    ReleaseDC(NULL,screen);
    paper=CreateSolidBrush(RGB(255,253,249));
    panel=CreateSolidBrush(RGB(246,241,233));
    header=CreateSolidBrush(RGB(43,31,22));
    WNDCLASSW cls={};cls.lpfnWndProc=handler;cls.hInstance=instance;cls.lpszClassName=L"DukeTTKSetup";cls.hCursor=LoadCursor(NULL,IDC_ARROW);
    cls.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(101));
    RegisterClassW(&cls);
    const DWORD style=WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX;
    RECT size={0,0,px(650),px(411)};
    AdjustWindowRectEx(&size,style,FALSE,0);
    win=CreateWindowW(cls.lpszClassName,L"Duke Nukem: Time to Kill - Preparar o jogo",style,CW_USEDEFAULT,CW_USEDEFAULT,size.right-size.left,size.bottom-size.top,NULL,NULL,instance,NULL);
    font=CreateFontW(-px(16),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
    label_font=CreateFontW(-px(17),0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
    title_font=CreateFontW(-px(27),0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
    heading=control(L"STATIC",L"Duke Nukem: Time to Kill",0,82,32,535,42,heading_id,title_font);
    step=control(L"STATIC",L"",0,44,146,560,27,step_id,label_font);
    report=control(L"STATIC",L"",0,44,181,558,66,report_id);
    disc_label=control(L"STATIC",L"",SS_PATHELLIPSIS,44,253,558,24,disc_id);
    progress_bar=control(PROGRESS_CLASSW,L"",0,44,289,558,8,0);
    SendMessageW(progress_bar,PBM_SETRANGE32,0,100);
    show_progress(false);
    details=control(L"BUTTON",L"Ver detalhes",WS_TABSTOP,24,346,116,36,details_id);
    replace_disc=control(L"BUTTON",L"Trocar disco…",WS_TABSTOP,258,346,139,36,replace_id);
    action=control(L"BUTTON",L"",WS_TABSTOP|BS_OWNERDRAW,414,342,212,44,choose_id);
    kit=app/L"toolchain";SetTimer(win,1,220,NULL);
    if(direct_play && ready_to_play() && gpu_check())start(L"play");
    if(!process_handle) {
        direct_play=false;
        ShowWindow(win,SW_SHOWNORMAL);
        if(!failed)home();
        UpdateWindow(win);
    }
    MSG message;while(GetMessageW(&message,NULL,0,0)>0){
        if((message.message==WM_KEYDOWN || message.message==WM_SYSKEYDOWN) && message.wParam==VK_RETURN &&
           GetFocus()==action && IsWindowEnabled(action)){SendMessageW(action,BM_CLICK,0,0);continue;}
        if(!IsDialogMessageW(win,&message)){TranslateMessage(&message);DispatchMessageW(&message);}
    }
    DeleteObject(font);DeleteObject(label_font);DeleteObject(title_font);
    DeleteObject(paper);DeleteObject(panel);DeleteObject(header);
    CloseHandle(lock);CoUninitialize();return 0;
}
